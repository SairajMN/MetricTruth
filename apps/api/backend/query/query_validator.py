from pydantic import BaseModel, Field
import sqlglot
from sqlglot import exp
from backend.query.plan_schema import MetricQueryPlan
from backend.query.query_policy import (
    ALLOWED_FILTER_FIELDS,
    ALLOWED_REPORTING_VIEWS,
    FORBIDDEN_SQL_FUNCTIONS,
    MAX_CTES,
    MAX_JOINS,
    MAX_QUERY_LIMIT,
    MAX_WINDOW_DAYS,
)
from backend.query.sql_compiler import CompiledQueryArtifact
from backend.semantic.models import CertifiedMetricSpec


class PolicyCheckResult(BaseModel):
    check_name: str
    passed: bool
    detail: str


class QueryValidationReport(BaseModel):
    passed: bool
    checks: list[PolicyCheckResult] = Field(default_factory=list)
    failed_reasons: list[str] = Field(default_factory=list)


FORBIDDEN_AST_TYPES = tuple(
    t
    for t in (
        getattr(exp, "Insert", None),
        getattr(exp, "Update", None),
        getattr(exp, "Delete", None),
        getattr(exp, "Drop", None),
        getattr(exp, "Create", None),
        getattr(exp, "Alter", None),
        getattr(exp, "Command", None),
        getattr(exp, "Copy", None),
        getattr(exp, "Grant", None),
        getattr(exp, "Transaction", None),
        getattr(exp, "Commit", None),
        getattr(exp, "Rollback", None),
        getattr(exp, "Pragma", None),
    )
    if t is not None
)


class QueryValidator:
    def validate(
        self,
        plan: MetricQueryPlan,
        spec: CertifiedMetricSpec,
        artifact: CompiledQueryArtifact,
    ) -> QueryValidationReport:
        checks: list[PolicyCheckResult] = []

        # 1. Metric validation
        metric_ok = spec.status == "approved" and plan.metric_id == spec.metric_id
        checks.append(
            PolicyCheckResult(
                check_name="metric_validation",
                passed=metric_ok,
                detail=f"Metric '{spec.metric_id}' status={spec.status}",
            )
        )

        # 2. Dimension validation
        bad_dims = [d for d in plan.group_by if d not in spec.dimensions]
        checks.append(
            PolicyCheckResult(
                check_name="dimension_validation",
                passed=(len(bad_dims) == 0),
                detail="All requested dimensions allowed" if not bad_dims else f"Unauthorized dimensions: {bad_dims}",
            )
        )

        # 3. Filter validation
        bad_filters = [f for f in plan.filters if f not in ALLOWED_FILTER_FIELDS]
        checks.append(
            PolicyCheckResult(
                check_name="filter_validation",
                passed=(len(bad_filters) == 0),
                detail="All filters allowed" if not bad_filters else f"Unsupported filters: {bad_filters}",
            )
        )

        # 4. Time range validation
        span_days = (plan.period.end_date - plan.period.start_date).days
        time_ok = 0 <= span_days <= MAX_WINDOW_DAYS
        checks.append(
            PolicyCheckResult(
                check_name="time_range",
                passed=time_ok,
                detail=f"Window span is {span_days + 1} days (max {MAX_WINDOW_DAYS})",
            )
        )

        # 5. Result size validation
        limit_ok = 1 <= plan.limit <= MAX_QUERY_LIMIT
        checks.append(
            PolicyCheckResult(
                check_name="result_size",
                passed=limit_ok,
                detail=f"Row limit={plan.limit} (max {MAX_QUERY_LIMIT})",
            )
        )

        # Parse SQL via SQLGlot for AST structural & security checks
        try:
            parsed = sqlglot.parse(artifact.display_sql, read="postgres")
        except Exception as exc:
            checks.append(
                PolicyCheckResult(
                    check_name="query_structure",
                    passed=False,
                    detail=f"SQLGlot parse error: {exc}",
                )
            )
            return self._finalize(checks)

        single_select = (
            len(parsed) == 1
            and parsed[0] is not None
            and isinstance(parsed[0], exp.Select)
            and not any(isinstance(node, FORBIDDEN_AST_TYPES) for node in parsed[0].walk())
        )
        checks.append(
            PolicyCheckResult(
                check_name="query_structure",
                passed=single_select,
                detail="Verified single read-only SELECT AST" if single_select else "Non-SELECT or multi-statement SQL detected",
            )
        )

        if not single_select or parsed[0] is None:
            return self._finalize(checks)

        ast_root = parsed[0]
        cte_names = {cte.alias_or_name.lower() for cte in ast_root.find_all(exp.CTE)}
        physical_tables = {
            tbl.name.lower()
            for tbl in ast_root.find_all(exp.Table)
            if tbl.name and tbl.name.lower() not in cte_names
        }

        # 6. Source access validation
        unauthorized_tables = [t for t in physical_tables if t not in ALLOWED_REPORTING_VIEWS]
        checks.append(
            PolicyCheckResult(
                check_name="source_access",
                passed=(len(unauthorized_tables) == 0 and len(physical_tables) > 0),
                detail=f"Accessed views: {sorted(physical_tables)}"
                if not unauthorized_tables
                else f"Unauthorized table access: {unauthorized_tables}",
            )
        )

        # 7. Join validation
        joins = list(ast_root.find_all(exp.Join))
        joins_ok = len(joins) <= MAX_JOINS
        checks.append(
            PolicyCheckResult(
                check_name="join_validation",
                passed=joins_ok,
                detail=f"{len(joins)} approved grain-aligned joins",
            )
        )

        # 8. Query complexity validation
        ctes = list(ast_root.find_all(exp.CTE))
        complexity_ok = len(ctes) <= MAX_CTES and len(joins) <= MAX_JOINS
        checks.append(
            PolicyCheckResult(
                check_name="query_complexity",
                passed=complexity_ok,
                detail=f"CTEs={len(ctes)} (max {MAX_CTES}), Joins={len(joins)} (max {MAX_JOINS})",
            )
        )

        # 9. Parameter & function safety validation
        called_funcs = {
            fn.name.lower() for fn in ast_root.find_all(exp.Anonymous, exp.Func) if fn.name
        }
        bad_funcs = [f for f in called_funcs if f in FORBIDDEN_SQL_FUNCTIONS]
        params_ok = len(bad_funcs) == 0 and len(artifact.bound_params) > 0
        checks.append(
            PolicyCheckResult(
                check_name="parameter_validation",
                passed=params_ok,
                detail=f"{len(artifact.bound_params)} bound parameters, 0 dangerous functions"
                if params_ok
                else f"Forbidden functions or unbound literals: {bad_funcs}",
            )
        )

        return self._finalize(checks)

    def _finalize(self, checks: list[PolicyCheckResult]) -> QueryValidationReport:
        failed = [f"{c.check_name}: {c.detail}" for c in checks if not c.passed]
        return QueryValidationReport(passed=(len(failed) == 0), checks=checks, failed_reasons=failed)

