from datetime import date
import pytest
from sqlalchemy import text
from backend.agents.claim_validator import ClaimValidator
from backend.agents.insight_generator import (
    AnalyticalClaim,
    InvestigationReport,
    ReportSection,
)
from backend.db import get_readonly_connection, readonly_engine
from backend.query.plan_schema import Comparison, MetricQueryPlan, Period
from backend.query.query_validator import QueryValidator
from backend.query.sql_compiler import CompiledQueryArtifact
from backend.semantic.registry import MetricRegistryRepository
from backend.verification.result_validator import ResultValidator
from scripts.seed_database import seed_all


@pytest.mark.asyncio
async def test_readonly_database_blocks_writes_and_unauthorized_tables():
    await seed_all(simulate_stale_hours=0, reset=True)

    # 1. Direct write attempt on readonly_engine must be denied at DB driver level
    with pytest.raises(Exception):
        async with get_readonly_connection(readonly_engine) as conn:
            await conn.execute(text("DELETE FROM campaigns"))

    # 2. Reading audit_events directly on readonly_engine must be denied by authorizer/role
    with pytest.raises(Exception):
        async with get_readonly_connection(readonly_engine) as conn:
            await conn.execute(text("SELECT * FROM audit_events"))

    # 3. Reading non-view table directly without going through v_* reporting view must be denied
    with pytest.raises(Exception):
        async with get_readonly_connection(readonly_engine) as conn:
            await conn.execute(text("SELECT * FROM customer_acquisitions"))


@pytest.mark.asyncio
async def test_sqlglot_query_validator_blocks_malicious_ast():
    await seed_all(simulate_stale_hours=0, reset=True)
    repo = MetricRegistryRepository()
    spec = await repo.get_metric("paid_customer_acquisition_cost")
    assert spec is not None

    plan = MetricQueryPlan(
        metric_id="paid_customer_acquisition_cost",
        period=Period(start_date=date(2026, 11, 1), end_date=date(2026, 11, 30)),
        comparison=Comparison(type="none"),
        group_by=["campaign"],
    )
    validator = QueryValidator()

    for bad_sql in (
        "SELECT * FROM patient_records LIMIT 10",
        "SELECT * FROM v_campaigns; DROP TABLE campaigns",
        "DELETE FROM v_campaigns WHERE campaign_id = 'CMP_001'",
        "SELECT pg_sleep(10) FROM v_campaigns LIMIT 1",
    ):
        tampered_artifact = CompiledQueryArtifact(
            metric_id=spec.metric_id,
            metric_version=spec.version,
            sql_text=bad_sql,
            display_sql=bad_sql,
            bound_params={"cur_start_date": "2026-11-01"},
            tables_accessed=["v_campaigns"],
            approved_joins=[],
            query_fingerprint="sha256:tampered",
            current_period=plan.period,
            comparison_period=None,
        )
        rep = validator.validate(plan, spec, tampered_artifact)
        assert not rep.passed, f"Expected malicious SQL to be blocked: {bad_sql}"


@pytest.mark.asyncio
async def test_claim_validator_strips_competitor_bidding_hallucination():
    await seed_all(simulate_stale_hours=0, reset=True)
    repo = MetricRegistryRepository()
    spec = await repo.get_metric("paid_customer_acquisition_cost")
    assert spec is not None

    auditor = ResultValidator()
    raw_rows = [
        {
            "dimension_key": "Search",
            "channel": "SEARCH",
            "cur_spend_usd": 90000,
            "cur_clicks": 40000,
            "cur_impressions": 800000,
            "cur_new_customers": 2500,
            "cur_revenue_usd": 900000,
            "cur_numerator": 90000,
            "cur_denominator": 2500,
            "cur_metric_value": 36.0,
            "prev_spend_usd": 60000,
            "prev_clicks": 40000,
            "prev_impressions": 800000,
            "prev_new_customers": 2500,
            "prev_revenue_usd": 850000,
            "prev_numerator": 60000,
            "prev_denominator": 2500,
            "prev_metric_value": 24.0,
        }
    ]
    fake_art = CompiledQueryArtifact(
        metric_id=spec.metric_id,
        metric_version=spec.version,
        sql_text="SELECT 1",
        display_sql="SELECT 1",
        bound_params={},
        tables_accessed=["v_campaigns"],
        approved_joins=[],
        query_fingerprint="sha256:test",
        current_period=Period(start_date=date(2026, 11, 1), end_date=date(2026, 11, 30)),
        comparison_period=Period(start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)),
    )
    bundle = await auditor.validate_results(raw_rows, spec, fake_art)

    draft = InvestigationReport(
        title="CAC Investigation",
        overall_finding="Search CAC rose 50%.",
        executive_summary="Summary.",
        certification_status="CERTIFIED",
        certification_banner="Banner",
        sections=[
            ReportSection(
                heading="1. Search",
                body="Search CAC rose from $24.00 to $36.00. Competitors raised their bidding budgets in November.",
            )
        ],
        claims=[
            AnalyticalClaim(
                claim_id="CLM_1",
                claim_type="NUMERICAL",
                statement="Search CAC rose from $24.00 to $36.00 (+50.00%).",
                referenced_numbers=[24.0, 36.0, 50.0],
                evidence_source="row:Search",
            ),
            AnalyticalClaim(
                claim_id="CLM_2",
                claim_type="CAUSAL_EXPLANATION",
                statement="Search CAC increased because competitors raised their bidding budgets.",
                referenced_numbers=[],
                evidence_source="model_guess",
            ),
        ],
    )

    cv = ClaimValidator()
    cleaned = cv.validate_and_sanitize(draft, bundle)
    assert len(cleaned.claims) == 1
    assert len(cleaned.stripped_claims) == 1
    assert "competitors" in cleaned.stripped_claims[0].original_statement.lower()
    assert "competitors" not in cleaned.sections[0].body.lower()

