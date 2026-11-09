from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.agents.claim_validator import ClaimValidator
from backend.agents.insight_generator import InsightGenerator
from backend.agents.metric_resolver import MetricResolver
from backend.agents.query_planner import QueryPlanner
from backend.agents.question_planner import QuestionPlanner
from backend.agents.schema_explorer import SchemaExplorer
from backend.cache import WatermarkCache, cache
from backend.core.event_bus import EventBus, event_bus
from backend.core.execution_state import (
    ClarificationPayload,
    OrchestratorRunResult,
    StepTraceEvent,
)
from backend.core.llm_client import LLMRouterClient
from backend.db import app_engine, readonly_engine
from backend.models.tables import (
    agent_events,
    agent_runs,
    data_source_runs,
    tool_invocations,
)
from backend.observability.cost_tracker import RunBudgetLedger
from backend.observability.telemetry import trace_agent_step
from backend.query.plan_schema import Period
from backend.query.query_executor import QueryExecutor
from backend.query.query_validator import QueryValidator
from backend.query.sql_compiler import SQLCompiler
from backend.security.audit_log import log_security_event
from backend.semantic.registry import MetricRegistryRepository
from backend.verification.evidence_builder import EvidenceBuilder
from backend.verification.result_validator import ResultValidator


class MetricTruthOrchestrator:
    def __init__(
        self,
        app_db: AsyncEngine | None = None,
        ro_db: AsyncEngine | None = None,
        llm_client: LLMRouterClient | None = None,
        cache_backend: WatermarkCache | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self._app_db = app_db or app_engine
        self._ro_db = ro_db or readonly_engine
        self._llm = llm_client or LLMRouterClient()
        self._cache = cache_backend or cache
        self._bus = bus or event_bus

        self._repo = MetricRegistryRepository(engine=self._app_db)
        self._question_planner = QuestionPlanner(llm_client=self._llm)
        self._metric_resolver = MetricResolver(repo=self._repo)
        self._schema_explorer = SchemaExplorer()
        self._query_planner = QueryPlanner(llm_client=self._llm)
        self._sql_compiler = SQLCompiler()
        self._query_validator = QueryValidator()
        self._query_executor = QueryExecutor(engine=self._ro_db)
        self._result_validator = ResultValidator(engine=self._app_db)
        self._evidence_builder = EvidenceBuilder(engine=self._app_db)
        self._insight_generator = InsightGenerator(llm_client=self._llm)
        self._claim_validator = ClaimValidator()

    async def ask(
        self,
        question: str,
        metric_override: str | None = None,
        period_override: Period | None = None,
        injected_unverified_claim: str | None = None,
        use_cache: bool = True,
        actor_role: str = "viewer",
    ) -> OrchestratorRunResult:
        t_start = time.perf_counter()
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        run_id = f"MT_{uuid.uuid4().hex[:8].upper()}"
        ledger = RunBudgetLedger()
        events: list[StepTraceEvent] = []
        seq = 1

        async def _emit(
            comp: str,
            label: str,
            status: str,
            dur_ms: float,
            details: dict[str, Any],
        ) -> None:
            nonlocal seq
            ev = StepTraceEvent(
                sequence=seq,
                component=comp,
                label=label,
                status=status,  # type: ignore[arg-type]
                duration_ms=round(dur_ms, 2),
                details=details,
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            seq += 1
            events.append(ev)
            await self._bus.publish_step(run_id, ev)

        watermark_sig = await self._current_watermark_signature()
        cache_key = self._build_cache_key(question, metric_override, period_override, watermark_sig)
        if use_cache and not injected_unverified_claim:
            cached_payload = await self._cache.get_json(cache_key)
            if cached_payload is not None:
                cached_res = OrchestratorRunResult.model_validate(cached_payload)
                cached_res.run_id = run_id
                cached_res.cache_hit = True
                cached_res.usage = RunBudgetLedger()
                cached_res.created_at = now_utc
                cached_res.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                cached_res.duration_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
                await self._persist_run(cached_res)
                await self._bus.publish_done(run_id, cached_res.status)
                return cached_res

        state = OrchestratorRunResult(
            run_id=run_id,
            question=question,
            status="RUNNING",
            current_stage="question_planner",
            created_at=now_utc,
        )

        # Stage 1: Question Planner
        s_t0 = time.perf_counter()
        with trace_agent_step(run_id, "question_planner"):
            q_plan = await self._question_planner.plan(
                question=question,
                ledger=ledger,
                metric_override=metric_override,
                period_override=period_override,
            )
        state.question_plan = q_plan

        if q_plan.intent in ("SECURITY_VIOLATION", "UNSUPPORTED_FORMULA"):
            await _emit(
                "Question Planner",
                "Understanding business question",
                "BLOCKED",
                (time.perf_counter() - s_t0) * 1000.0,
                {"intent": q_plan.intent, "reason": q_plan.security_violation_reason},
            )
            await log_security_event(
                actor_role=actor_role,
                event_type=q_plan.intent,
                severity="HIGH",
                resource="question_planner",
                details={"question": question, "reason": q_plan.security_violation_reason},
                engine=self._app_db,
            )
            return await self._finish(
                state,
                status="BLOCKED",
                stage="question_planner",
                ledger=ledger,
                events=events,
                t_start=t_start,
                failure_reason=q_plan.security_violation_reason,
            )

        await _emit(
            "Question Planner",
            "Understanding business question",
            "COMPLETED",
            (time.perf_counter() - s_t0) * 1000.0,
            {
                "intent": q_plan.intent,
                "primary_metric": q_plan.primary_metric,
                "comparison": q_plan.comparison,
                "group_by": q_plan.group_by,
            },
        )

        if q_plan.requires_clarification:
            state.clarification = ClarificationPayload(
                question=q_plan.clarification_question or "Please clarify your request.",
                options=q_plan.clarification_options,
            )
            return await self._finish(
                state,
                status="CLARIFICATION_REQUIRED",
                stage="question_planner",
                ledger=ledger,
                events=events,
                t_start=t_start,
            )

        # Stage 2: Metric Resolver
        s_t0 = time.perf_counter()
        with trace_agent_step(run_id, "metric_resolver"):
            m_res = await self._metric_resolver.resolve(
                requested_metric=q_plan.primary_metric,
                question_text=question,
                has_campaign_context=q_plan.has_campaign_context,
                explicit_selection=(metric_override is not None),
            )
        state.metric_resolution = m_res

        if m_res.status == "AMBIGUOUS":
            await _emit(
                "Metric Resolver",
                "Resolving certified metrics",
                "COMPLETED",
                (time.perf_counter() - s_t0) * 1000.0,
                {"status": "AMBIGUOUS", "candidates": m_res.candidate_metrics},
            )
            state.clarification = ClarificationPayload(
                question=m_res.clarification_question or "Which certified metric should I investigate?",
                options=["Paid CAC", "Blended CAC", "Fully Loaded CAC"],
                candidate_metrics=m_res.candidate_metrics,
            )
            return await self._finish(
                state,
                status="CLARIFICATION_REQUIRED",
                stage="metric_resolver",
                ledger=ledger,
                events=events,
                t_start=t_start,
            )

        if m_res.status != "RESOLVED" or m_res.metric_spec is None:
            await _emit(
                "Metric Resolver",
                "Resolving certified metrics",
                "BLOCKED",
                (time.perf_counter() - s_t0) * 1000.0,
                {"status": m_res.status, "reason": m_res.rejection_reason},
            )
            await log_security_event(
                actor_role=actor_role,
                event_type=m_res.status,
                severity="MEDIUM",
                resource=q_plan.primary_metric,
                details={"reason": m_res.rejection_reason},
                engine=self._app_db,
            )
            return await self._finish(
                state,
                status="BLOCKED",
                stage="metric_resolver",
                ledger=ledger,
                events=events,
                t_start=t_start,
                failure_reason=m_res.rejection_reason,
            )

        spec = m_res.metric_spec
        await _emit(
            "Metric Resolver",
            "Resolving certified metrics",
            "COMPLETED",
            (time.perf_counter() - s_t0) * 1000.0,
            {
                "selected_metric": spec.metric_id,
                "version": spec.version,
                "status": spec.status.upper(),
            },
        )

        # Stage 3: Schema Explorer
        s_t0 = time.perf_counter()
        with trace_agent_step(run_id, "schema_explorer"):
            schema_ctx = self._schema_explorer.explore(spec)
        await _emit(
            "Schema Explorer",
            "Mapping approved data relationships",
            "COMPLETED",
            (time.perf_counter() - s_t0) * 1000.0,
            {"reporting_views": schema_ctx.reporting_views, "allowed_dimensions": schema_ctx.allowed_dimensions},
        )

        # Stages 4, 5, 6: Bounded Plan -> Compile -> Validate Loop (max 2 iterations)
        replan_feedback: str | None = None
        valid_plan_found = False
        for _attempt in range(2):
            s_t0 = time.perf_counter()
            with trace_agent_step(run_id, "query_planner"):
                q_plan_struct = await self._query_planner.create_plan(
                    question_plan=q_plan,
                    spec=spec,
                    schema_ctx=schema_ctx,
                    ledger=ledger,
                    replan_feedback=replan_feedback,
                )
            state.query_plan = q_plan_struct
            await _emit(
                "Query Planner",
                "Building analytical plan",
                "COMPLETED",
                (time.perf_counter() - s_t0) * 1000.0,
                q_plan_struct.model_dump(mode="json"),
            )

            s_t0 = time.perf_counter()
            with trace_agent_step(run_id, "sql_compiler"):
                artifact = self._sql_compiler.compile(
                    plan=q_plan_struct,
                    spec=spec,
                    dialect_name=self._ro_db.dialect.name,
                )
            state.compiled_sql = artifact
            await _emit(
                "SQL Compiler",
                "Compiling deterministic SQL",
                "COMPLETED",
                (time.perf_counter() - s_t0) * 1000.0,
                {"fingerprint": artifact.query_fingerprint, "tables": artifact.tables_accessed},
            )

            s_t0 = time.perf_counter()
            with trace_agent_step(run_id, "query_validator"):
                val_report = self._query_validator.validate(q_plan_struct, spec, artifact)
            state.query_validation = val_report

            if val_report.passed:
                await _emit(
                    "Query Validator",
                    "Validating query & permissions",
                    "PASSED",
                    (time.perf_counter() - s_t0) * 1000.0,
                    {"checks_passed": len(val_report.checks)},
                )
                valid_plan_found = True
                break

            replan_feedback = "; ".join(val_report.failed_reasons)
            await _emit(
                "Query Validator",
                "Validating query & permissions",
                "FAILED",
                (time.perf_counter() - s_t0) * 1000.0,
                {"failed_reasons": val_report.failed_reasons},
            )

        if not valid_plan_found or state.query_plan is None or state.compiled_sql is None or state.query_validation is None:
            await self._evidence_builder.record_provenance(
                agent_run_id=run_id,
                plan=state.query_plan,  # type: ignore[arg-type]
                validation=state.query_validation,  # type: ignore[arg-type]
            )
            return await self._finish(
                state,
                status="BLOCKED",
                stage="query_validator",
                ledger=ledger,
                events=events,
                t_start=t_start,
                failure_reason=f"Query plan failed policy validation: {replan_feedback}",
            )

        # Stage 7: Read-Only Database Executor
        s_t0 = time.perf_counter()
        try:
            with trace_agent_step(run_id, "database_executor"):
                exec_res = await self._query_executor.execute(state.compiled_sql)
            await _emit(
                "Database Executor",
                "Executing read-only SQL",
                "COMPLETED",
                (time.perf_counter() - s_t0) * 1000.0,
                {"rows_returned": exec_res.row_count, "execution_ms": exec_res.execution_ms},
            )
        except Exception as exc:
            await _emit(
                "Database Executor",
                "Executing read-only SQL",
                "FAILED",
                (time.perf_counter() - s_t0) * 1000.0,
                {"error": str(exc)},
            )
            return await self._finish(
                state,
                status="FAILED",
                stage="database_executor",
                ledger=ledger,
                events=events,
                t_start=t_start,
                failure_reason=(
                    f"QUERY EXECUTION FAILED — Reason: {exc}. "
                    f"Requested metric: {spec.name}. Result: NOT AVAILABLE. "
                    "Action: No numerical conclusion generated."
                ),
            )

        # Stage 8: Independent Result Auditor
        s_t0 = time.perf_counter()
        with trace_agent_step(run_id, "result_auditor"):
            audit_bundle = await self._result_validator.validate_results(
                raw_rows=exec_res.rows,
                spec=spec,
                artifact=state.compiled_sql,
            )
            await self._evidence_builder.record_provenance(
                agent_run_id=run_id,
                plan=state.query_plan,
                validation=state.query_validation,
                artifact=state.compiled_sql,
                raw_rows=exec_res.rows,
                execution_ms=exec_res.execution_ms,
                audit_bundle=audit_bundle,
            )
        state.audit_bundle = audit_bundle

        if audit_bundle.overall_status == "FAILED":
            await _emit(
                "Result Auditor",
                "Auditing numerical results",
                "FAILED",
                (time.perf_counter() - s_t0) * 1000.0,
                {
                    "numerical": audit_bundle.numerical.status,
                    "reconciliation": audit_bundle.reconciliation.status,
                    "freshness": audit_bundle.freshness.status,
                },
            )
            return await self._finish(
                state,
                status="FAILED",
                stage="result_auditor",
                ledger=ledger,
                events=events,
                t_start=t_start,
                failure_reason=(
                    "QUERY EXECUTION FAILED — Numerical verification, reconciliation, or source completeness failed. "
                    "Action: No numerical conclusion generated."
                ),
            )

        await _emit(
            "Result Auditor",
            "Auditing numerical results",
            "PASSED",
            (time.perf_counter() - s_t0) * 1000.0,
            {
                "overall_status": audit_bundle.overall_status,
                "numerical": audit_bundle.numerical.status,
                "reconciliation": audit_bundle.reconciliation.status,
                "freshness": audit_bundle.freshness.status,
            },
        )

        # Stage 9: Insight Generator
        s_t0 = time.perf_counter()
        with trace_agent_step(run_id, "insight_generator"):
            draft_report = await self._insight_generator.generate(
                bundle=audit_bundle,
                spec=spec,
                ledger=ledger,
                injected_unverified_claim=injected_unverified_claim,
            )
        await _emit(
            "Insight Generator",
            "Generating explanation",
            "COMPLETED",
            (time.perf_counter() - s_t0) * 1000.0,
            {"sections": len(draft_report.sections), "draft_claims": len(draft_report.claims)},
        )

        # Stage 10: Claim Validator
        s_t0 = time.perf_counter()
        with trace_agent_step(run_id, "claim_validator"):
            verified_report = self._claim_validator.validate_and_sanitize(draft_report, audit_bundle)
        state.report = verified_report
        await _emit(
            "Claim Validator",
            "Verifying analytical claims",
            "PASSED",
            (time.perf_counter() - s_t0) * 1000.0,
            {
                "kept_claims": len(verified_report.claims),
                "stripped_claims": len(verified_report.stripped_claims),
                "grounded_claim_rate": verified_report.grounded_claim_rate,
            },
        )

        final_state = await self._finish(
            state,
            status="COMPLETED",
            stage="completed",
            ledger=ledger,
            events=events,
            t_start=t_start,
        )

        if use_cache and not injected_unverified_claim and audit_bundle.overall_status == "VERIFIED":
            await self._cache.set_json(cache_key, final_state.model_dump(mode="json"))

        return final_state

    async def get_run(self, run_id: str) -> OrchestratorRunResult | None:
        async with self._app_db.connect() as conn:
            row = (
                await conn.execute(select(agent_runs.c.report_json).where(agent_runs.c.run_id == run_id))
            ).first()
        if not row or not row[0]:
            return None
        return OrchestratorRunResult.model_validate_json(row[0])

    async def list_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        stmt = (
            select(
                agent_runs.c.run_id,
                agent_runs.c.question,
                agent_runs.c.status,
                agent_runs.c.selected_metric_id,
                agent_runs.c.metric_version,
                agent_runs.c.input_tokens,
                agent_runs.c.output_tokens,
                agent_runs.c.model_calls,
                agent_runs.c.total_cost_usd,
                agent_runs.c.duration_ms,
                agent_runs.c.created_at,
            )
            .order_by(agent_runs.c.created_at.desc())
            .limit(limit)
        )
        async with self._app_db.connect() as conn:
            rows = (await conn.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def _finish(
        self,
        state: OrchestratorRunResult,
        status: str,
        stage: str,
        ledger: RunBudgetLedger,
        events: list[StepTraceEvent],
        t_start: float,
        failure_reason: str | None = None,
    ) -> OrchestratorRunResult:
        state.status = status  # type: ignore[assignment]
        state.current_stage = stage
        state.usage = ledger
        state.events = events
        state.failure_reason = failure_reason
        state.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        state.duration_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
        await self._persist_run(state)
        await self._bus.publish_done(state.run_id, state.status)
        return state

    async def _persist_run(self, state: OrchestratorRunResult) -> None:
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        sel_metric = (
            state.metric_resolution.selected_metric
            if state.metric_resolution and state.metric_resolution.selected_metric
            else None
        )
        sel_ver = (
            state.metric_resolution.definition_version
            if state.metric_resolution and state.metric_resolution.definition_version
            else None
        )
        async with self._app_db.begin() as conn:
            await conn.execute(
                agent_runs.insert().values(
                    run_id=state.run_id,
                    question=state.question,
                    status=state.status,
                    selected_metric_id=sel_metric,
                    metric_version=sel_ver,
                    current_stage=state.current_stage,
                    report_json=state.model_dump_json(),
                    clarification_json=state.clarification.model_dump_json() if state.clarification else None,
                    failure_reason=state.failure_reason,
                    input_tokens=state.usage.input_tokens,
                    output_tokens=state.usage.output_tokens,
                    cached_tokens=state.usage.cached_tokens,
                    model_calls=state.usage.model_calls,
                    retries=state.usage.retries,
                    total_cost_usd=state.usage.total_cost_usd,
                    duration_ms=state.duration_ms,
                    created_at=state.created_at,
                    completed_at=state.completed_at or now_utc,
                )
            )
            for ev in state.events:
                await conn.execute(
                    agent_events.insert().values(
                        event_id=f"EV_{uuid.uuid4().hex[:10].upper()}",
                        run_id=state.run_id,
                        sequence=ev.sequence,
                        component=ev.component,
                        status=ev.status,
                        duration_ms=ev.duration_ms,
                        details_json=json.dumps(ev.details, default=str),
                        created_at=ev.timestamp,
                    )
                )
            for call in state.usage.calls:
                await conn.execute(
                    tool_invocations.insert().values(
                        invocation_id=f"INV_{uuid.uuid4().hex[:10].upper()}",
                        run_id=state.run_id,
                        tool_name=call.component,
                        model_name=call.model_name,
                        input_tokens=call.input_tokens,
                        output_tokens=call.output_tokens,
                        cached_tokens=call.cached_tokens,
                        cost_usd=call.cost_usd,
                        duration_ms=call.duration_ms,
                        status="COMPLETED",
                        created_at=now_utc,
                    )
                )

    async def _current_watermark_signature(self) -> str:
        stmt = select(
            data_source_runs.c.source_name,
            data_source_runs.c.batch_id,
            data_source_runs.c.freshness_watermark,
        ).order_by(data_source_runs.c.uploaded_at.desc())
        async with self._app_db.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        raw = "|".join(f"{r[0]}:{r[1]}:{r[2]}" for r in rows[:10])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _build_cache_key(
        self,
        question: str,
        metric_override: str | None,
        period_override: Period | None,
        watermark_sig: str,
    ) -> str:
        norm = " ".join(question.strip().lower().split())
        per_str = period_override.model_dump_json() if period_override else ""
        digest = hashlib.sha256(
            f"{norm}||{metric_override or ''}||{per_str}||{watermark_sig}".encode("utf-8")
        ).hexdigest()
        return f"mt:ask:{digest}"


orchestrator = MetricTruthOrchestrator()

