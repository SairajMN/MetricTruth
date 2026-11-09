from datetime import datetime, timedelta, timezone
import json
from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, update
from backend.cache import cache
from backend.data.ingestion import SOURCE_TABLES, ingest_csv_bytes
from backend.db import app_engine
from backend.models.tables import data_quality_results, data_source_runs
from backend.security.audit_log import log_security_event
from backend.security.auth import RoleType, require_analyst_or_admin

router = APIRouter(prefix="/api/v1/data", tags=["data"])


class SimulateFreshnessRequest(BaseModel):
    source_name: str = "daily_campaign_performance"
    age_hours: int = 48


@router.post("/upload")
async def upload_csv(
    source_name: str = Form(...),
    file: UploadFile = File(...),
    role: RoleType = Depends(require_analyst_or_admin),
) -> dict[str, Any]:
    content = await file.read()
    try:
        summary = await ingest_csv_bytes(
            source_name=source_name,
            file_name=file.filename or f"{source_name}.csv",
            content=content,
            engine=app_engine,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await cache.clear()
    await log_security_event(
        actor_role=role,
        event_type="DATA_INGESTION",
        severity="INFO",
        resource=source_name,
        details=summary.model_dump(mode="json"),
    )
    return summary.model_dump(mode="json")


@router.post("/simulate-freshness")
async def simulate_freshness(
    req: SimulateFreshnessRequest,
    role: RoleType = Depends(require_analyst_or_admin),
) -> dict[str, Any]:
    if req.source_name not in SOURCE_TABLES:
        raise HTTPException(status_code=400, detail=f"Unknown source: {req.source_name}")
    wm = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=req.age_hours)
    async with app_engine.begin() as conn:
        await conn.execute(
            update(data_source_runs)
            .where(data_source_runs.c.source_name == req.source_name)
            .values(freshness_watermark=wm)
        )
    await cache.clear()
    await log_security_event(
        actor_role=role,
        event_type="FRESHNESS_WATERMARK_SIMULATED",
        severity="WARNING" if req.age_hours > 24 else "INFO",
        resource=req.source_name,
        details={"age_hours": req.age_hours, "new_watermark": wm.isoformat()},
    )
    return {
        "source_name": req.source_name,
        "simulated_age_hours": req.age_hours,
        "freshness_watermark": wm.isoformat(),
    }


@router.get("/sources")
async def list_data_sources() -> dict[str, Any]:
    stmt = select(data_source_runs).order_by(data_source_runs.c.uploaded_at.desc())
    async with app_engine.connect() as conn:
        rows = (await conn.execute(stmt)).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        d["validation_failures"] = json.loads(d.pop("validation_failures_json", "[]"))
        items.append(d)
    return {"sources": items}


@router.get("/sources/{source_id}")
async def get_data_source(source_id: str) -> dict[str, Any]:
    stmt = (
        select(data_source_runs)
        .where(
            (data_source_runs.c.source_name == source_id)
            | (data_source_runs.c.batch_id == source_id)
        )
        .order_by(data_source_runs.c.uploaded_at.desc())
    )
    async with app_engine.connect() as conn:
        rows = (await conn.execute(stmt)).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found.")
    items = []
    for r in rows:
        d = dict(r)
        d["validation_failures"] = json.loads(d.pop("validation_failures_json", "[]"))
        items.append(d)
    return {"source_id": source_id, "runs": items}


@router.get("/quality")
async def get_data_quality() -> dict[str, Any]:
    stmt = select(data_quality_results).order_by(data_quality_results.c.checked_at.desc()).limit(100)
    async with app_engine.connect() as conn:
        rows = (await conn.execute(stmt)).mappings().all()
    return {"quality_checks": [dict(r) for r in rows]}

