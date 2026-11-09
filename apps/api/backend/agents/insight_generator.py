from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field
from backend.core.llm_client import LLMRouterClient
from backend.observability.cost_tracker import ModelCallUsage, RunBudgetLedger
from backend.semantic.models import CertifiedMetricSpec
from backend.verification.result_validator import AuditBundle

ClaimType = Literal[
    "NUMERICAL",
    "PERCENTAGE_CHANGE",
    "CAMPAIGN_COMPARISON",
    "METRIC_DEFINITION",
    "DATA_FRESHNESS",
    "CAUSAL_EXPLANATION",
    "RECOMMENDATION",
]

SupportStatus = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]


class AnalyticalClaim(BaseModel):
    claim_id: str
    claim_type: ClaimType
    statement: str
    referenced_numbers: list[float] = Field(default_factory=list)
    evidence_source: str
    support_status: SupportStatus = "SUPPORTED"
    qualification_note: str | None = None


class ReportSection(BaseModel):
    heading: str
    body: str
    highlight_metric: str | None = None


class StrippedClaimRecord(BaseModel):
    claim_id: str
    claim_type: str
    original_statement: str
    rejection_reason: str


class InvestigationReport(BaseModel):
    title: str
    overall_finding: str
    executive_summary: str
    certification_status: Literal["CERTIFIED", "NOT_CERTIFIED_STALE_DATA", "REJECTED"]
    certification_banner: str
    sections: list[ReportSection] = Field(default_factory=list)
    claims: list[AnalyticalClaim] = Field(default_factory=list)
    stripped_claims: list[StrippedClaimRecord] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    grounded_claim_rate: float = 1.0


