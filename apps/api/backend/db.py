import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from backend.config import settings

REPORTING_ALLOWED_RELATIONS = frozenset({
    "v_campaigns",
    "v_daily_campaign_performance",
    "v_customer_acquisitions",
    "v_operating_expenses",
    "campaigns",
    "daily_campaign_performance",
    "customer_acquisitions",
    "operating_expenses_monthly",
    "sqlite_master",
    "sqlite_schema",
})

SQLITE_ALLOWED_ACTIONS = frozenset({
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
})


def _sqlite_readonly_authorizer(
    action: int, arg1: str | None, arg2: str | None, dbname: str | None, source: str | None
) -> int:
    if action not in SQLITE_ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_READ and arg1:
        rel = arg1.lower()
        if rel not in REPORTING_ALLOWED_RELATIONS:
            return sqlite3.SQLITE_DENY
        if source is None and not rel.startswith("v_") and not rel.startswith("sqlite_"):
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def build_engines(
    app_url: str | None = None, readonly_url: str | None = None
) -> tuple[AsyncEngine, AsyncEngine]:
    resolved_app = app_url or settings.app_database_url
    resolved_ro = readonly_url or settings.readonly_database_url

    app_eng = create_async_engine(resolved_app, future=True)
    ro_eng = create_async_engine(resolved_ro, future=True)

    if resolved_ro.startswith("sqlite"):
        @event.listens_for(ro_eng.sync_engine, "connect")
        def _lock_down_sqlite_ro(dbapi_conn, _conn_record) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA query_only = ON;")
            cursor.close()
            aio_conn = getattr(dbapi_conn, "_connection", dbapi_conn)
            raw_sqlite = getattr(aio_conn, "_conn", aio_conn)
            if hasattr(raw_sqlite, "set_authorizer"):
                raw_sqlite.set_authorizer(_sqlite_readonly_authorizer)

    return app_eng, ro_eng


app_engine, readonly_engine = build_engines()


@asynccontextmanager
async def get_app_connection(engine: AsyncEngine | None = None) -> AsyncIterator[AsyncConnection]:
    target = engine or app_engine
    async with target.begin() as conn:
        yield conn


@asynccontextmanager
async def get_readonly_connection(
    engine: AsyncEngine | None = None, timeout_ms: int | None = None
) -> AsyncIterator[AsyncConnection]:
    target = engine or readonly_engine
    limit_ms = timeout_ms or settings.sql_timeout_ms
    async with target.connect() as conn:
        if target.dialect.name == "postgresql":
            await conn.execute(text("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            await conn.execute(text(f"SET LOCAL statement_timeout = '{int(limit_ms)}ms'"))
            await conn.execute(text("SET LOCAL search_path TO reporting"))
            try:
                yield conn
            finally:
                await conn.execute(text("COMMIT"))
        else:
            yield conn
