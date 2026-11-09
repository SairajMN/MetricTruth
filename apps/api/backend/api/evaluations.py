from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import APIRouter, Depends, HTTPException
from backend.security.auth import RoleType, require_analyst_or_admin
from evals.graders.pipeline_grader import (
    get_evaluation_run,
    list_evaluation_runs,
    load_golden_dataset,
    run_golden_evaluation_suite,
)

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.post("/run")
async def trigger_evaluation_run(
    _role: RoleType = Depends(require_analyst_or_admin),
) -> dict[str, Any]:
    report = await run_golden_evaluation_suite()
    return report.model_dump(mode="json")


@router.get("/results")
async def get_evaluation_results() -> dict[str, Any]:
    runs = await list_evaluation_runs(limit=10)
    latest_detail = None
    if runs:
        latest_detail = await get_evaluation_run(str(runs[0]["eval_run_id"]))
    scenarios = load_golden_dataset()
    return {
        "runs": runs,
        "latest": latest_detail.model_dump(mode="json") if latest_detail else None,
        "golden_dataset_size": len(scenarios),
    }


@router.get("/{run_id}")
async def get_single_evaluation_run(run_id: str) -> dict[str, Any]:
    report = await get_evaluation_run(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Evaluation run '{run_id}' not found.")
    return report.model_dump(mode="json")

