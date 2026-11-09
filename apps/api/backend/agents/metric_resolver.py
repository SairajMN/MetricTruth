from typing import Literal
from pydantic import BaseModel, Field
from backend.semantic.models import CertifiedMetricSpec
from backend.semantic.registry import MetricRegistryRepository


class MetricResolutionResult(BaseModel):
    status: Literal["RESOLVED", "AMBIGUOUS", "REJECTED_UNAPPROVED", "REJECTED_NOT_FOUND"]
    selected_metric: str | None = None
    metric_spec: CertifiedMetricSpec | None = None
    definition_version: int | None = None
    approval_status: str | None = None
    dimensions_available: list[str] = Field(default_factory=list)
    candidate_metrics: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    rejection_reason: str | None = None


class MetricResolver:
    def __init__(self, repo: MetricRegistryRepository | None = None) -> None:
        self._repo = repo or MetricRegistryRepository()

    async def resolve(
        self,
        requested_metric: str,
        question_text: str = "",
        has_campaign_context: bool = False,
        explicit_selection: bool = False,
    ) -> MetricResolutionResult:
        all_metrics = await self._repo.list_metrics()
        by_id = {m.metric_id: m for m in all_metrics}

        norm_req = requested_metric.strip().lower()
        norm_q = question_text.strip().lower()

        # 1. Check explicit qualifier in question or requested_metric first
        if "fully loaded" in norm_q or "loaded cac" in norm_q or norm_req == "fully_loaded_customer_acquisition_cost":
            target = by_id.get("fully_loaded_customer_acquisition_cost")
            if target:
                return self._check_approval(target)

        if "blended" in norm_q or norm_req == "blended_customer_acquisition_cost":
            target = by_id.get("blended_customer_acquisition_cost")
            if target:
                return self._check_approval(target)

        if "paid cac" in norm_q or "paid customer acquisition" in norm_q or "paid acquisition" in norm_q:
            target = by_id.get("paid_customer_acquisition_cost")
            if target:
                return self._check_approval(target)

        # 2. Check generic CAC ambiguity when not explicitly selected and no campaign/paid context
        is_generic_cac = (
            norm_req in {"cac", "customer_acquisition_cost", "paid_customer_acquisition_cost"}
            and ("cac" in norm_q or "customer acquisition cost" in norm_q or "acquisition cost" in norm_q)
            and "paid" not in norm_q
            and "blended" not in norm_q
            and "loaded" not in norm_q
        )
        if is_generic_cac and not explicit_selection and not has_campaign_context:
            return MetricResolutionResult(
                status="AMBIGUOUS",
                candidate_metrics=[
                    "paid_customer_acquisition_cost",
                    "blended_customer_acquisition_cost",
                    "fully_loaded_customer_acquisition_cost",
                ],
                clarification_question=(
                    "Which acquisition-cost metric should I investigate: "
                    "Paid CAC, Blended CAC or Fully Loaded CAC?"
                ),
            )

        # 3. Direct ID match
        if norm_req in by_id:
            return self._check_approval(by_id[norm_req])

        # 4. Alias match
        for m in all_metrics:
            aliases = {a.lower() for a in m.aliases} | {m.name.lower(), m.metric_id.lower()}
            if norm_req in aliases:
                return self._check_approval(m)

        for m in all_metrics:
            for alias in m.aliases:
                if alias.lower() in norm_q:
                    return self._check_approval(m)

        return MetricResolutionResult(
            status="REJECTED_NOT_FOUND",
            rejection_reason=f"Metric '{requested_metric}' does not exist in the certified metric registry.",
        )

    def _check_approval(self, spec: CertifiedMetricSpec) -> MetricResolutionResult:
        if spec.status != "approved":
            return MetricResolutionResult(
                status="REJECTED_UNAPPROVED",
                selected_metric=spec.metric_id,
                metric_spec=spec,
                definition_version=spec.version,
                approval_status=spec.status.upper(),
                rejection_reason=(
                    f"Metric '{spec.name}' ({spec.metric_id}) has status '{spec.status.upper()}' "
                    "and is not approved for business reporting."
                ),
            )
        return MetricResolutionResult(
            status="RESOLVED",
            selected_metric=spec.metric_id,
            metric_spec=spec,
            definition_version=spec.version,
            approval_status="APPROVED",
            dimensions_available=list(spec.dimensions),
        )

