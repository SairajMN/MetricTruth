from datetime import date
from decimal import Decimal
import pytest
from backend.agents.metric_resolver import MetricResolver
from backend.db import readonly_engine
from backend.query.plan_schema import Comparison, MetricQueryPlan, Period
from backend.query.query_executor import QueryExecutor
from backend.query.query_validator import QueryValidator
from backend.query.sql_compiler import SQLCompiler
from backend.verification.math_engine import calculate_cac
from backend.verification.result_validator import ResultValidator
from scripts.seed_database import seed_all


def test_calculate_cac_basic():
    assert calculate_cac(150000, 4000) == 37.50
    with pytest.raises(ValueError):
        calculate_cac(150000, 0)


@pytest.mark.asyncio
async def test_deterministic_cac_pipeline_without_llm():
    await seed_all(simulate_stale_hours=0, reset=True)

    resolver = MetricResolver()
    res = await resolver.resolve(
        requested_metric="paid_customer_acquisition_cost",
        question_text="Why did our paid CAC increase in November compared with October by campaign?",
        has_campaign_context=True,
    )
    assert res.status == "RESOLVED"
    assert res.metric_spec is not None

    plan = MetricQueryPlan(
        metric_id="paid_customer_acquisition_cost",
        period=Period(start_date=date(2026, 11, 1), end_date=date(2026, 11, 30)),
        comparison=Comparison(type="previous_month"),
        group_by=["campaign"],
        order_by=["spend_desc"],
        limit=10,
    )

    compiler = SQLCompiler()
    artifact = compiler.compile(plan, res.metric_spec, dialect_name=readonly_engine.dialect.name)

    validator = QueryValidator()
    val_report = validator.validate(plan, res.metric_spec, artifact)
    assert val_report.passed, f"Validation failed: {val_report.failed_reasons}"

    executor = QueryExecutor()
    exec_res = await executor.execute(artifact)
    assert exec_res.row_count == 3

    auditor = ResultValidator()
    bundle = await auditor.validate_results(exec_res.rows, res.metric_spec, artifact)

    assert bundle.overall_status == "VERIFIED"
    assert bundle.numerical.status == "PASSED"
    assert bundle.reconciliation.status == "PASSED"
    assert bundle.freshness.status == "PASSED"

    assert bundle.numerical.aggregate_current == Decimal("37.50")
    assert bundle.numerical.aggregate_previous == Decimal("30.00")
    assert bundle.numerical.aggregate_pct_change == Decimal("25.00")

    by_campaign = {r.dimension_key: r for r in bundle.numerical.rows}
    assert by_campaign["Search"].previous_value == Decimal("24.00")
    assert by_campaign["Search"].current_value == Decimal("36.00")
    assert by_campaign["Search"].pct_change == Decimal("50.00")
    assert by_campaign["Search"].previous_drivers.cpc == Decimal("1.50")
    assert by_campaign["Search"].current_drivers.cpc == Decimal("2.25")
    assert by_campaign["Search"].current_drivers.cvr_pct == Decimal("6.25")

    assert by_campaign["Social"].previous_value == Decimal("40.00")
    assert by_campaign["Social"].current_value == Decimal("42.00")
    assert by_campaign["Social"].pct_change == Decimal("5.00")

    assert by_campaign["Affiliate"].previous_value == Decimal("40.00")
    assert by_campaign["Affiliate"].current_value == Decimal("36.00")
    assert by_campaign["Affiliate"].pct_change == Decimal("-10.00")

