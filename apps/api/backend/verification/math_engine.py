from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


class DriverDecomposition(BaseModel):
    spend_usd: Decimal
    clicks: int
    impressions: int
    new_customers: int
    cpc: Decimal | None
    ctr_pct: Decimal | None
    cvr_pct: Decimal | None
    cac: Decimal | None
    identity_verified: bool


def calculate_cac(total_spend: float | Decimal, new_customers: int) -> float:
    if new_customers <= 0:
        raise ValueError("CAC cannot be calculated without new customers.")
    res = Decimal(str(total_spend)) / Decimal(int(new_customers))
    return float(res.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def compute_metric_decimal(
    numerator: Decimal | int | float,
    denominator: Decimal | int | float,
    aggregation: Literal["ratio", "percentage"] = "ratio",
) -> Decimal | None:
    num = Decimal(str(numerator))
    den = Decimal(str(denominator))
    if den <= Decimal("0"):
        return None
    raw = (num / den) * (Decimal("100") if aggregation == "percentage" else Decimal("1"))
    return raw.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_period_delta(
    current_val: Decimal | None, previous_val: Decimal | None
) -> tuple[Decimal | None, Decimal | None]:
    if current_val is None or previous_val is None:
        return None, None
    abs_change = (current_val - previous_val).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if previous_val == Decimal("0"):
        return abs_change, None
    pct_change = (((current_val - previous_val) / previous_val) * Decimal("100")).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    return abs_change, pct_change


def compute_cac_drivers(
    spend_usd: Decimal, clicks: int, impressions: int, new_customers: int
) -> DriverDecomposition:
    cpc = compute_metric_decimal(spend_usd, clicks, "ratio")
    ctr_pct = compute_metric_decimal(clicks, impressions, "percentage")
    cvr_pct = compute_metric_decimal(new_customers, clicks, "percentage")
    cac = compute_metric_decimal(spend_usd, new_customers, "ratio")

    identity_ok = True
    if cac is not None and cpc is not None and cvr_pct is not None and cvr_pct > Decimal("0"):
        raw_cpc = Decimal(str(spend_usd)) / Decimal(clicks)
        raw_cvr = Decimal(new_customers) / Decimal(clicks)
        derived_cac = (raw_cpc / raw_cvr).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        identity_ok = abs(derived_cac - cac) <= Decimal("0.02")

    return DriverDecomposition(
        spend_usd=spend_usd.quantize(TWO_PLACES),
        clicks=clicks,
        impressions=impressions,
        new_customers=new_customers,
        cpc=cpc,
        ctr_pct=ctr_pct,
        cvr_pct=cvr_pct,
        cac=cac,
        identity_verified=identity_ok,
    )

