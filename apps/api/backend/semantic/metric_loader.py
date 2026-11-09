from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine
import yaml
from backend.config import ROOT_DIR
from backend.db import app_engine
from backend.models.tables import (
    certified_metrics,
    metric_dimensions,
    metric_sources,
    metric_versions,
)
from backend.semantic.models import CertifiedMetricSpec

REGISTRY_DIR = ROOT_DIR / "registry"

SOURCE_TO_VIEW = {
    "campaigns": "v_campaigns",
    "daily_campaign_performance": "v_daily_campaign_performance",
    "customer_acquisitions": "v_customer_acquisitions",
    "operating_expenses_monthly": "v_operating_expenses",
}

DIMENSION_TO_COLUMN = {
    "campaign": ("v_campaigns.campaign_name", None),
    "channel": ("v_campaigns.channel", ["SEARCH", "SOCIAL", "AFFILIATE", "DISPLAY"]),
    "date": ("v_daily_campaign_performance.report_date", None),
}


def load_yaml_metrics(metrics_dir: Path | None = None) -> list[CertifiedMetricSpec]:
    target_dir = metrics_dir or (REGISTRY_DIR / "metrics")
    specs: list[CertifiedMetricSpec] = []
    for path in sorted(target_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "metrics" in raw and isinstance(raw["metrics"], dict):
            for m_id, m_body in raw["metrics"].items():
                m_body.setdefault("metric_id", m_id)
                spec = CertifiedMetricSpec.model_validate(m_body)
                spec.validate_semantic_integrity()
                specs.append(spec)
        else:
            spec = CertifiedMetricSpec.model_validate(raw)
            spec.validate_semantic_integrity()
            specs.append(spec)
    return specs


async def sync_registry_to_db(
    engine: AsyncEngine | None = None, metrics_dir: Path | None = None
) -> list[CertifiedMetricSpec]:
    specs = load_yaml_metrics(metrics_dir)
    target_engine = engine or app_engine
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    async with target_engine.begin() as conn:
        for spec in specs:
            await _upsert_metric_spec(conn, spec, now_utc)
    return specs


async def upsert_single_metric(
    spec: CertifiedMetricSpec,
    engine: AsyncEngine | None = None,
    approved_by: str | None = None,
) -> CertifiedMetricSpec:
    spec.validate_semantic_integrity()
    target_engine = engine or app_engine
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    async with target_engine.begin() as conn:
        await _upsert_metric_spec(conn, spec, now_utc, approved_by=approved_by)
    return spec


async def _upsert_metric_spec(
    conn, spec: CertifiedMetricSpec, now_utc: datetime, approved_by: str | None = None
) -> None:
    spec_json = spec.model_dump_json()
    spec_hash = hashlib.sha256(spec_json.encode("utf-8")).hexdigest()

    existing = (
        await conn.execute(
            select(certified_metrics.c.metric_id).where(certified_metrics.c.metric_id == spec.metric_id)
        )
    ).first()

    values = {
        "metric_id": spec.metric_id,
        "name": spec.name,
        "description": spec.description.strip(),
        "formula_json": spec.formula.model_dump_json(),
        "numerator": spec.formula.numerator,
        "denominator": spec.formula.denominator,
        "aggregation": spec.formula.aggregation,
        "unit": spec.unit,
        "grain": spec.grain,
        "attribution_json": spec.attribution.model_dump_json(),
        "time_dimension": spec.time_dimension,
        "timezone": spec.timezone,
        "owner": spec.owner,
        "freshness_max_age_hours": spec.freshness.maximum_age_hours,
        "status": spec.status,
        "version": spec.version,
        "spec_json": spec_json,
        "updated_at": now_utc,
    }

    if existing:
        await conn.execute(
            certified_metrics.update()
            .where(certified_metrics.c.metric_id == spec.metric_id)
            .values(**values)
        )
    else:
        await conn.execute(certified_metrics.insert().values(**values))

    version_id = f"{spec.metric_id}:v{spec.version}:{spec_hash[:8]}"
    ver_exists = (
        await conn.execute(
            select(metric_versions.c.version_id).where(metric_versions.c.version_id == version_id)
        )
    ).first()
    if not ver_exists:
        await conn.execute(
            metric_versions.insert().values(
                version_id=version_id,
                metric_id=spec.metric_id,
                version=spec.version,
                status=spec.status,
                spec_hash=spec_hash,
                spec_json=spec_json,
                approved_by=approved_by or (spec.owner if spec.status == "approved" else None),
                created_at=now_utc,
            )
        )

    await conn.execute(
        delete(metric_dimensions).where(metric_dimensions.c.metric_id == spec.metric_id)
    )
    for dim in spec.dimensions:
        col, allowed = DIMENSION_TO_COLUMN[dim]
        await conn.execute(
            metric_dimensions.insert().values(
                id=f"{spec.metric_id}:{dim}",
                metric_id=spec.metric_id,
                dimension_id=dim,
                source_column=col,
                allowed_values_json=json.dumps(allowed) if allowed else None,
            )
        )

    await conn.execute(delete(metric_sources).where(metric_sources.c.metric_id == spec.metric_id))
    for src in spec.sources:
        await conn.execute(
            metric_sources.insert().values(
                id=f"{spec.metric_id}:{src}",
                metric_id=spec.metric_id,
                source_name=src,
                reporting_view=SOURCE_TO_VIEW[src],
            )
        )

