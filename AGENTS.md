# MetricTruth Engineering Guidelines

## Non-Negotiable Architecture Invariants

1. **LLMs never define business truth.** All metric definitions, formulas, grains, attribution rules, exclusions, and freshness SLAs must be resolved from versioned YAML definitions registered in the database.
2. **LLMs never generate or execute SQL.** Models output strictly validated Pydantic v2 query plans (`MetricQueryPlan`). Application code compiles grain-safe SQL via SQLAlchemy Core, validates the AST via SQLGlot, and executes via the restricted `metrictruth_reader` connection.
3. **LLMs never self-certify numerical or causal outputs.** Deterministic auditors recompute ratios, reconciliations, and freshness watermarks in `Decimal`, and `ClaimValidator` strips any unsupported causal claims before emitting a report.

## Coding Standards

- Solve the problem with the smallest complete change using standard library and existing project dependencies.
- Keep functions and modules single-purpose without speculative wrappers or unused abstractions.
- Write self-explanatory code; add a single-line comment only when explaining a non-obvious *why*.
- Never cut validation at trust boundaries, read-only database restrictions, or numerical audit checks.

