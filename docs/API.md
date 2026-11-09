# MetricTruth REST & SSE API Reference

Base URL: `http://localhost:8000/api/v1`

## Analytics & Orchestrator

- `GET /analytics/overview` — Command Center summary counters, November 2026 KPIs, data source health, and recent runs.
- `POST /analytics/ask` — Execute a full 10-stage analytical investigation.
  - Body: `{"question": "...", "metric_override": null, "period_start": null, "period_end": null, "injected_unverified_claim": null, "use_cache": true}`
- `GET /analytics/runs` — List recent orchestrator runs.
- `GET /analytics/runs/{run_id}` — Full `OrchestratorRunResult` payload.
- `GET /analytics/runs/{run_id}/report` — Investigation report, audit bundle, and clarification payload.
- `GET /analytics/runs/{run_id}/sql` — Compiled SQL query, bound parameters, and 9-point SQLGlot validation report.
- `GET /analytics/runs/{run_id}/evidence` — Metric resolution, audit bundle, and raw query evidence rows.
- `GET /analytics/runs/{run_id}/events` — Step trace waterfall (supports `Accept: text/event-stream` or `?stream=true` for SSE).

## Certified Metric Registry

- `GET /metrics` — List all registered metrics (`?status=approved`).
- `GET /metrics/{metric_id}` — Get metric definition and version history.
- `POST /metrics` — Create a new metric (`X-Role: admin`).
- `PUT /metrics/{metric_id}` — Update a metric (`X-Role: admin`).
- `POST /metrics/{metric_id}/approve` — Promote a `draft` metric to `approved` and increment version (`X-Role: admin`).

## Data Ingestion & Quality

- `POST /data/upload` — Upload and validate a CSV batch (`X-Role: analyst` or `admin`).
- `POST /data/simulate-freshness` — Set `freshness_watermark` age in hours (`X-Role: analyst` or `admin`).
- `GET /data/sources` — List ingestion audit runs and watermarks.
- `GET /data/sources/{source_id}` — Inspect batch history for a specific source.
- `GET /data/quality` — List automated data quality test results.

## Golden Evaluation Suite

- `POST /evaluations/run` — Execute the 55-scenario Golden Evaluation Suite (`X-Role: analyst` or `admin`).
- `GET /evaluations/results` — Retrieve latest evaluation suite scorecard and scenario breakdown.
- `GET /evaluations/{run_id}` — Retrieve a specific evaluation run by ID.

