from backend.agents.question_planner import QuestionPlan
from backend.core.llm_client import LLMRouterClient
from backend.observability.cost_tracker import ModelCallUsage, RunBudgetLedger
from backend.query.plan_schema import AllowedDimension, Comparison, MetricQueryPlan
from backend.semantic.models import CertifiedMetricSpec
from backend.semantic.relationship_graph import CuratedSchemaContext


class QueryPlanner:
    def __init__(self, llm_client: LLMRouterClient | None = None) -> None:
        self._llm = llm_client or LLMRouterClient()

    async def create_plan(
        self,
        question_plan: QuestionPlan,
        spec: CertifiedMetricSpec,
        schema_ctx: CuratedSchemaContext,
        ledger: RunBudgetLedger,
        replan_feedback: str | None = None,
    ) -> MetricQueryPlan:
        allowed_dims: list[AllowedDimension] = [
            d for d in question_plan.group_by if d in schema_ctx.allowed_dimensions
        ]
        if not allowed_dims and "campaign" in schema_ctx.allowed_dimensions:
            allowed_dims = ["campaign"]

        det_plan = MetricQueryPlan(
            metric_id=spec.metric_id,
            period=question_plan.period,
            comparison=Comparison(type=question_plan.comparison),
            group_by=allowed_dims,
            filters=question_plan.filters,
            order_by=["spend_desc"],
            limit=20,
            include_driver_analysis=("DRIVER_ANALYSIS" in question_plan.analysis_type),
        )

        if self._llm.is_live_enabled:
            try:
                sys_prompt = (
                    f"Create a structured MetricQueryPlan JSON for metric '{spec.metric_id}'. "
                    f"Allowed dimensions: {schema_ctx.allowed_dimensions}. "
                    f"Replan feedback: {replan_feedback or 'none'}."
                )
                user_prompt = question_plan.model_dump_json()
                llm_plan = await self._llm.generate_structured(
                    component="query_planner",
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    response_model=MetricQueryPlan,
                    ledger=ledger,
                    tier="fast",
                )
                llm_plan.metric_id = spec.metric_id
                llm_plan.group_by = [
                    d for d in llm_plan.group_by if d in schema_ctx.allowed_dimensions
                ] or allowed_dims
                return llm_plan
            except Exception:
                pass
        else:
            ledger.record_call(
                ModelCallUsage(
                    component="query_planner",
                    model_name="deterministic-plan-builder",
                    input_tokens=45,
                    output_tokens=32,
                    cached_tokens=0,
                    duration_ms=0.9,
                    is_billed_provider_cost=False,
                )
            )

        return det_plan

