-- PostgreSQL 16 dual-role security initialization for MetricTruth

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'metrictruth_app') THEN
        CREATE ROLE metrictruth_app WITH LOGIN PASSWORD 'metrictruth_app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'metrictruth_reader') THEN
        CREATE ROLE metrictruth_reader WITH LOGIN PASSWORD 'metrictruth_reader_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS core AUTHORIZATION metrictruth_app;
CREATE SCHEMA IF NOT EXISTS reporting AUTHORIZATION metrictruth_app;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION metrictruth_app;
CREATE SCHEMA IF NOT EXISTS eval AUTHORIZATION metrictruth_app;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA core FROM metrictruth_reader;
REVOKE ALL ON SCHEMA audit FROM metrictruth_reader;
REVOKE ALL ON SCHEMA eval FROM metrictruth_reader;

GRANT USAGE ON SCHEMA core, reporting, audit, eval TO metrictruth_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core, reporting, audit, eval TO metrictruth_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA core, reporting, audit, eval GRANT ALL PRIVILEGES ON TABLES TO metrictruth_app;

-- Restrict metrictruth_reader strictly to read-only access on reporting views
GRANT USAGE ON SCHEMA reporting TO metrictruth_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO metrictruth_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE metrictruth_app IN SCHEMA reporting GRANT SELECT ON TABLES TO metrictruth_reader;
ALTER ROLE metrictruth_reader SET default_transaction_read_only = on;
ALTER ROLE metrictruth_reader SET statement_timeout = '5000ms';

