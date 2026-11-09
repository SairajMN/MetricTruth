from decimal import Decimal
from typing import Any, Literal
from pydantic import BaseModel, Field
from backend.semantic.models import CertifiedMetricSpec
from backend.verification.math_engine import (
    DriverDecomposition,
    compute_cac_drivers,
    compute_metric_decimal,
    compute_period_delta,
)


class VerifiedBreakdownRow(BaseModel):
    dimension_key: str
    channel: str
    current_value: Decimal | None
    current_display: str
    previous_value: Decimal | None
    previous_display: str
    absolute_change: Decimal | None
    pct_change: Decimal | None
    cur_numerator: Decimal
    cur_denominator: Decimal
    prev_numerator: Decimal
    prev_denominator: Decimal
    cur_spend_usd: Decimal
    prev_spend_usd: Decimal
    spend_change_pct: Decimal | None
    cur_new_customers: int
    prev_new_customers: int
    customer_change_pct: Decimal | None
    cur_clicks: int
    prev_clicks: int
    cur_impressions: int
    prev_impressions: int
    cur_revenue_usd: Decimal
    prev_revenue_usd: Decimal
    current_drivers: DriverDecomposition
    previous_drivers: DriverDecomposition
    sql_matched_audit: bool


class NumericalAuditReport(BaseModel):
    status: Literal["PASSED", "FAILED"]
    aggregate_current: Decimal | None
    aggregate_current_display: str
    aggregate_previous: Decimal | None
    aggregate_previous_display: str
    aggregate_abs_change: Decimal | None
    aggregate_pct_change: Decimal | None
    aggregate_cur_spend: Decimal
    aggregate_prev_spend: Decimal
    aggregate_cur_customers: int
    aggregate_prev_customers: int
    aggregate_cur_clicks: int
    aggregate_prev_clicks: int
    aggregate_cur_impressions: int
    aggregate_prev_impressions: int
    aggregate_cur_revenue: Decimal
    aggregate_prev_revenue: Decimal
    aggregate_current_drivers: DriverDecomposition
    aggregate_previous_drivers: DriverDecomposition
    rows: list[VerifiedBreakdownRow] = Field(default_factory=list)
    undefined_rows: list[str] = Field(default_factory=list)
    discrepancies: list[str] = Field(default_factory=list)


def _fmt_metric(val: Decimal | None, unit: str, den: Decimal) -> str:
    if val is None or den <= Decimal("0"):
        return "N/A — no attributed customers" if unit == "USD" else "N/A — zero denominator"
    if unit == "USD":
        return f"${val:,.2f}"
    if unit == "PERCENT":
        return f"{val:.2f}%"
    if unit == "RATIO":
        return f"{val:.2f}x"
    return f"{val:,.2f}"


