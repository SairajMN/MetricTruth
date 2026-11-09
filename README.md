# MetricTruth — Certified AI Business Intelligence Engine

MetricTruth is an internal AI-powered business intelligence platform built for **DirectMeds** marketing, revenue, and operational analytics using synthetic datasets.

Instead of asking an LLM to invent SQL or calculate numbers in its weights, MetricTruth enforces a **Certified Metric Registry**, **Pydantic v2 structured query plans**, **deterministic SQLAlchemy Core CTE compilation**, **SQLGlot AST policy validation**, **read-only database isolation**, **independent Python `Decimal` numerical/reconciliation/freshness auditing**, and **claim grounding verification**.

---

## Core Capabilities

1. **Natural Language Analytics (`/ask`)**: Ask questions in plain English. Ambiguous requests (such as generic `"CAC"` without specifying Paid vs. Blended, or vague time windows) trigger structured clarification rather than guessing.
2. **Certified Metric Registry (`/metrics`)**: YAML-backed and database-versioned definitions (`paid_customer_acquisition_cost`, `blended_customer_acquisition_cost`, `fully_loaded_customer_acquisition_cost` [draft], `cost_per_click`, `click_through_rate`, `customer_conversion_rate`, `return_on_ad_spend`).
3. **Deterministic Query Engine (`/sql`)**: Application code (`SQLCompiler`) compiles validated `MetricQueryPlan` objects into parameterized SQLAlchemy Core CTE queries against `v_*` reporting views only.
4. **Independent Result Verification (`/runs/[runId]`)**: Recomputes all ratios, period-over-period changes, campaign contributions, and CPC/CVR driver decompositions in Python `Decimal`, verifies segment-to-total reconciliation (`$0.01` tolerance), and checks source freshness watermarks (`24h` SLA).
5. **Claim Validator**: Cross-checks every narrative claim against the `AuditBundle` and strips unsupported causal hallucinations (e.g., competitor bidding or ad platform algorithm claims not backed by warehouse columns).
6. **Execution Observatory & 55-Scenario Golden Evaluation Center (`/observatory`, `/evaluations`)**: Full step-by-step trace waterfall, token/cost budget enforcement, watermark-aware caching, and a 55-scenario automated benchmark suite.

---

## Quick Start

### 1. Backend & Database Setup (Python 3.12 + `uv`)

```bash
# Install dependencies
uv sync

# Generate deterministic synthetic datasets, seed schema + registry, and run initial ingestion
uv run python scripts/seed_database.py

# Run the 8-part video demonstration walkthrough
uv run python scripts/demo_walkthrough.py

# Run the 55-scenario Golden Evaluation Suite
uv run python scripts/run_evaluations.py

# Run pytest suite (unit, security boundaries, and API integration)
uv run pytest -v

# Start FastAPI server on http://localhost:8000
uv run uvicorn backend.main:app --app-dir apps/api --reload --port 8000
```

### 2. Frontend Setup (Next.js 15 App Router)

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000` to explore all 7 screens:
1. **Command Center** (`/`)
2. **Ask MetricTruth** (`/ask`)
3. **Investigation Report** (`/runs/latest`)
4. **SQL Inspector** (`/sql`)
5. **Certified Metric Registry** (`/metrics`)
6. **Execution Observatory** (`/observatory`)
7. **Evaluation Center** (`/evaluations`)

### 3. Optional Docker Compose (PostgreSQL 16 + Redis 7)

```bash
docker compose up -d
```
When PostgreSQL is running, set `APP_DATABASE_URL` and `READONLY_DATABASE_URL` in `.env` (see `.env.example`). `scripts/init_db.sql` automatically provisions the `metrictruth_app` and `metrictruth_reader` (`READ ONLY`, `reporting` views only) roles.
