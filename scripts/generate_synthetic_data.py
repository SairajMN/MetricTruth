import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import uuid

ROOT_DIR = Path(__file__).resolve().parents[1]
SYNTHETIC_DIR = ROOT_DIR / "data" / "synthetic"

BATCH_CAMPAIGNS = "b0000001-0000-4000-8000-000000000001"
BATCH_PERF = "b0000002-0000-4000-8000-000000000002"
BATCH_ACQ = "b0000003-0000-4000-8000-000000000003"
BATCH_EXP = "b0000004-0000-4000-8000-000000000004"


def _det_uuid(namespace: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"metrictruth.{namespace}.{index}"))


def _split_int(total: int, parts: int) -> list[int]:
    base, rem = divmod(total, parts)
    return [base + (1 if i < rem else 0) for i in range(parts)]


def _split_dec(total: Decimal, parts: int) -> list[Decimal]:
    cents = int(total * 100)
    splits = _split_int(cents, parts)
    return [Decimal(c) / Decimal(100) for c in splits]


def generate_all(output_dir: Path = SYNTHETIC_DIR) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    campaigns_rows = [
        {
            "campaign_id": "CMP_001",
            "campaign_name": "Search",
            "channel": "SEARCH",
            "campaign_status": "ACTIVE",
            "created_at": "2026-01-15T09:00:00",
        },
        {
            "campaign_id": "CMP_002",
            "campaign_name": "Social",
            "channel": "SOCIAL",
            "campaign_status": "ACTIVE",
            "created_at": "2026-01-15T09:00:00",
        },
        {
            "campaign_id": "CMP_003",
            "campaign_name": "Affiliate",
            "channel": "AFFILIATE",
            "campaign_status": "ACTIVE",
            "created_at": "2026-02-01T09:00:00",
        },
        {
            "campaign_id": "CMP_004",
            "campaign_name": "Internal Test - Sandbox",
            "channel": "SEARCH",
            "campaign_status": "INTERNAL_TEST",
            "created_at": "2026-06-01T09:00:00",
        },
        {
            "campaign_id": "CMP_005",
            "campaign_name": "Display - Retargeting Pilot",
            "channel": "DISPLAY",
            "campaign_status": "ACTIVE",
            "created_at": "2026-08-15T09:00:00",
        },
    ]

    monthly_specs = [
        # September 2026 (includes CMP_005 zero-customer campaign for undefined-ratio testing)
        ("CMP_001", date(2026, 9, 1), 30, 750000, 38000, Decimal("57000.00"), 2375, Decimal("807500.00")),
        ("CMP_002", date(2026, 9, 1), 30, 960000, 24000, Decimal("38400.00"), 960, Decimal("297600.00")),
        ("CMP_003", date(2026, 9, 1), 30, 480000, 14400, Decimal("19200.00"), 480, Decimal("182400.00")),
        ("CMP_005", date(2026, 9, 1), 30, 120000, 2000, Decimal("3000.00"), 0, Decimal("0.00")),
        # October 2026 (Paid CAC = $120,000 / 4,000 = $30.00)
        ("CMP_001", date(2026, 10, 1), 31, 800000, 40000, Decimal("60000.00"), 2500, Decimal("850000.00")),
        ("CMP_002", date(2026, 10, 1), 31, 1000000, 25000, Decimal("40000.00"), 1000, Decimal("310000.00")),
        ("CMP_003", date(2026, 10, 1), 31, 500000, 15000, Decimal("20000.00"), 500, Decimal("190000.00")),
        ("CMP_004", date(2026, 10, 1), 31, 50000, 2500, Decimal("7500.00"), 120, Decimal("0.00")),
        # November 2026 (Paid CAC = $150,000 / 4,000 = $37.50, CVR = 4,000 / 83,000 = 4.82%, Revenue = $1.42M)
        ("CMP_001", date(2026, 11, 1), 30, 800000, 40000, Decimal("90000.00"), 2500, Decimal("900000.00")),
        ("CMP_002", date(2026, 11, 1), 30, 1120000, 28000, Decimal("42000.00"), 1000, Decimal("320000.00")),
        ("CMP_003", date(2026, 11, 1), 30, 500000, 15000, Decimal("18000.00"), 500, Decimal("200000.00")),
        ("CMP_004", date(2026, 11, 1), 30, 50000, 2500, Decimal("7500.00"), 110, Decimal("0.00")),
    ]

    perf_rows: list[dict[str, str]] = []
    acq_rows: list[dict[str, str]] = []
    perf_idx = 1
    acq_idx = 1
    cust_idx = 1

    for cid, start_dt, num_days, impressions, clicks, spend, valid_custs, revenue in monthly_specs:
        imp_daily = _split_int(impressions, num_days)
        clk_daily = _split_int(clicks, num_days)
        spd_daily = _split_dec(spend, num_days)
        cust_daily = _split_int(valid_custs, num_days)
        rev_splits = _split_dec(revenue, valid_custs) if valid_custs > 0 else []
        rev_cursor = 0

        for day_offset in range(num_days):
            cur_date = start_dt + timedelta(days=day_offset)
            perf_rows.append(
                {
                    "id": _det_uuid("perf", perf_idx),
                    "campaign_id": cid,
                    "report_date": cur_date.isoformat(),
                    "impressions": str(imp_daily[day_offset]),
                    "clicks": str(clk_daily[day_offset]),
                    "spend_usd": f"{spd_daily[day_offset]:.2f}",
                    "source_batch_id": BATCH_PERF,
                }
            )
            perf_idx += 1

            for c_i in range(cust_daily[day_offset]):
                acq_time = datetime(
                    cur_date.year, cur_date.month, cur_date.day, 10 + (c_i % 10), (c_i * 7) % 60, 0
                )
                cust_rev = rev_splits[rev_cursor] if rev_cursor < len(rev_splits) else Decimal("0.00")
                rev_cursor += 1
                acq_rows.append(
                    {
                        "acquisition_id": _det_uuid("acq", acq_idx),
                        "customer_id": f"CUST_{cust_idx:06d}",
                        "campaign_id": cid,
                        "acquired_at": acq_time.isoformat(),
                        "attribution_model": "last_non_direct_paid_click",
                        "is_valid": "true",
                        "first_order_revenue_usd": f"{cust_rev:.2f}",
                        "source_batch_id": BATCH_ACQ,
                    }
                )
                acq_idx += 1
                cust_idx += 1

    # Add invalid customer records and non-paid direct acquisitions to test exclusion rules
    for m in (10, 11):
        for i in range(50):
            acq_rows.append(
                {
                    "acquisition_id": _det_uuid("acq_invalid", m * 1000 + i),
                    "customer_id": f"CUST_INV_{m}_{i:04d}",
                    "campaign_id": "CMP_001",
                    "acquired_at": f"2026-{m:02d}-15T12:00:00",
                    "attribution_model": "last_non_direct_paid_click",
                    "is_valid": "false",
                    "first_order_revenue_usd": "0.00",
                    "source_batch_id": BATCH_ACQ,
                }
            )
        # Organic/direct new customers (included in Blended CAC, excluded from Paid CAC)
        for i in range(1000):
            acq_rows.append(
                {
                    "acquisition_id": _det_uuid("acq_organic", m * 10000 + i),
                    "customer_id": f"CUST_ORG_{m}_{i:04d}",
                    "campaign_id": "CMP_001",
                    "acquired_at": f"2026-{m:02d}-{(i % 28) + 1:02d}T14:00:00",
                    "attribution_model": "direct_organic",
                    "is_valid": "true",
                    "first_order_revenue_usd": "120.00",
                    "source_batch_id": BATCH_ACQ,
                }
            )

    expenses_rows = [
        {
            "expense_id": _det_uuid("exp", 1),
            "report_date": "2026-09-01",
            "category": "MARKETING_OPS_AND_SALES",
            "amount_usd": "25000.00",
            "source_batch_id": BATCH_EXP,
        },
        {
            "expense_id": _det_uuid("exp", 2),
            "report_date": "2026-10-01",
            "category": "MARKETING_OPS_AND_SALES",
            "amount_usd": "30000.00",
            "source_batch_id": BATCH_EXP,
        },
        {
            "expense_id": _det_uuid("exp", 3),
            "report_date": "2026-11-01",
            "category": "MARKETING_OPS_AND_SALES",
            "amount_usd": "35000.00",
            "source_batch_id": BATCH_EXP,
        },
    ]

    paths = {
        "campaigns": output_dir / "campaigns.csv",
        "daily_campaign_performance": output_dir / "daily_campaign_performance.csv",
        "customer_acquisitions": output_dir / "customer_acquisitions.csv",
        "operating_expenses_monthly": output_dir / "operating_expenses_monthly.csv",
    }

    _write_csv(paths["campaigns"], list(campaigns_rows[0].keys()), campaigns_rows)
    _write_csv(paths["daily_campaign_performance"], list(perf_rows[0].keys()), perf_rows)
    _write_csv(paths["customer_acquisitions"], list(acq_rows[0].keys()), acq_rows)
    _write_csv(paths["operating_expenses_monthly"], list(expenses_rows[0].keys()), expenses_rows)

    _verify_generated_Rollups(perf_rows, acq_rows)
    return paths


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _verify_generated_Rollups(
    perf_rows: list[dict[str, str]], acq_rows: list[dict[str, str]]
) -> None:
    active_cids = {"CMP_001", "CMP_002", "CMP_003"}
    oct_spend = sum(
        Decimal(r["spend_usd"])
        for r in perf_rows
        if r["campaign_id"] in active_cids and r["report_date"].startswith("2026-10")
    )
    nov_spend = sum(
        Decimal(r["spend_usd"])
        for r in perf_rows
        if r["campaign_id"] in active_cids and r["report_date"].startswith("2026-11")
    )
    oct_cust = len(
        {
            r["customer_id"]
            for r in acq_rows
            if r["campaign_id"] in active_cids
            and r["acquired_at"].startswith("2026-10")
            and r["is_valid"] == "true"
            and r["attribution_model"] == "last_non_direct_paid_click"
        }
    )
    nov_cust = len(
        {
            r["customer_id"]
            for r in acq_rows
            if r["campaign_id"] in active_cids
            and r["acquired_at"].startswith("2026-11")
            and r["is_valid"] == "true"
            and r["attribution_model"] == "last_non_direct_paid_click"
        }
    )
    assert oct_spend == Decimal("120000.00"), f"Expected Oct spend 120000, got {oct_spend}"
    assert nov_spend == Decimal("150000.00"), f"Expected Nov spend 150000, got {nov_spend}"
    assert oct_cust == 4000, f"Expected Oct customers 4000, got {oct_cust}"
    assert nov_cust == 4000, f"Expected Nov customers 4000, got {nov_cust}"
    assert oct_spend / oct_cust == Decimal("30.00")
    assert nov_spend / nov_cust == Decimal("37.50")


if __name__ == "__main__":
    out = generate_all()
    for name, p in out.items():
        print(f"Generated {name}: {p}")