class InsightGenerator:
    def __init__(self, llm_client: LLMRouterClient | None = None) -> None:
        self._llm = llm_client or LLMRouterClient()

    async def generate(
        self,
        bundle: AuditBundle,
        spec: CertifiedMetricSpec,
        ledger: RunBudgetLedger,
        injected_unverified_claim: str | None = None,
    ) -> InvestigationReport:
        report = self._build_deterministic_report(bundle, spec, injected_unverified_claim)

        if self._llm.is_live_enabled and not injected_unverified_claim:
            try:
                sys_prompt = (
                    "You are the MetricTruth Insight Generator. Summarize ONLY the verified numbers in "
                    "the provided AuditBundle. Never invent causes not present in the schema."
                )
                llm_report = await self._llm.generate_structured(
                    component="insight_generator",
                    system_prompt=sys_prompt,
                    user_prompt=bundle.model_dump_json(),
                    response_model=InvestigationReport,
                    ledger=ledger,
                    tier="synthesis",
                )
                if llm_report.sections and llm_report.claims:
                    return llm_report
            except Exception:
                pass
        else:
            ledger.record_call(
                ModelCallUsage(
                    component="insight_generator",
                    model_name="deterministic-evidence-narrator",
                    input_tokens=180,
                    output_tokens=210,
                    cached_tokens=0,
                    duration_ms=1.5,
                    is_billed_provider_cost=False,
                )
            )

        return report

    def _build_deterministic_report(
        self,
        bundle: AuditBundle,
        spec: CertifiedMetricSpec,
        injected_unverified_claim: str | None = None,
    ) -> InvestigationReport:
        num = bundle.numerical
        cur_disp = num.aggregate_current_display
        prev_disp = num.aggregate_previous_display
        pct = num.aggregate_pct_change

        if pct is not None and num.aggregate_previous is not None:
            direction = "increased" if pct >= Decimal("0") else "decreased"
            overall = (
                f"{spec.name} {direction} by {abs(pct):.2f}% "
                f"(from {prev_disp} in the previous period to {cur_disp} in the current period)."
            )
        else:
            overall = f"{spec.name} for the current period ({bundle.current_period_label}) is {cur_disp}."

        cert_status: Literal["CERTIFIED", "NOT_CERTIFIED_STALE_DATA", "REJECTED"] = (
            "CERTIFIED"
            if bundle.overall_status == "VERIFIED"
            else ("NOT_CERTIFIED_STALE_DATA" if bundle.overall_status == "UNCERTIFIED_STALE" else "REJECTED")
        )
        cert_banner = (
            bundle.freshness.warning_message
            if bundle.freshness.warning_message
            else f"CERTIFIED REPORT — {spec.name} (v{spec.version}) verified against read-only reporting views."
        )

        sections: list[ReportSection] = []
        claims: list[AnalyticalClaim] = []
        claim_idx = 1

        claims.append(
            AnalyticalClaim(
                claim_id=f"CLM_{claim_idx:02d}",
                claim_type="METRIC_DEFINITION",
                statement=(
                    f"Certified Metric '{spec.name}' (v{spec.version}) is calculated as "
                    f"{spec.formula.numerator} / {spec.formula.denominator}."
                ),
                referenced_numbers=[float(spec.version)],
                evidence_source=f"certified_metrics:{spec.metric_id}:v{spec.version}",
                support_status="SUPPORTED",
            )
        )
        claim_idx += 1

        if num.aggregate_current is not None:
            ref_nums = [float(num.aggregate_current)]
            if num.aggregate_previous is not None:
                ref_nums.append(float(num.aggregate_previous))
            if pct is not None:
                ref_nums.append(float(pct))
            claims.append(
                AnalyticalClaim(
                    claim_id=f"CLM_{claim_idx:02d}",
                    claim_type="PERCENTAGE_CHANGE" if pct is not None else "NUMERICAL",
                    statement=overall,
                    referenced_numbers=ref_nums,
                    evidence_source="numerical_auditor:aggregate",
                    support_status="SUPPORTED",
                )
            )
            claim_idx += 1

        sorted_rows = sorted(
            num.rows,
            key=lambda r: abs(r.pct_change or Decimal("0")),
            reverse=True,
        )

        for idx, row in enumerate(sorted_rows, start=1):
            if row.current_value is None:
                body = (
                    f"{row.dimension_key}: {row.current_display}. "
                    f"Spend was ${row.cur_spend_usd:,.2f} with {row.cur_new_customers:,} attributed customers."
                )
                sections.append(
                    ReportSection(
                        heading=f"{idx}. {row.dimension_key} (Undefined Ratio)",
                        body=body,
                        highlight_metric=row.current_display,
                    )
                )
                continue

            if row.previous_value is not None and row.pct_change is not None:
                r_dir = "increased" if row.pct_change >= Decimal("0") else "decreased"
                lead = "Main contributor: " if idx == 1 else ""
                heading = f"{idx}. {lead}{row.dimension_key}"
                body_parts = [
                    f"{row.dimension_key} {spec.name} {r_dir} from {row.previous_display} to {row.current_display} ({row.pct_change:+.2f}%)."
                ]
                if row.spend_change_pct is not None and row.customer_change_pct is not None:
                    body_parts.append(
                        f"Advertising expenditure changed by {row.spend_change_pct:+.2f}% "
                        f"(${row.prev_spend_usd:,.2f} to ${row.cur_spend_usd:,.2f}), while attributed new customers "
                        f"changed by {row.customer_change_pct:+.2f}% ({row.prev_new_customers:,} to {row.cur_new_customers:,})."
                    )
                if (
                    row.current_drivers.cpc is not None
                    and row.previous_drivers.cpc is not None
                    and row.current_drivers.cvr_pct is not None
                    and row.previous_drivers.cvr_pct is not None
                ):
                    body_parts.append(
                        f"Driver decomposition shows CPC moved from ${row.previous_drivers.cpc:.2f} to "
                        f"${row.current_drivers.cpc:.2f} while conversion rate moved from "
                        f"{row.previous_drivers.cvr_pct:.2f}% to {row.current_drivers.cvr_pct:.2f}%."
                    )
                body = " ".join(body_parts)
                sections.append(
                    ReportSection(
                        heading=heading,
                        body=body,
                        highlight_metric=f"{row.current_display} ({row.pct_change:+.1f}%)",
                    )
                )
                claims.append(
                    AnalyticalClaim(
                        claim_id=f"CLM_{claim_idx:02d}",
                        claim_type="CAMPAIGN_COMPARISON",
                        statement=body,
                        referenced_numbers=[
                            float(row.previous_value),
                            float(row.current_value),
                            float(row.pct_change),
                        ],
                        evidence_source=f"query_evidence:row:{row.dimension_key}",
                        support_status="SUPPORTED",
                    )
                )
                claim_idx += 1
            else:
                body = (
                    f"{row.dimension_key} recorded {row.current_display} "
                    f"(Spend: ${row.cur_spend_usd:,.2f}, Customers: {row.cur_new_customers:,}, "
                    f"Clicks: {row.cur_clicks:,})."
                )
                sections.append(
                    ReportSection(
                        heading=f"{idx}. {row.dimension_key}",
                        body=body,
                        highlight_metric=row.current_display,
                    )
                )
                claims.append(
                    AnalyticalClaim(
                        claim_id=f"CLM_{claim_idx:02d}",
                        claim_type="NUMERICAL",
                        statement=body,
                        referenced_numbers=[float(row.current_value)],
                        evidence_source=f"query_evidence:row:{row.dimension_key}",
                        support_status="SUPPORTED",
                    )
                )
                claim_idx += 1

        if injected_unverified_claim:
            claims.append(
                AnalyticalClaim(
                    claim_id=f"CLM_{claim_idx:02d}",
                    claim_type="CAUSAL_EXPLANATION",
                    statement=injected_unverified_claim,
                    referenced_numbers=[],
                    evidence_source="unverified_model_hypothesis",
                    support_status="UNSUPPORTED",
                )
            )
            claim_idx += 1

        top_name = sorted_rows[0].dimension_key if sorted_rows else "primary campaign"
        rec_text = (
            f"Analytical suggestion: Investigate {top_name}'s cost-per-click and keyword placement mix. "
            "External auction-level telemetry and impression-share logs are not stored in the reporting warehouse "
            "and would be required to establish external root-cause causality."
        )
        sections.append(
            ReportSection(
                heading=f"{len(sections) + 1}. Recommended Investigation",
                body=rec_text,
            )
        )
        claims.append(
            AnalyticalClaim(
                claim_id=f"CLM_{claim_idx:02d}",
                claim_type="RECOMMENDATION",
                statement=rec_text,
                referenced_numbers=[],
                evidence_source="analytical_suggestion",
                support_status="PARTIALLY_SUPPORTED",
                qualification_note="Identified as an analytical suggestion, not a verified causal fact.",
            )
        )

        exec_summary = (
            f"{overall} Reconciliation across {len(num.rows)} grouped segments {bundle.reconciliation.status.lower()} "
            f"(${bundle.reconciliation.total_spend_usd:,.2f} total spend, {bundle.reconciliation.total_new_customers:,} attributed customers)."
        )

        return InvestigationReport(
            title=f"{spec.name} Investigation",
            overall_finding=overall,
            executive_summary=exec_summary,
            certification_status=cert_status,
            certification_banner=cert_banner,
            sections=sections,
            claims=claims,
            recommendations=[rec_text],
        )
