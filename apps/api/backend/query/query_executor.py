from datetime import date, datetime
import time
from typing import Any
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.db import get_readonly_connection, readonly_engine
from backend.query.sql_compiler import CompiledQueryArtifact


class RawQueryExecutionResult(BaseModel):
    rows: list[dict[str, Any]]
    row_count: int
    execution_ms: float


class QueryExecutor:
    def __init__(self, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or readonly_engine

    async def execute(self, artifact: CompiledQueryArtifact) -> RawQueryExecutionResult:
        t0 = time.perf_counter()
        is_sqlite = self._engine.dialect.name == "sqlite"
        exec_params: dict[str, Any] = {}
        for k, v in artifact.bound_params.items():
            if is_sqlite and isinstance(v, datetime):
                exec_params[k] = v.strftime("%Y-%m-%d %H:%M:%S.%f")
            elif is_sqlite and isinstance(v, date):
                exec_params[k] = v.isoformat()
            else:
                exec_params[k] = v

        async with get_readonly_connection(self._engine) as conn:
            result = await conn.execute(text(artifact.sql_text), exec_params)
            mappings = result.mappings().all()
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        rows = [dict(r) for r in mappings]
        return RawQueryExecutionResult(
            rows=rows,
            row_count=len(rows),
            execution_ms=elapsed_ms,
        )
