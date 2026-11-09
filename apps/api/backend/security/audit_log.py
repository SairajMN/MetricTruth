from datetime import datetime, timezone
import json
from typing import Any
import uuid
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.db import app_engine
from backend.models.tables import audit_events


async def log_security_event(
    actor_role: str,
    event_type: str,
    severity: str,
    resource: str,
    details: dict[str, Any],
    engine: AsyncEngine | None = None,
) -> str:
    target = engine or app_engine
    audit_id = f"AUD_{uuid.uuid4().hex[:10].upper()}"
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    async with target.begin() as conn:
        await conn.execute(
            audit_events.insert().values(
                audit_id=audit_id,
                actor_role=actor_role,
                event_type=event_type,
                severity=severity,
                resource=resource,
                details_json=json.dumps(details, default=str),
                created_at=now_utc,
            )
        )
    return audit_id

