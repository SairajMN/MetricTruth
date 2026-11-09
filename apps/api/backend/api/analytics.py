import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from backend.core.event_bus import event_bus
from backend.core.orchestrator import orchestrator
from backend.db import app_engine, get_readonly_connection, readonly_engine
from backend.models.tables import (
    agent_runs,
    certified_metrics,
    data_source_runs,
    query_evidence,
    query_runs,
)
from backend.query.plan_schema import Period
from backend.security.auth import RoleType, resolve_role

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class AskRequest(BaseModel):
    question: str
    metric_override: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    injected_unverified_claim: str | None = None
    use_cache: bool = True


@router.get("/overview")
async def get_command_center_overview() -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    async with app_engine.connect() as conn:
        metrics_count = (
            await conn.execute(
                select(func.count()).select_from(certified_metrics).where(certified_metrics.c.status == "approved")
            )
        ).scalar_one()
        total_metrics_count = (
            await conn.execute(select(func.count()).select_from(certified_metrics))
        ).scalar_one()
        queries_count = (
            await conn.execute(select(func.count()).select_from(agent_runs))
        ).scalar_one()
        verified_count = (
            await conn.execute(
                select(func.count())
                .select_from(agent_runs)
                .where(agent_runs.c.status == "COMPLETED")
            )
        ).scalar_one()

        source_rows = (
            await conn.execute(
                select(
                    data_source_runs.c.source_name,
                    data_source_runs.c.batch_id,
                    data_source_runs.c.freshness_watermark,
                    data_source_runs.c.accepted_rows,
                    data_source_runs.c.status,
                ).order_by(data_source_runs.c.uploaded_at.desc())
            )
        ).mappings().all()

    seen_sources: dict[str, dict[str, Any]] = {}
    for sr in source_rows:
        sname = str(sr["source_name"])
        if sname not in seen_sources:
            wm = sr["freshness_watermark"]
            age_h = round(max(0.0, (now_utc - wm).total_seconds() / 3600.0), 1) if wm else 999.0
            seen_sources[sname] = {
                "source_name": sname,
                "batch_id": sr["batch_id"],
                "freshness_watermark": wm.isoformat() if wm else None,
                "age_hours": age_h,
                "accepted_rows": sr["accepted_rows"],
                "health": "HEALTHY" if age_h <= 24.0 else "WARNING",
            }

    # Live SQL query on reporting views for November 2026 KPIs
    is_sqlite = readonly_engine.dialect.name == "sqlite"
    async with get_readonly_connection(readonly_engine) as ro_conn:
        from sqlalchemy import text

        perf_sql = text(
            """
            SELECT COALESCE(SUM(p.spend_usd), 0) AS spend,
                   COALESCE(SUM(p.clicks), 0) AS clicks,
                   COALESCE(SUM(p.impressions), 0) AS impressions
            FROM v_daily_campaign_performance p
            JOIN v_campaigns c ON c.campaign_id = p.campaign_id
            WHERE c.campaign_status = 'ACTIVE'
              AND p.report_date >= :s_dt AND p.report_date <= :e_dt
            """
        )
        acq_sql = text(
            """
            SELECT COUNT(DISTINCT a.customer_id) AS customers,
                   COALESCE(SUM(a.first_order_revenue_usd), 0) AS revenue
            FROM v_customer_acquisitions a
            JOIN v_campaigns c ON c.campaign_id = a.campaign_id
            WHERE c.campaign_status = 'ACTIVE'
              AND a.is_valid = :valid_val
              AND a.attribution_model = 'last_non_direct_paid_click'
              AND a.acquired_at >= :s_ts AND a.acquired_at < :e_ts
            """
        )
        perf_params = {
            "s_dt": "2026-11-01" if is_sqlite else date(2026, 11, 1),
            "e_dt": "2026-11-30" if is_sqlite else date(2026, 11, 30),
        }
        acq_params = {
            "valid_val": 1 if is_sqlite else True,
            "s_ts": "2026-11-01 00:00:00" if is_sqlite else datetime(2026, 11, 1, 0, 0, 0),
            "e_ts": "2026-12-01 00:00:00" if is_sqlite else datetime(2026, 12, 1, 0, 0, 0),
        }
        p_res = (await ro_conn.execute(perf_sql, perf_params)).mappings().first()
        a_res = (await ro_conn.execute(acq_sql, acq_params)).mappings().first()

    spend = float(p_res["spend"] if p_res else 0.0)
    clicks = int(p_res["clicks"] if p_res else 0)
    customers = int(a_res["customers"] if a_res else 0)
    revenue = float(a_res["revenue"] if a_res else 0.0)

    paid_cac = round(spend / customers, 2) if customers > 0 else 0.0
    cvr_pct = round((customers / clicks) * 100.0, 2) if clicks > 0 else 0.0

    recent_runs = await orchestrator.list_recent_runs(limit=8)

    return {
        "summary_counters": {
            "certified_metrics": metrics_count,
            "total_registered_metrics": total_metrics_count,
            "active_data_sources": len(seen_sources),
            "queries_today": queries_count,
            "successful_verifications": verified_count,
        },
        "business_performance": {
            "period": "November 2026",
            "paid_cac_usd": paid_cac,
            "conversion_rate_pct": cvr_pct,
            "attributed_revenue_usd": revenue,
            "new_customers": customers,
            "paid_spend_usd": spend,
            "total_clicks": clicks,
        },
        "data_health": list(seen_sources.values()),
        "recent_investigations": recent_runs,
    }


