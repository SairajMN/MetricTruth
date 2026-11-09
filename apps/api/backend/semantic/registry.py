from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.db import app_engine
from backend.models.tables import certified_metrics, metric_versions
from backend.semantic.models import CertifiedMetricSpec


class MetricRegistryRepository:
    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or app_engine

    async def list_metrics(self, status: str | None = None) -> list[CertifiedMetricSpec]:
        stmt = select(certified_metrics.c.spec_json).order_by(certified_metrics.c.metric_id)
        if status:
            stmt = stmt.where(certified_metrics.c.status == status)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [CertifiedMetricSpec.model_validate_json(r[0]) for r in rows]

    async def get_metric(self, metric_id: str) -> CertifiedMetricSpec | None:
        stmt = select(certified_metrics.c.spec_json).where(certified_metrics.c.metric_id == metric_id)
        async with self._engine.connect() as conn:
            row = (await conn.execute(stmt)).first()
        if not row:
            return None
        return CertifiedMetricSpec.model_validate_json(row[0])

    async def list_versions(self, metric_id: str) -> list[dict]:
        stmt = (
            select(
                metric_versions.c.version_id,
                metric_versions.c.version,
                metric_versions.c.status,
                metric_versions.c.spec_hash,
                metric_versions.c.approved_by,
                metric_versions.c.created_at,
            )
            .where(metric_versions.c.metric_id == metric_id)
            .order_by(metric_versions.c.version.desc())
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

