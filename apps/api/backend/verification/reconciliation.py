from decimal import Decimal
from typing import Literal
from pydantic import BaseModel
from backend.verification.numerical_auditor import NumericalAuditReport


class ReconciliationReport(BaseModel):
    status: Literal["PASSED", "FAILED"]
    total_spend_usd: Decimal
    sum_of_rows_spend_usd: Decimal
    total_new_customers: int
    sum_of_rows_customers: int
    spend_reconciled: bool
    customers_reconciled: bool
    detail: str


class ReconciliationAuditor:
    def reconcile(self, numerical_report: NumericalAuditReport) -> ReconciliationReport:
        row_spend_sum = sum((r.cur_spend_usd for r in numerical_report.rows), Decimal("0.00"))
        row_cust_sum = sum((r.cur_new_customers for r in numerical_report.rows), 0)

        spend_ok = abs(row_spend_sum - numerical_report.aggregate_cur_spend) <= Decimal("0.01")
        cust_ok = row_cust_sum == numerical_report.aggregate_cur_customers
        passed = spend_ok and cust_ok

        return ReconciliationReport(
            status="PASSED" if passed else "FAILED",
            total_spend_usd=numerical_report.aggregate_cur_spend,
            sum_of_rows_spend_usd=row_spend_sum,
            total_new_customers=numerical_report.aggregate_cur_customers,
            sum_of_rows_customers=row_cust_sum,
            spend_reconciled=spend_ok,
            customers_reconciled=cust_ok,
            detail=(
                f"Spend (${row_spend_sum:,.2f} == ${numerical_report.aggregate_cur_spend:,.2f}) "
                f"and customers ({row_cust_sum:,} == {numerical_report.aggregate_cur_customers:,}) reconciled."
                if passed
                else "Aggregate totals did not reconcile with grouped rows."
            ),
        )

