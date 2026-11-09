import asyncio
from collections import defaultdict
from typing import Any
from backend.core.execution_state import StepTraceEvent


class EventBus:
    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    async def publish_step(self, run_id: str, event: StepTraceEvent) -> None:
        payload = event.model_dump(mode="json")
        self._history[run_id].append(payload)
        for q in list(self._subscribers.get(run_id, [])):
            await q.put(payload)

    async def publish_done(self, run_id: str, status: str) -> None:
        payload = {"type": "RUN_COMPLETE", "run_id": run_id, "status": status}
        self._history[run_id].append(payload)
        for q in list(self._subscribers.get(run_id, [])):
            await q.put(payload)

    def get_history(self, run_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(run_id, []))

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        for past in self._history.get(run_id, []):
            q.put_nowait(past)
        self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        if q in self._subscribers.get(run_id, []):
            self._subscribers[run_id].remove(q)


event_bus = EventBus()

