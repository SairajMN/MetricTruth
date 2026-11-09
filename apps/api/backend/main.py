from contextlib import asynccontextmanager
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from backend.api.analytics import router as analytics_router
from backend.api.datasets import router as datasets_router
from backend.api.evaluations import router as evaluations_router
from backend.api.metrics import router as metrics_router
from backend.db import app_engine
from backend.models.tables import campaigns, init_schema
from scripts.seed_database import seed_all


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_schema(app_engine)
    async with app_engine.connect() as conn:
        count = (await conn.execute(select(func.count()).select_from(campaigns))).scalar_one()
    if count == 0:
        await seed_all(simulate_stale_hours=0, reset=False)
    yield


app = FastAPI(
    title="MetricTruth API",
    description="Certified-metric agentic business intelligence engine with deterministic SQL and independent result auditing.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)
app.include_router(metrics_router)
app.include_router(datasets_router)
app.include_router(evaluations_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

