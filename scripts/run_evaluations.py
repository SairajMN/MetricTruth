import asyncio
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "apps" / "api"))

from evals.graders.pipeline_grader import run_golden_evaluation_suite, write_golden_dataset
from scripts.seed_database import seed_all


async def main() -> None:
    write_golden_dataset()
    await seed_all(simulate_stale_hours=0, reset=True)
    report = await run_golden_evaluation_suite()
    print(f"Evaluation Run: {report.eval_run_id}")
    print(f"Passed: {report.passed_cases}/{report.total_cases}")
    print(f"Metric Selection Accuracy: {report.metric_selection_accuracy * 100:.1f}%")
    print(f"Numerical Accuracy:        {report.numerical_accuracy * 100:.1f}%")
    print(f"Grounded Claim Rate:       {report.grounded_claim_rate * 100:.1f}%")
    print(f"Abstention Accuracy:       {report.abstention_accuracy * 100:.1f}%")
    print(f"Security Pass Rate:        {report.security_pass_rate * 100:.1f}%")
    print(f"Average Latency:           {report.avg_latency_ms:.2f} ms")

    failed = [c for c in report.cases if not c.passed]
    if failed:
        for f in failed:
            print(
                f"  FAILED {f.test_id}: expected=({f.expected_status}, {f.expected_metric}, {f.expected_result}) "
                f"actual=({f.actual_status}, {f.selected_metric}, {f.actual_result})"
            )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

