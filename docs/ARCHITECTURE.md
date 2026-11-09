# MetricTruth Technical Architecture

## 1. Ten-Stage Deterministic Orchestration Pipeline

MetricTruth uses a custom deterministic orchestrator (`apps/api/backend/core/orchestrator.py`) that coordinates 10 specialized components:

1. **Question Planner (`question_planner.py`)**: Classifies user intent, detects prompt injection or destructive SQL payloads, identifies candidate metrics, dimensions, filters, and reporting windows, and flags ambiguity.
2. **Metric Resolver (`metric_resolver.py`)**: Resolves candidate metrics against the Certified Metric Registry (`status == 'approved'`). Blocks `draft` or `retired` metrics and custom user-invented formulas.
3. **Schema Explorer (`schema_explorer.py`)**: Inspects the approved `RelationshipGraph` (`campaign_id` grain alignment across `v_campaigns`, `v_daily_campaign_performance`, and `v_customer_acquisitions`).
4. **Query Planner (`query_planner.py`)**: Constructs a strict Pydantic v2 `MetricQueryPlan` (`extra="forbid"`).
5. **SQL Compiler (`sql_compiler.py`)**: Deterministically builds parameterized SQLAlchemy Core CTE queries (`spend_cur`, `acq_cur`, `spend_prev`, `acq_prev`) preventing join fan-out between daily spend rows and acquisition events.
6. **Query Validator (`query_validator.py`)**: Parses the compiled SQL into a SQLGlot AST and enforces 9 policy checks (`metric_validation`, `dimension_validation`, `filter_validation`, `time_range`, `result_size`, `query_structure`, `source_access`, `join_validation`, `parameter_validation`).
7. **Query Executor (`query_executor.py`)**: Executes the validated query exclusively over `readonly_engine` (`metrictruth_reader` role / SQLite `query_only` + C-level `set_authorizer`).
8. **Result Validator (`result_validator.py`)**: Runs `NumericalAuditor` (`Decimal` arithmetic), `ReconciliationAuditor` (segment sum vs. aggregate total), and `FreshnessAuditor` (`data_source_runs.freshness_watermark` vs. `maximum_age_hours`).
9. **Insight Generator (`insight_generator.py`)**: Synthesizes structured sections and typed `AnalyticalClaim` objects from the verified `AuditBundle`.
10. **Claim Validator (`claim_validator.py`)**: Verifies every numerical and causal claim against the `AuditBundle` and strips unsupported causal hypotheses before returning the report.

