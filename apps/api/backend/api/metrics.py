from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.security.audit_log import log_security_event
from backend.security.auth import RoleType, require_admin
from backend.semantic.metric_loader import upsert_single_metric
from backend.semantic.models import CertifiedMetricSpec
from backend.semantic.registry import MetricRegistryRepository

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])
repo = MetricRegistryRepository()


@router.get("")
async def list_metrics(status: str | None = Query(default=None)) -> dict[str, Any]:
    specs = await repo.list_metrics(status=status)
    return {"metrics": [s.model_dump(mode="json") for s in specs]}


@router.get("/{metric_id}")
async def get_metric(metric_id: str) -> dict[str, Any]:
    spec = await repo.get_metric(metric_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_id}' not found.")
    versions = await repo.list_versions(metric_id)
    return {
        "metric": spec.model_dump(mode="json"),
        "versions": versions,
    }


@router.post("")
async def create_metric(
    spec: CertifiedMetricSpec,
    role: RoleType = Depends(require_admin),
) -> dict[str, Any]:
    existing = await repo.get_metric(spec.metric_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Metric '{spec.metric_id}' already exists.")
    try:
        saved = await upsert_single_metric(spec, approved_by=role if spec.status == "approved" else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await log_security_event(
        actor_role=role,
        event_type="METRIC_CREATED",
        severity="INFO",
        resource=spec.metric_id,
        details={"version": spec.version, "status": spec.status},
    )
    return {"metric": saved.model_dump(mode="json")}


@router.put("/{metric_id}")
async def update_metric(
    metric_id: str,
    spec: CertifiedMetricSpec,
    role: RoleType = Depends(require_admin),
) -> dict[str, Any]:
    if spec.metric_id != metric_id:
        raise HTTPException(status_code=400, detail="Path metric_id does not match payload metric_id.")
    existing = await repo.get_metric(metric_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_id}' not found.")
    try:
        saved = await upsert_single_metric(spec, approved_by=role if spec.status == "approved" else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await log_security_event(
        actor_role=role,
        event_type="METRIC_UPDATED",
        severity="INFO",
        resource=metric_id,
        details={"version": spec.version, "status": spec.status},
    )
    return {"metric": saved.model_dump(mode="json")}


@router.post("/{metric_id}/approve")
async def approve_metric(
    metric_id: str,
    role: RoleType = Depends(require_admin),
) -> dict[str, Any]:
    spec = await repo.get_metric(metric_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Metric '{metric_id}' not found.")
    spec.status = "approved"
    spec.version += 1
    saved = await upsert_single_metric(spec, approved_by=role)
    await log_security_event(
        actor_role=role,
        event_type="METRIC_APPROVED",
        severity="INFO",
        resource=metric_id,
        details={"new_version": saved.version, "approved_by": role},
    )
    return {"metric": saved.model_dump(mode="json")}