class NumericalAuditor:
    def audit(
        self, raw_rows: list[dict[str, Any]], spec: CertifiedMetricSpec
    ) -> NumericalAuditReport:
        agg_type = spec.formula.aggregation
        discrepancies: list[str] = []
        undefined_rows: list[str] = []
        verified_rows: list[VerifiedBreakdownRow] = []

        tot_cur_num = Decimal("0")
        tot_cur_den = Decimal("0")
        tot_prev_num = Decimal("0")
        tot_prev_den = Decimal("0")
        tot_cur_spend = Decimal("0")
        tot_prev_spend = Decimal("0")
        tot_cur_cust = 0
        tot_prev_cust = 0
        tot_cur_clicks = 0
        tot_prev_clicks = 0
        tot_cur_imp = 0
        tot_prev_imp = 0
        tot_cur_rev = Decimal("0")
        tot_prev_rev = Decimal("0")

        for r in raw_rows:
            dim_key = str(r["dimension_key"])
            channel = str(r.get("channel") or "ALL")

            cur_num = Decimal(str(r["cur_numerator"] or 0))
            cur_den = Decimal(str(r["cur_denominator"] or 0))
            prev_num = Decimal(str(r["prev_numerator"] or 0))
            prev_den = Decimal(str(r["prev_denominator"] or 0))

            cur_spend = Decimal(str(r["cur_spend_usd"] or 0)).quantize(Decimal("0.01"))
            prev_spend = Decimal(str(r["prev_spend_usd"] or 0)).quantize(Decimal("0.01"))
            cur_cust = int(r["cur_new_customers"] or 0)
            prev_cust = int(r["prev_new_customers"] or 0)
            cur_clicks = int(r["cur_clicks"] or 0)
            prev_clicks = int(r["prev_clicks"] or 0)
            cur_imp = int(r["cur_impressions"] or 0)
            prev_imp = int(r["prev_impressions"] or 0)
            cur_rev = Decimal(str(r["cur_revenue_usd"] or 0)).quantize(Decimal("0.01"))
            prev_rev = Decimal(str(r["prev_revenue_usd"] or 0)).quantize(Decimal("0.01"))

            tot_cur_num += cur_num
            tot_cur_den += cur_den
            tot_prev_num += prev_num
            tot_prev_den += prev_den
            tot_cur_spend += cur_spend
            tot_prev_spend += prev_spend
            tot_cur_cust += cur_cust
            tot_prev_cust += prev_cust
            tot_cur_clicks += cur_clicks
            tot_prev_clicks += prev_clicks
            tot_cur_imp += cur_imp
            tot_prev_imp += prev_imp
            tot_cur_rev += cur_rev
            tot_prev_rev += prev_rev

            audit_cur = compute_metric_decimal(cur_num, cur_den, agg_type)
            audit_prev = compute_metric_decimal(prev_num, prev_den, agg_type)

            if audit_cur is None:
                undefined_rows.append(dim_key)

            sql_cur_raw = r.get("cur_metric_value")
            sql_matched = True
            if audit_cur is not None and sql_cur_raw is not None:
                sql_cur_dec = Decimal(str(round(float(sql_cur_raw), 2)))
                if abs(sql_cur_dec - audit_cur) > Decimal("0.02"):
                    sql_matched = False
                    discrepancies.append(
                        f"Row '{dim_key}' SQL value {sql_cur_dec} != audited value {audit_cur}"
                    )
            elif (audit_cur is None) != (sql_cur_raw is None):
                sql_matched = False
                discrepancies.append(f"Row '{dim_key}' NULL mismatch between SQL and auditor")

            abs_chg, pct_chg = compute_period_delta(audit_cur, audit_prev)
            _, spend_chg_pct = compute_period_delta(cur_spend, prev_spend)
            _, cust_chg_pct = compute_period_delta(Decimal(cur_cust), Decimal(prev_cust))

            cur_drivers = compute_cac_drivers(cur_spend, cur_clicks, cur_imp, cur_cust)
            prev_drivers = compute_cac_drivers(prev_spend, prev_clicks, prev_imp, prev_cust)

            verified_rows.append(
                VerifiedBreakdownRow(
                    dimension_key=dim_key,
                    channel=channel,
                    current_value=audit_cur,
                    current_display=_fmt_metric(audit_cur, spec.unit, cur_den),
                    previous_value=audit_prev,
                    previous_display=_fmt_metric(audit_prev, spec.unit, prev_den),
                    absolute_change=abs_chg,
                    pct_change=pct_chg,
                    cur_numerator=cur_num,
                    cur_denominator=cur_den,
                    prev_numerator=prev_num,
                    prev_denominator=prev_den,
                    cur_spend_usd=cur_spend,
                    prev_spend_usd=prev_spend,
                    spend_change_pct=spend_chg_pct,
                    cur_new_customers=cur_cust,
                    prev_new_customers=prev_cust,
                    customer_change_pct=cust_chg_pct,
                    cur_clicks=cur_clicks,
                    prev_clicks=prev_clicks,
                    cur_impressions=cur_imp,
                    prev_impressions=prev_imp,
                    cur_revenue_usd=cur_rev,
                    prev_revenue_usd=prev_rev,
                    current_drivers=cur_drivers,
                    previous_drivers=prev_drivers,
                    sql_matched_audit=sql_matched,
                )
            )

        agg_cur = compute_metric_decimal(tot_cur_num, tot_cur_den, agg_type)
        agg_prev = compute_metric_decimal(tot_prev_num, tot_prev_den, agg_type)
        agg_abs, agg_pct = compute_period_delta(agg_cur, agg_prev)

        return NumericalAuditReport(
            status="PASSED" if not discrepancies else "FAILED",
            aggregate_current=agg_cur,
            aggregate_current_display=_fmt_metric(agg_cur, spec.unit, tot_cur_den),
            aggregate_previous=agg_prev,
            aggregate_previous_display=_fmt_metric(agg_prev, spec.unit, tot_prev_den),
            aggregate_abs_change=agg_abs,
            aggregate_pct_change=agg_pct,
            aggregate_cur_spend=tot_cur_spend,
            aggregate_prev_spend=tot_prev_spend,
            aggregate_cur_customers=tot_cur_cust,
            aggregate_prev_customers=tot_prev_cust,
            aggregate_cur_clicks=tot_cur_clicks,
            aggregate_prev_clicks=tot_prev_clicks,
            aggregate_cur_impressions=tot_cur_imp,
            aggregate_prev_impressions=tot_prev_imp,
            aggregate_cur_revenue=tot_cur_rev,
            aggregate_prev_revenue=tot_prev_rev,
            aggregate_current_drivers=compute_cac_drivers(
                tot_cur_spend, tot_cur_clicks, tot_cur_imp, tot_cur_cust
            ),
            aggregate_previous_drivers=compute_cac_drivers(
                tot_prev_spend, tot_prev_clicks, tot_prev_imp, tot_prev_cust
            ),
            rows=verified_rows,
            undefined_rows=undefined_rows,
            discrepancies=discrepancies,
        )

