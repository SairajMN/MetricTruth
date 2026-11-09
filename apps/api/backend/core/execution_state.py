from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field
from backend.agents.insight_generator import InvestigationReport
from backend.agents.metric_resolver import MetricResolutionResult
from backend.agents.question_planner import QuestionPlan
from backend.observability.cost_tracker import RunBudgetLedger
from backend.query.plan_schema import MetricQueryPlan
from backend.query.query_validator import QueryValidationReport
from backend.query.sql_compiler import CompiledQueryArtifact
from backend.verification.result_validator import AuditBundle

RunStatus = Literal[
    "RUNNING",
    "COMPLETED",
    "CLARIFICATION_REQUIRED",
    "BLOCKED",
    "FAILED",
]


class StepTraceEvent(BaseModel):
    sequence: int
    component: str
    label: str
    status: Literal["COMPLETED", "PASSED", "FAILED", "BLOCKED", "SKIPPED"]
    duration_ms: float
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class ClarificationPayload(BaseModel):
    question: str
    options: list[str]
    candidate_metrics: list[str] = Field(default_factory=list)


class OrchestratorRunResult(BaseModel):
    run_id: str
    question: str
    status: RunStatus
    current_stage: str
    question_plan: QuestionPlan | None = None
    metric_resolution: MetricResolutionResult | None = None
    query_plan: MetricQueryPlan | None = None
    compiled_sql: CompiledQueryArtifact | None = None
    query_validation: QueryValidationReport | None = None
    audit_bundle: AuditBundle | None = None
    report: InvestigationReport | None = None
    clarification: ClarificationPayload | None = None
    failure_reason: str | None = None
    events: list[StepTraceEvent] = Field(default_factory=list)
    usage: RunBudgetLedger = Field(default_factory=RunBudgetLedger)
    cache_hit: bool = False
    duration_ms: float = 0.0
    created_at: datetime
    completed_at: datetime | None = None

