from decimal import Decimal
from typing import Any

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "campaigns": ("campaign_id", "campaign_name", "channel", "campaign_status", "created_at"),
    "daily_campaign_performance": ("id", "campaign_id", "report_date", "impressions", "clicks", "spend_usd"),
    "customer_acquisitions": (
        "acquisition_id",
        "customer_id",
        "campaign_id",
        "acquired_at",
        "attribution_model",
        "is_valid",
    ),
    "operating_expenses_monthly": ("expense_id", "report_date", "category", "amount_usd"),
}

PRIMARY_KEY_COLUMN: dict[str, str] = {
    "campaigns": "campaign_id",
    "daily_campaign_performance": "id",
    "customer_acquisitions": "acquisition_id",
    "operating_expenses_monthly": "expense_id",
}


def validate_row_quality(source_name: str, row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pk_col = PRIMARY_KEY_COLUMN[source_name]
    if not row.get(pk_col):
        errors.append(f"missing_primary_key:{pk_col}")

    if source_name == "campaigns":
        if not row.get("campaign_name"):
            errors.append("empty_campaign_name")
        if row.get("channel") not in {"SEARCH", "SOCIAL", "AFFILIATE", "DISPLAY", "EMAIL"}:
            errors.append(f"invalid_channel:{row.get('channel')}")
    elif source_name == "daily_campaign_performance":
        if row["impressions"] < 0:
            errors.append("negative_impressions")
        if row["clicks"] < 0:
            errors.append("negative_clicks")
        if row["clicks"] > row["impressions"]:
            errors.append("clicks_exceed_impressions")
        if row["spend_usd"] < Decimal("0"):
            errors.append("negative_spend")
    elif source_name == "customer_acquisitions":
        if not row.get("customer_id"):
            errors.append("missing_customer_id")
        if not row.get("campaign_id"):
            errors.append("missing_campaign_id")
        if row["first_order_revenue_usd"] < Decimal("0"):
            errors.append("negative_revenue")
    elif source_name == "operating_expenses_monthly":
        if row["amount_usd"] < Decimal("0"):
            errors.append("negative_expense_amount")

    return errors

