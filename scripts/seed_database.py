import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "apps" / "api"))

from sqlalchemy import delete
from backend.data.ingestion import ingest_csv_bytes
from backend.db import app_engine
from backend.models.tables import (
    campaigns,
    customer_acquisitions,
    daily_campaign_performance,
    data_quality_results,
    data_source_runs,
    init_schema,
    operating_expenses_monthly,
)
from backend.semantic.metric_loader import sync_registry_to_db
from scripts.generate_synthetic_data import generate_all


async def seed_all(simulate_stale_hours: int = 0, reset: bool = True) -> dict:
    await init_schema(app_engine)
    if reset:
        async with app_engine.begin() as conn:
            for tbl in (
                data_quality_results,
                data_source_runs,
                customer_acquisitions,
                daily_campaign_performance,
                operating_expenses_monthly,
                campaigns,
            ):
                await conn.execute(delete(tbl))

    csv_paths = generate_all()
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    stale_wm = now_utc - timedelta(hours=simulate_stale_hours) if simulate_stale_hours > 0 else now_utc

    summaries = {}
    for source_name, path in csv_paths.items():
        wm = stale_wm if source_name == "daily_campaign_performance" else now_utc
        summary = await ingest_csv_bytes(
            source_name=source_name,
            file_name=path.name,
            content=path.read_bytes(),
            engine=app_engine,
            watermark_override=wm,
        )
        summaries[source_name] = summary.model_dump()

    metrics = await sync_registry_to_db(engine=app_engine)
    return {
        "ingested_sources": summaries,
        "synced_metrics": [m.metric_id for m in metrics],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MetricTruth database with synthetic data and registry.")
    parser.add_argument("--simulate-stale-hours", type=int, default=0)
    args = parser.parse_args()
    res = asyncio.run(seed_all(simulate_stale_hours=args.simulate_stale_hours))
    print(f"Seeded {len(res['ingested_sources'])} sources and {len(res['synced_metrics'])} metrics.")


if __name__ == "__main__":
    main()
