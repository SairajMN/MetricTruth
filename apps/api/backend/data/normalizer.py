from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_text(value: str) -> str:
    cleaned = CONTROL_CHAR_RE.sub("", value.strip())
    while cleaned.startswith(FORMULA_PREFIXES):
        cleaned = cleaned[1:].lstrip()
    return cleaned


def normalize_row(source_name: str, raw: dict[str, str], default_batch_id: str) -> dict[str, Any]:
    if source_name == "campaigns":
        return {
            "campaign_id": sanitize_text(raw["campaign_id"]),
            "campaign_name": sanitize_text(raw["campaign_name"]),
            "channel": sanitize_text(raw["channel"]).upper(),
            "campaign_status": sanitize_text(raw["campaign_status"]).upper(),
            "created_at": datetime.fromisoformat(raw["created_at"].strip()),
        }
    if source_name == "daily_campaign_performance":
        return {
            "id": sanitize_text(raw["id"]),
            "campaign_id": sanitize_text(raw["campaign_id"]),
            "report_date": date.fromisoformat(raw["report_date"].strip()),
            "impressions": int(raw["impressions"].strip()),
            "clicks": int(raw["clicks"].strip()),
            "spend_usd": _parse_decimal(raw["spend_usd"]),
            "source_batch_id": sanitize_text(raw.get("source_batch_id") or default_batch_id),
        }
    if source_name == "customer_acquisitions":
        return {
            "acquisition_id": sanitize_text(raw["acquisition_id"]),
            "customer_id": sanitize_text(raw["customer_id"]),
            "campaign_id": sanitize_text(raw["campaign_id"]),
            "acquired_at": datetime.fromisoformat(raw["acquired_at"].strip()),
            "attribution_model": sanitize_text(raw["attribution_model"]).lower(),
            "is_valid": _parse_bool(raw["is_valid"]),
            "first_order_revenue_usd": _parse_decimal(raw.get("first_order_revenue_usd", "0.00")),
            "source_batch_id": sanitize_text(raw.get("source_batch_id") or default_batch_id),
        }
    if source_name == "operating_expenses_monthly":
        return {
            "expense_id": sanitize_text(raw["expense_id"]),
            "report_date": date.fromisoformat(raw["report_date"].strip()),
            "category": sanitize_text(raw["category"]).upper(),
            "amount_usd": _parse_decimal(raw["amount_usd"]),
            "source_batch_id": sanitize_text(raw.get("source_batch_id") or default_batch_id),
        }
    raise ValueError(f"Unsupported data source: {source_name}")


def _parse_decimal(val: str) -> Decimal:
    try:
        return Decimal(val.strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Invalid decimal value: {val!r}") from exc


def _parse_bool(val: str) -> bool:
    norm = val.strip().lower()
    if norm in ("true", "1", "yes", "t"):
        return True
    if norm in ("false", "0", "no", "f"):
        return False
    raise ValueError(f"Invalid boolean value: {val!r}")

