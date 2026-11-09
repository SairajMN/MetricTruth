ALLOWED_REPORTING_VIEWS = frozenset({
    "v_campaigns",
    "v_daily_campaign_performance",
    "v_customer_acquisitions",
    "v_operating_expenses",
})

ALLOWED_FILTER_FIELDS = frozenset({"channel", "campaign"})

FORBIDDEN_SQL_FUNCTIONS = frozenset({
    "pg_sleep",
    "dblink",
    "dblink_exec",
    "lo_import",
    "lo_export",
    "pg_read_file",
    "pg_ls_dir",
    "load_extension",
})

MAX_QUERY_LIMIT = 100
MAX_WINDOW_DAYS = 366
MAX_CTES = 6
MAX_JOINS = 6

