from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.db import app_engine
from backend.models.tables import data_source_runs
from backend.semantic.models import CertifiedMetricSpec


class SourceFreshnessStatus(BaseModel):
    source_name: str
    batch_id: str | None
    last_updated: datetime | None
    age_hours: float | None
    max_allowed_hours: int
    is_fresh: bool


class FreshnessReport(BaseModel):
    status: Literal["PASSED", "WARNING_STALE_DATA", "FAILED_MISSING_SOURCE"]
    certified_for_current_reporting: bool
    sources: list[SourceFreshnessStatus] = Field(default_factory=list)
    warning_message: str | None = None


class FreshnessAuditor:
    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or app_engine

    async def check_freshness(
        self, spec: CertifiedMetricSpec, now_override: datetime | None = None
    ) -> FreshnessReport:
        now_utc = now_override or datetime.now(timezone.utc).replace(tzinfo=None)
        max_hours = spec.freshness.maximum_age_hours
        source_statuses: list[SourceFreshnessStatus] = []
        stale_messages: list[str] = []
        missing_sources: list[str] = []

        async with self._engine.connect() as conn:
            for src in spec.sources:
                stmt = (
                    select(
                        data_source_runs.c.batch_id,
                        data_source_runs.c.freshness_watermark,
                    )
                    .where(data_source_runs.c.source_name == src)
                    .order_by(data_source_runs.c.uploaded_at.desc())
                    .limit(1)
                )
                row = (await conn.execute(stmt)).first()
                if not row or row[1] is None:
                    missing_sources.append(src)
                    source_statuses.append(
                        SourceFreshnessStatus(
                            source_name=src,
                            batch_id=None,
                            last_updated=None,
                            age_hours=None,
                            max_allowed_hours=max_hours,
                            is_fresh=False,
                        )
                    )
                    continue

                batch_id, wm = str(row[0]), row[1]
                age_hours = round(max(0.0, (now_utc - wm).total_seconds() / 3600.0), 1)
                fresh = age_hours <= float(max_hours)
                if not fresh:
                    stale_messages.append(
                        f"{src}: Last updated {age_hours:.0f} hours ago. Required freshness: {max_hours} hours."
                    )
                source_statuses.append(
                    SourceFreshnessStatus(
                        source_name=src,
                        batch_id=batch_id,
                        last_updated=wm,
                        age_hours=age_hours,
                        max_allowed_hours=max_hours,
                        is_fresh=fresh,
                    )
                )

        if missing_sources:
            return FreshnessReport(
                status="FAILED_MISSING_SOURCE",
                certified_for_current_reporting=False,
                sources=source_statuses,
                warning_message=f"Required data sources have not arrived: {missing_sources}",
            )

        if stale_messages:
            return FreshnessReport(
                status="WARNING_STALE_DATA",
                certified_for_current_reporting=False,
                sources=source_statuses,
                warning_message=(
                    "WARNING: DATA FRESHNESS FAILURE — "
                    + " ".join(stale_messages)
                    + " Result: NOT CERTIFIED FOR CURRENT-PERIOD REPORTING."
                ),
            )

        return FreshnessReport(
            status="PASSED",
            certified_for_current_reporting=True,
            sources=source_statuses,
            warning_message=None,
        )

