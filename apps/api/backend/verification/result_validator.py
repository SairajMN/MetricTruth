from typing import Any, Literal
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.query.sql_compiler import CompiledQueryArtifact
from backend.semantic.models import CertifiedMetricSpec
from backend.verification.freshness import FreshnessAuditor, FreshnessReport
from backend.verification.numerical_auditor import NumericalAuditReport, NumericalAuditor
from backend.verification.reconciliation import ReconciliationAuditor, ReconciliationReport


class AuditBundle(BaseModel):
    overall_status: Literal["VERIFIED", "UNCERTIFIED_STALE", "FAILED"]
    metric_id: str
    metric_name: str
    metric_version: int
    unit: str
    current_period_label: str
    comparison_period_label: str | None
    numerical: NumericalAuditReport
    reconciliation: ReconciliationReport
    freshness: FreshnessReport
    completeness_passed: bool


class ResultValidator:
    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._num = NumericalAuditor()
        self._rec = ReconciliationAuditor()
        self._fresh = FreshnessAuditor(engine=engine)

    async def validate_results(
        self,
        raw_rows: list[dict[str, Any]],
        spec: CertifiedMetricSpec,
        artifact: CompiledQueryArtifact,
    ) -> AuditBundle:
        numerical = self._num.audit(raw_rows, spec)
        reconciliation = self._rec.reconcile(numerical)
        freshness = await self._fresh.check_freshness(spec)
        completeness_ok = len(raw_rows) > 0 and freshness.status != "FAILED_MISSING_SOURCE"

        if numerical.status == "FAILED" or reconciliation.status == "FAILED" or not completeness_ok:
            overall = "FAILED"
        elif not freshness.certified_for_current_reporting:
            overall = "UNCERTIFIED_STALE"
        else:
            overall = "VERIFIED"

        cur_lbl = f"{artifact.current_period.start_date.isoformat()} to {artifact.current_period.end_date.isoformat()}"
        comp_lbl = (
            f"{artifact.comparison_period.start_date.isoformat()} to {artifact.comparison_period.end_date.isoformat()}"
            if artifact.comparison_period
            else None
        )

        return AuditBundle(
            overall_status=overall,
            metric_id=spec.metric_id,
            metric_name=spec.name,
            metric_version=spec.version,
            unit=spec.unit,
            current_period_label=cur_lbl,
            comparison_period_label=comp_lbl,
            numerical=numerical,
            reconciliation=reconciliation,
            freshness=freshness,
            completeness_passed=completeness_ok,
        )

