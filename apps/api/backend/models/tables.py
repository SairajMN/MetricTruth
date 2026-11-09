from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.ext.asyncio import AsyncEngine

metadata = MetaData()

campaigns = Table(
    "campaigns",
    metadata,
    Column("campaign_id", String(64), primary_key=True),
    Column("campaign_name", Text, nullable=False),
    Column("channel", String(64), nullable=False),
    Column("campaign_status", String(32), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

daily_campaign_performance = Table(
    "daily_campaign_performance",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("campaign_id", String(64), nullable=False, index=True),
    Column("report_date", Date, nullable=False, index=True),
    Column("impressions", Integer, nullable=False),
    Column("clicks", Integer, nullable=False),
    Column("spend_usd", Numeric(12, 2), nullable=False),
    Column("source_batch_id", String(64), nullable=False, index=True),
)

customer_acquisitions = Table(
    "customer_acquisitions",
    metadata,
    Column("acquisition_id", String(64), primary_key=True),
    Column("customer_id", String(64), nullable=False, index=True),
    Column("campaign_id", String(64), nullable=False, index=True),
    Column("acquired_at", DateTime, nullable=False, index=True),
    Column("attribution_model", String(64), nullable=False),
    Column("is_valid", Boolean, nullable=False),
    Column("first_order_revenue_usd", Numeric(12, 2), nullable=False, server_default="0"),
    Column("source_batch_id", String(64), nullable=False, index=True),
)

operating_expenses_monthly = Table(
    "operating_expenses_monthly",
    metadata,
    Column("expense_id", String(64), primary_key=True),
    Column("report_date", Date, nullable=False, index=True),
    Column("category", String(64), nullable=False),
    Column("amount_usd", Numeric(12, 2), nullable=False),
    Column("source_batch_id", String(64), nullable=False),
)

certified_metrics = Table(
    "certified_metrics",
    metadata,
    Column("metric_id", String(128), primary_key=True),
    Column("name", String(256), nullable=False),
    Column("description", Text, nullable=False),
    Column("formula_json", Text, nullable=False),
    Column("numerator", String(128), nullable=False),
    Column("denominator", String(128), nullable=False),
    Column("aggregation", String(64), nullable=False),
    Column("unit", String(32), nullable=False),
    Column("grain", String(64), nullable=False),
    Column("attribution_json", Text, nullable=False),
    Column("time_dimension", String(64), nullable=False),
    Column("timezone", String(64), nullable=False),
    Column("owner", String(128), nullable=False),
    Column("freshness_max_age_hours", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("spec_json", Text, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

metric_versions = Table(
    "metric_versions",
    metadata,
    Column("version_id", String(128), primary_key=True),
    Column("metric_id", String(128), nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("spec_hash", String(64), nullable=False),
    Column("spec_json", Text, nullable=False),
    Column("approved_by", String(128), nullable=True),
    Column("created_at", DateTime, nullable=False),
)

metric_dimensions = Table(
    "metric_dimensions",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("metric_id", String(128), nullable=False, index=True),
    Column("dimension_id", String(64), nullable=False),
    Column("source_column", String(128), nullable=False),
    Column("allowed_values_json", Text, nullable=True),
)

metric_sources = Table(
    "metric_sources",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("metric_id", String(128), nullable=False, index=True),
    Column("source_name", String(128), nullable=False),
    Column("reporting_view", String(128), nullable=False),
)

data_source_runs = Table(
    "data_source_runs",
    metadata,
    Column("batch_id", String(64), primary_key=True),
    Column("source_name", String(128), nullable=False, index=True),
    Column("file_name", String(256), nullable=False),
    Column("uploaded_at", DateTime, nullable=False),
    Column("total_rows", Integer, nullable=False),
    Column("accepted_rows", Integer, nullable=False),
    Column("rejected_rows", Integer, nullable=False),
    Column("duplicate_rows", Integer, nullable=False),
    Column("validation_failures_json", Text, nullable=False),
    Column("freshness_watermark", DateTime, nullable=False),
    Column("status", String(32), nullable=False),
)

data_quality_results = Table(
    "data_quality_results",
    metadata,
    Column("check_id", String(64), primary_key=True),
    Column("batch_id", String(64), nullable=False, index=True),
    Column("source_name", String(128), nullable=False),
    Column("rule_name", String(128), nullable=False),
    Column("passed", Boolean, nullable=False),
    Column("failed_rows", Integer, nullable=False),
    Column("details", Text, nullable=False),
    Column("checked_at", DateTime, nullable=False),
)

query_runs = Table(
    "query_runs",
    metadata,
    Column("query_run_id", String(64), primary_key=True),
    Column("agent_run_id", String(64), nullable=False, index=True),
    Column("metric_id", String(128), nullable=False),
    Column("metric_version", Integer, nullable=False),
    Column("data_sources_json", Text, nullable=False),
    Column("source_batch_ids_json", Text, nullable=False),
    Column("compiled_sql", Text, nullable=False),
    Column("bound_params_json", Text, nullable=False),
    Column("query_fingerprint", String(128), nullable=False, index=True),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("execution_ms", Numeric(10, 2), nullable=False),
    Column("validation_status", String(32), nullable=False),
    Column("result_validation", String(32), nullable=False),
    Column("data_freshness", String(32), nullable=False),
    Column("execution_status", String(32), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

query_plans = Table(
    "query_plans",
    metadata,
    Column("plan_id", String(64), primary_key=True),
    Column("agent_run_id", String(64), nullable=False, index=True),
    Column("metric_id", String(128), nullable=False),
    Column("plan_json", Text, nullable=False),
    Column("is_valid", Boolean, nullable=False),
    Column("validation_errors_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

query_evidence = Table(
    "query_evidence",
    metadata,
    Column("evidence_id", String(64), primary_key=True),
    Column("query_run_id", String(64), nullable=False, index=True),
    Column("agent_run_id", String(64), nullable=False, index=True),
    Column("rows_json", Text, nullable=False),
    Column("audit_bundle_json", Text, nullable=False),
    Column("reconciliation_json", Text, nullable=False),
    Column("freshness_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

agent_runs = Table(
    "agent_runs",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("question", Text, nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("selected_metric_id", String(128), nullable=True),
    Column("metric_version", Integer, nullable=True),
    Column("current_stage", String(64), nullable=False),
    Column("report_json", Text, nullable=True),
    Column("clarification_json", Text, nullable=True),
    Column("failure_reason", Text, nullable=True),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("cached_tokens", Integer, nullable=False, server_default="0"),
    Column("model_calls", Integer, nullable=False, server_default="0"),
    Column("retries", Integer, nullable=False, server_default="0"),
    Column("total_cost_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("duration_ms", Numeric(10, 2), nullable=False, server_default="0"),
    Column("created_at", DateTime, nullable=False),
    Column("completed_at", DateTime, nullable=True),
)

agent_events = Table(
    "agent_events",
    metadata,
    Column("event_id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False, index=True),
    Column("sequence", Integer, nullable=False),
    Column("component", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("duration_ms", Numeric(10, 2), nullable=False),
    Column("details_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

tool_invocations = Table(
    "tool_invocations",
    metadata,
    Column("invocation_id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False, index=True),
    Column("tool_name", String(64), nullable=False),
    Column("model_name", String(128), nullable=True),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("cached_tokens", Integer, nullable=False, server_default="0"),
    Column("cost_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("duration_ms", Numeric(10, 2), nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

evaluation_runs = Table(
    "evaluation_runs",
    metadata,
    Column("eval_run_id", String(64), primary_key=True),
    Column("total_cases", Integer, nullable=False),
    Column("passed_cases", Integer, nullable=False),
    Column("intent_accuracy", Numeric(6, 4), nullable=False),
    Column("metric_selection_accuracy", Numeric(6, 4), nullable=False),
    Column("plan_validity_rate", Numeric(6, 4), nullable=False),
    Column("execution_accuracy", Numeric(6, 4), nullable=False),
    Column("numerical_accuracy", Numeric(6, 4), nullable=False),
    Column("grounded_claim_rate", Numeric(6, 4), nullable=False),
    Column("abstention_accuracy", Numeric(6, 4), nullable=False),
    Column("security_pass_rate", Numeric(6, 4), nullable=False),
    Column("avg_latency_ms", Numeric(10, 2), nullable=False),
    Column("total_cost_usd", Numeric(12, 6), nullable=False),
    Column("results_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("audit_id", String(64), primary_key=True),
    Column("actor_role", String(64), nullable=False),
    Column("event_type", String(64), nullable=False, index=True),
    Column("severity", String(32), nullable=False),
    Column("resource", String(128), nullable=False),
    Column("details_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)


REPORTING_VIEW_DDLS = [
    (
        "v_campaigns",
        "SELECT campaign_id, campaign_name, channel, campaign_status, created_at FROM campaigns",
    ),
    (
        "v_daily_campaign_performance",
        "SELECT id, campaign_id, report_date, impressions, clicks, spend_usd, source_batch_id FROM daily_campaign_performance",
    ),
    (
        "v_customer_acquisitions",
        "SELECT acquisition_id, customer_id, campaign_id, acquired_at, attribution_model, is_valid, first_order_revenue_usd, source_batch_id FROM customer_acquisitions",
    ),
    (
        "v_operating_expenses",
        "SELECT expense_id, report_date, category, amount_usd, source_batch_id FROM operating_expenses_monthly",
    ),
]


async def init_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        is_pg = engine.dialect.name == "postgresql"
        for view_name, select_sql in REPORTING_VIEW_DDLS:
            if is_pg:
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS reporting"))
                await conn.execute(text(f"CREATE OR REPLACE VIEW reporting.{view_name} AS {select_sql}"))
                await conn.execute(text(f"CREATE OR REPLACE VIEW {view_name} AS {select_sql}"))
            else:
                await conn.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
                await conn.execute(text(f"CREATE VIEW {view_name} AS {select_sql}"))
