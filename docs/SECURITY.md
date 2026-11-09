# Security & Governance Controls

## 1. Dual-Engine Read-Only Database Isolation

- **Application Engine (`app_engine`)**: Used only for ingestion, metric governance, and audit logging.
- **Read-Only Reporting Engine (`readonly_engine`)**:
  - **PostgreSQL (`scripts/init_db.sql`)**: Connects as `metrictruth_reader` with `default_transaction_read_only = on`, `statement_timeout = 5000ms`, `lock_timeout = 2000ms`, and `SELECT` privileges granted exclusively on `reporting.v_*` views.
  - **SQLite (`apps/api/backend/db.py`)**: Enforces `PRAGMA query_only = ON` plus a C-level `sqlite3.Connection.set_authorizer` callback that denies `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, and blocks `READ` access to any table outside `{v_campaigns, v_daily_campaign_performance, v_customer_acquisitions, v_expenses}`.

## 2. SQLGlot AST Validation (`QueryValidator`)

Before any query reaches `readonly_engine`, `QueryValidator` parses the SQL into a SQLGlot AST and verifies:
1. Single `SELECT` statement only (blocks multi-statement queries and all DDL/DML nodes).
2. Physical table references belong strictly to `ALLOWED_REPORTING_VIEWS`.
3. No dangerous database functions (`pg_sleep`, `dblink`, `pg_read_file`, `lo_import`, `load_extension`).
4. Bound parameters used for all filter values (`paramstyle="named"`).

## 3. Prompt Injection & Governance Guardrails

- Prompt injection attempts (`"Ignore the metric registry..."`, `"Bypass security guardrails..."`) and SQL injection strings (`"DROP TABLE..."`, `"SELECT * FROM patient_records"`) are intercepted at the Question Planner stage and logged to `security_audit_log`.
- Role-Based Access Control (`X-Role: viewer | analyst | admin`):
  - `viewer`: Can ask questions and inspect reports/SQL/observatory.
  - `analyst`: Can upload CSV batches, simulate freshness watermarks, and trigger evaluation runs.
  - `admin`: Can create, update, and approve (`POST /api/v1/metrics/{id}/approve`) certified metrics.

