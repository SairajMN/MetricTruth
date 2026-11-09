from datetime import datetime, timezone
import json
from typing import Any
import uuid
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.db import app_engine
from backend.models.tables import query_evidence, query_plans, query_runs
from backend.query.plan_schema import MetricQueryPlan
from backend.query.query_validator import QueryValidationReport
from backend.query.sql_compiler import CompiledQueryArtifact
from backend.verification.result_validator import AuditBundle


class EvidenceBuilder:
    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or app_engine

    async def record_provenance(
        self,
        agent_run_id: str,
        plan: MetricQueryPlan,
        validation: QueryValidationReport,
        artifact: CompiledQueryArtifact | None = None,
        raw_rows: list[dict[str, Any]] | None = None,
        execution_ms: float = 0.0,
        audit_bundle: AuditBundle | None = None,
    ) -> tuple[str, str | None]:
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        plan_id = f"PLN_{uuid.uuid4().hex[:10].upper()}"
        query_run_id = f"QR_{uuid.uuid4().hex[:10].upper()}" if artifact else None

        async with self._engine.begin() as conn:
            await conn.execute(
                query_plans.insert().values(
                    plan_id=plan_id,
                    agent_run_id=agent_run_id,
                    metric_id=plan.metric_id,
                    plan_json=plan.model_dump_json(),
                    is_valid=validation.passed,
                    validation_errors_json=json.dumps(validation.failed_reasons),
                    created_at=now_utc,
                )
            )

            if artifact and query_run_id:
                batch_ids = [
                    s.batch_id for s in (audit_bundle.freshness.sources if audit_bundle else []) if s.batch_id
                ]
                await conn.execute(
                    query_runs.insert().values(
                        query_run_id=query_run_id,
                        agent_run_id=agent_run_id,
                        metric_id=artifact.metric_id,
                        metric_version=artifact.metric_version,
                        data_sources_json=json.dumps(artifact.tables_accessed),
                        source_batch_ids_json=json.dumps(batch_ids),
                        compiled_sql=artifact.display_sql,
                        bound_params_json=json.dumps(artifact.bound_params, default=str),
                        query_fingerprint=artifact.query_fingerprint,
                        period_start=artifact.current_period.start_date,
                        period_end=artifact.current_period.end_date,
                        row_count=len(raw_rows or []),
                        execution_ms=execution_ms,
                        validation_status="PASSED" if validation.passed else "FAILED",
                        result_validation=audit_bundle.numerical.status if audit_bundle else "SKIPPED",
                        data_freshness=audit_bundle.freshness.status if audit_bundle else "SKIPPED",
                        execution_status="COMPLETED" if audit_bundle else "FAILED",
                        created_at=now_utc,
                    )
                )

                if audit_bundle is not None:
                    await conn.execute(
                        query_evidence.insert().values(
                            evidence_id=f"EV_{uuid.uuid4().hex[:10].upper()}",
                            query_run_id=query_run_id,
                            agent_run_id=agent_run_id,
                            rows_json=json.dumps(raw_rows or [], default=str),
                            audit_bundle_json=audit_bundle.model_dump_json(),
                            reconciliation_json=audit_bundle.reconciliation.model_dump_json(),
                            freshness_json=audit_bundle.freshness.model_dump_json(),
                            created_at=now_utc,
                        )
                    )

        return plan_id, query_run_id

