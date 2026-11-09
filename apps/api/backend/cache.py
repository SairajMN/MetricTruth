import json
import time
from typing import Any
from backend.config import settings

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None


class WatermarkCache:
    def __init__(self, redis_url: str | None = None, default_ttl_s: int = 900) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._default_ttl_s = default_ttl_s
        self._mem: dict[str, tuple[float, str]] = {}
        self._redis_client: Any = None
        self._redis_failed = False

    async def _client(self) -> Any:
        if self._redis_failed or aioredis is None or not self._redis_url:
            return None
        if self._redis_client is None:
            try:
                client = aioredis.from_url(
                    self._redis_url, encoding="utf-8", decode_responses=True, socket_connect_timeout=0.3
                )
                await client.ping()
                self._redis_client = client
            except Exception:
                self._redis_failed = True
                return None
        return self._redis_client

    async def get_json(self, key: str) -> dict[str, Any] | None:
        client = await self._client()
        if client is not None:
            try:
                raw = await client.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                pass
        entry = self._mem.get(key)
        if not entry:
            return None
        expires_at, raw = entry
        if time.monotonic() > expires_at:
            self._mem.pop(key, None)
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: dict[str, Any], ttl_s: int | None = None) -> None:
        ttl = ttl_s or self._default_ttl_s
        serialized = json.dumps(value, default=str)
        client = await self._client()
        if client is not None:
            try:
                await client.setex(key, ttl, serialized)
                return
            except Exception:
                pass
        # shortcut: 1024 in-process cache entries when Redis is offline, switch to Redis in multi-worker prod
        if len(self._mem) >= 1024:
            oldest = next(iter(self._mem))
            self._mem.pop(oldest, None)
        self._mem[key] = (time.monotonic() + ttl, serialized)

    async def clear(self) -> None:
        self._mem.clear()
        client = await self._client()
        if client is not None:
            try:
                await client.flushdb()
            except Exception:
                pass


cache = WatermarkCache()

