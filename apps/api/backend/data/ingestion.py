import csv
from datetime import datetime, timezone
import io
import json
from typing import Any
import uuid
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.data.normalizer import normalize_row
from backend.data.quality import PRIMARY_KEY_COLUMN, REQUIRED_COLUMNS, validate_row_quality
from backend.db import app_engine
from backend.models.tables import (
    campaigns,
    customer_acquisitions,
    daily_campaign_performance,
    data_quality_results,
    data_source_runs,
    operating_expenses_monthly,
)

MAX_CSV_BYTES = 10 * 1024 * 1024

SOURCE_TABLES = {
    "campaigns": campaigns,
    "daily_campaign_performance": daily_campaign_performance,
    "customer_acquisitions": customer_acquisitions,
    "operating_expenses_monthly": operating_expenses_monthly,
}


class IngestionSummary(BaseModel):
    batch_id: str
    source_name: str
    file_name: str
    uploaded_at: datetime
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    duplicate_rows: int
    validation_failures: list[str]
    freshness_watermark: datetime
    status: str


async def ingest_csv_bytes(
    source_name: str,
    file_name: str,
    content: bytes,
    engine: AsyncEngine | None = None,
    watermark_override: datetime | None = None,
) -> IngestionSummary:
    if source_name not in SOURCE_TABLES:
        raise ValueError(f"Unknown source_name: {source_name}")
    if len(content) == 0:
        raise ValueError("Uploaded CSV file is empty.")
    if len(content) > MAX_CSV_BYTES:
        raise ValueError(f"CSV file exceeds maximum size of {MAX_CSV_BYTES} bytes.")

    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file must be valid UTF-8.") from exc

    reader = csv.DictReader(io.StringIO(text_content))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row.")

    missing_cols = [c for c in REQUIRED_COLUMNS[source_name] if c not in reader.fieldnames]
    if missing_cols:
        raise ValueError(f"Missing required columns for {source_name}: {missing_cols}")

    target_engine = engine or app_engine
    table = SOURCE_TABLES[source_name]
    pk_col = PRIMARY_KEY_COLUMN[source_name]
    batch_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    watermark = watermark_override or now_utc

    async with target_engine.begin() as conn:
        existing_res = await conn.execute(select(table.c[pk_col]))
        existing_pks = {str(r[0]) for r in existing_res.fetchall()}

        seen_in_file: set[str] = set()
        accepted: list[dict[str, Any]] = []
        failures: list[str] = []
        rule_failure_counts = {"type_normalization": 0, "business_quality": 0, "duplicate_pk": 0}
        total_rows = 0
        duplicate_rows = 0
        rejected_rows = 0

        for idx, raw_row in enumerate(reader, start=1):
            total_rows += 1
            try:
                norm = normalize_row(source_name, raw_row, batch_id)
            except Exception as exc:
                rejected_rows += 1
                rule_failure_counts["type_normalization"] += 1
                if len(failures) < 50:
                    failures.append(f"row {idx}: type error ({exc})")
                continue

            pk_val = str(norm[pk_col])
            if pk_val in seen_in_file or pk_val in existing_pks:
                duplicate_rows += 1
                rule_failure_counts["duplicate_pk"] += 1
                continue

            row_errors = validate_row_quality(source_name, norm)
            if row_errors:
                rejected_rows += 1
                rule_failure_counts["business_quality"] += 1
                if len(failures) < 50:
                    failures.append(f"row {idx}: {', '.join(row_errors)}")
                continue

            seen_in_file.add(pk_val)
            accepted.append(norm)

        if accepted:
            for chunk_start in range(0, len(accepted), 500):
                await conn.execute(table.insert(), accepted[chunk_start : chunk_start + 500])

        status = "COMPLETED" if accepted or duplicate_rows == total_rows else "FAILED"
        await conn.execute(
            data_source_runs.insert().values(
                batch_id=batch_id,
                source_name=source_name,
                file_name=file_name,
                uploaded_at=now_utc,
                total_rows=total_rows,
                accepted_rows=len(accepted),
                rejected_rows=rejected_rows,
                duplicate_rows=duplicate_rows,
                validation_failures_json=json.dumps(failures),
                freshness_watermark=watermark,
                status=status,
            )
        )

        for rule_name, failed_count in rule_failure_counts.items():
            await conn.execute(
                data_quality_results.insert().values(
                    check_id=str(uuid.uuid4()),
                    batch_id=batch_id,
                    source_name=source_name,
                    rule_name=rule_name,
                    passed=(failed_count == 0),
                    failed_rows=failed_count,
                    details=f"{failed_count} rows triggered {rule_name}",
                    checked_at=now_utc,
                )
            )

    return IngestionSummary(
        batch_id=batch_id,
        source_name=source_name,
        file_name=file_name,
        uploaded_at=now_utc,
        total_rows=total_rows,
        accepted_rows=len(accepted),
        rejected_rows=rejected_rows,
        duplicate_rows=duplicate_rows,
        validation_failures=failures,
        freshness_watermark=watermark,
        status=status,
    )

