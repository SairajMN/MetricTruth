from pydantic import BaseModel
from backend.semantic.models import CertifiedMetricSpec


class JoinRelationship(BaseModel):
    left_view: str
    right_view: str
    join_keys: list[str]
    join_strategy: str


class CuratedSchemaContext(BaseModel):
    metric_id: str
    reporting_views: list[str]
    columns_by_view: dict[str, list[str]]
    approved_joins: list[JoinRelationship]
    grain: str
    allowed_dimensions: list[str]
    required_exclusions: list[str]


VIEW_COLUMNS: dict[str, list[str]] = {
    "v_campaigns": ["campaign_id", "campaign_name", "channel", "campaign_status", "created_at"],
    "v_daily_campaign_performance": [
        "id",
        "campaign_id",
        "report_date",
        "impressions",
        "clicks",
        "spend_usd",
        "source_batch_id",
    ],
    "v_customer_acquisitions": [
        "acquisition_id",
        "customer_id",
        "campaign_id",
        "acquired_at",
        "attribution_model",
        "is_valid",
        "first_order_revenue_usd",
        "source_batch_id",
    ],
    "v_operating_expenses": [
        "expense_id",
        "report_date",
        "category",
        "amount_usd",
        "source_batch_id",
    ],
}

SOURCE_VIEW_MAP = {
    "campaigns": "v_campaigns",
    "daily_campaign_performance": "v_daily_campaign_performance",
    "customer_acquisitions": "v_customer_acquisitions",
    "operating_expenses_monthly": "v_operating_expenses",
}


def build_curated_schema_context(spec: CertifiedMetricSpec) -> CuratedSchemaContext:
    views = [SOURCE_VIEW_MAP[s] for s in spec.sources if s in SOURCE_VIEW_MAP]
    cols = {v: VIEW_COLUMNS[v] for v in views}
    joins: list[JoinRelationship] = []
    if "v_daily_campaign_performance" in views and "v_campaigns" in views:
        joins.append(
            JoinRelationship(
                left_view="v_daily_campaign_performance",
                right_view="v_campaigns",
                join_keys=["campaign_id"],
                join_strategy="pre_aggregated_cte_join",
            )
        )
    if "v_customer_acquisitions" in views and "v_daily_campaign_performance" in views:
        joins.append(
            JoinRelationship(
                left_view="spend_cte",
                right_view="acquisitions_cte",
                join_keys=["campaign_id", "period_bucket"],
                join_strategy="independent_grain_aligned_cte_left_join",
            )
        )
    return CuratedSchemaContext(
        metric_id=spec.metric_id,
        reporting_views=views,
        columns_by_view=cols,
        approved_joins=joins,
        grain=spec.grain,
        allowed_dimensions=list(spec.dimensions),
        required_exclusions=list(spec.exclusions),
    )