@router.post("/ask")
async def ask_question(
    req: AskRequest,
    role: RoleType = Depends(resolve_role),
) -> dict[str, Any]:
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    period_override = None
    if req.period_start and req.period_end:
        period_override = Period(start_date=req.period_start, end_date=req.period_end)

    result = await orchestrator.ask(
        question=req.question,
        metric_override=req.metric_override,
        period_override=period_override,
        injected_unverified_claim=req.injected_unverified_claim,
        use_cache=req.use_cache,
        actor_role=role,
    )
    return result.model_dump(mode="json")


@router.get("/runs")
async def list_runs(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, Any]:
    runs = await orchestrator.list_recent_runs(limit=limit)
    return {"runs": runs}


@router.get("/runs/{run_id}")
async def get_run_details(run_id: str) -> dict[str, Any]:
    run = await orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return run.model_dump(mode="json")


@router.get("/runs/{run_id}/report")
async def get_run_report(run_id: str) -> dict[str, Any]:
    run = await orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return {
        "run_id": run.run_id,
        "question": run.question,
        "status": run.status,
        "report": run.report.model_dump(mode="json") if run.report else None,
        "audit_bundle": run.audit_bundle.model_dump(mode="json") if run.audit_bundle else None,
        "clarification": run.clarification.model_dump(mode="json") if run.clarification else None,
        "failure_reason": run.failure_reason,
    }


@router.get("/runs/{run_id}/sql")
async def get_run_sql(run_id: str) -> dict[str, Any]:
    run = await orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    async with app_engine.connect() as conn:
        q_row = (
            await conn.execute(
                select(query_runs).where(query_runs.c.agent_run_id == run_id)
            )
        ).mappings().first()

    return {
        "run_id": run.run_id,
        "compiled_sql": run.compiled_sql.model_dump(mode="json") if run.compiled_sql else None,
        "query_validation": run.query_validation.model_dump(mode="json") if run.query_validation else None,
        "query_run_record": dict(q_row) if q_row else None,
    }


@router.get("/runs/{run_id}/evidence")
async def get_run_evidence(run_id: str) -> dict[str, Any]:
    run = await orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    async with app_engine.connect() as conn:
        ev_row = (
            await conn.execute(
                select(query_evidence).where(query_evidence.c.agent_run_id == run_id)
            )
        ).mappings().first()
    return {
        "run_id": run.run_id,
        "metric_resolution": run.metric_resolution.model_dump(mode="json") if run.metric_resolution else None,
        "audit_bundle": run.audit_bundle.model_dump(mode="json") if run.audit_bundle else None,
        "raw_evidence_record": {
            "evidence_id": ev_row["evidence_id"],
            "query_run_id": ev_row["query_run_id"],
            "rows": json.loads(ev_row["rows_json"]),
        }
        if ev_row
        else None,
    }


@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    request: Request,
    stream: bool = Query(default=False),
) -> Any:
    accept = request.headers.get("accept", "")
    if stream or "text/event-stream" in accept:
        async def _sse_generator():
            q = event_bus.subscribe(run_id)
            try:
                while True:
                    item = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(item, default=str)}\n\n"
                    if item.get("type") == "RUN_COMPLETE":
                        break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'HEARTBEAT'})}\n\n"
            finally:
                event_bus.unsubscribe(run_id, q)

        return StreamingResponse(_sse_generator(), media_type="text/event-stream")

    run = await orchestrator.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return {
        "run_id": run.run_id,
        "status": run.status,
        "events": [e.model_dump(mode="json") for e in run.events],
        "usage": run.usage.model_dump(mode="json"),
        "duration_ms": run.duration_ms,
        "cache_hit": run.cache_hit,
    }
