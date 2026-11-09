import argparse
import asyncio
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "apps" / "api"))

from backend.data.ingestion import ingest_csv_bytes
from backend.db import app_engine
from backend.models.tables import init_schema


async def _run(source: str, file_path: Path) -> None:
    await init_schema(app_engine)
    summary = await ingest_csv_bytes(
        source_name=source,
        file_name=file_path.name,
        content=file_path.read_bytes(),
        engine=app_engine,
    )
    print(summary.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a CSV file into MetricTruth.")
    parser.add_argument("--source", required=True, help="Target dataset name")
    parser.add_argument("--file", required=True, type=Path, help="Path to CSV file")
    args = parser.parse_args()
    asyncio.run(_run(args.source, args.file))


if __name__ == "__main__":
    main()

