from decimal import Decimal
import re
from backend.agents.insight_generator import (
    AnalyticalClaim,
    InvestigationReport,
    StrippedClaimRecord,
)
from backend.verification.result_validator import AuditBundle

UNSUPPORTED_CAUSAL_PATTERNS = (
    r"competitor[s]?\s+(raised|increased|changed|aggressive)",
    r"competitor[s]?\s+bidding",
    r"bidding\s+budget[s]?",
    r"auction\s+competition",
    r"algorithm\s+(update|change)",
    r"ad\s+fatigue",
    r"creative\s+fatigue",
    r"macroeconomic",
    r"seasonal\s+demand\s+spike",
    r"ios\s+privacy\s+change",
)


class ClaimValidationOutcome(InvestigationReport):
    pass


class ClaimValidator:
    def validate_and_sanitize(
        self, report: InvestigationReport, bundle: AuditBundle
    ) -> InvestigationReport:
        allowed_numbers = self._collect_verified_numbers(bundle)
        kept_claims: list[AnalyticalClaim] = []
        stripped: list[StrippedClaimRecord] = list(report.stripped_claims)

        for claim in report.claims:
            stmt_lower = claim.statement.lower()

            # 1. Check for unsupported external causal explanations
            is_unmeasured_causal = claim.claim_type == "CAUSAL_EXPLANATION" or any(
                re.search(pat, stmt_lower) for pat in UNSUPPORTED_CAUSAL_PATTERNS
            )
            if is_unmeasured_causal:
                claim.support_status = "UNSUPPORTED"
                stripped.append(
                    StrippedClaimRecord(
                        claim_id=claim.claim_id,
                        claim_type=claim.claim_type,
                        original_statement=claim.statement,
                        rejection_reason=(
                            "Claim rejected: The database contains no competitor bidding, external auction, "
                            "or ad-fatigue telemetry to verify this causal explanation."
                        ),
                    )
                )
                continue

            # 2. Verify referenced numbers against AuditBundle
            if claim.claim_type in ("NUMERICAL", "PERCENTAGE_CHANGE", "CAMPAIGN_COMPARISON"):
                bad_nums = [
                    n
                    for n in claim.referenced_numbers
                    if not self._number_matches_any(n, allowed_numbers)
                ]
                if bad_nums:
                    claim.support_status = "UNSUPPORTED"
                    stripped.append(
                        StrippedClaimRecord(
                            claim_id=claim.claim_id,
                            claim_type=claim.claim_type,
                            original_statement=claim.statement,
                            rejection_reason=f"Unverified numerical values {bad_nums} not present in AuditBundle.",
                        )
                    )
                    continue
                claim.support_status = "SUPPORTED"

            # 3. Ensure recommendations are qualified as suggestions
            if claim.claim_type == "RECOMMENDATION":
                claim.support_status = "PARTIALLY_SUPPORTED"
                if not claim.qualification_note:
                    claim.qualification_note = (
                        "Analytical recommendation for follow-up investigation, not a verified fact."
                    )

            kept_claims.append(claim)

        # Strip unsupported causal sentences from section bodies as well
        for sec in report.sections:
            for pat in UNSUPPORTED_CAUSAL_PATTERNS:
                if re.search(pat, sec.body.lower()):
                    sec.body = re.sub(
                        r"[^.?!]*(" + pat + r")[^.?!]*[.?!]?",
                        "",
                        sec.body,
                        flags=re.IGNORECASE,
                    ).strip()

        total_evaluated = len(kept_claims) + len(stripped)
        grounded_rate = round(len(kept_claims) / total_evaluated, 4) if total_evaluated > 0 else 1.0

        report.claims = kept_claims
        report.stripped_claims = stripped
        report.grounded_claim_rate = grounded_rate
        return report

    def _collect_verified_numbers(self, bundle: AuditBundle) -> set[float]:
        nums: set[float] = {float(bundle.metric_version)}
        n = bundle.numerical
        for val in (
            n.aggregate_current,
            n.aggregate_previous,
            n.aggregate_abs_change,
            n.aggregate_pct_change,
            n.aggregate_cur_spend,
            n.aggregate_prev_spend,
            n.aggregate_cur_customers,
            n.aggregate_prev_customers,
            n.aggregate_cur_clicks,
            n.aggregate_prev_clicks,
            n.aggregate_cur_impressions,
            n.aggregate_prev_impressions,
            n.aggregate_cur_revenue,
            n.aggregate_prev_revenue,
            n.aggregate_current_drivers.cpc,
            n.aggregate_current_drivers.cvr_pct,
            n.aggregate_current_drivers.ctr_pct,
            n.aggregate_previous_drivers.cpc,
            n.aggregate_previous_drivers.cvr_pct,
            n.aggregate_previous_drivers.ctr_pct,
        ):
            if val is not None:
                nums.add(round(float(val), 2))
                nums.add(abs(round(float(val), 2)))

        for r in n.rows:
            for val in (
                r.current_value,
                r.previous_value,
                r.absolute_change,
                r.pct_change,
                r.cur_spend_usd,
                r.prev_spend_usd,
                r.spend_change_pct,
                r.cur_new_customers,
                r.prev_new_customers,
                r.customer_change_pct,
                r.cur_clicks,
                r.prev_clicks,
                r.cur_impressions,
                r.prev_impressions,
                r.cur_revenue_usd,
                r.prev_revenue_usd,
                r.current_drivers.cpc,
                r.current_drivers.cvr_pct,
                r.current_drivers.ctr_pct,
                r.previous_drivers.cpc,
                r.previous_drivers.cvr_pct,
                r.previous_drivers.ctr_pct,
            ):
                if val is not None:
                    nums.add(round(float(val), 2))
                    nums.add(abs(round(float(val), 2)))
        return nums

    def _number_matches_any(self, candidate: float, allowed: set[float]) -> bool:
        for a in allowed:
            if abs(candidate - a) <= 0.06:
                return True
        return False

