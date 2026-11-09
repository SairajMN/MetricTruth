from decimal import Decimal
import json
import time
from typing import TypeVar
import httpx
from pydantic import BaseModel, ValidationError
from backend.config import settings
from backend.observability.cost_tracker import ModelCallUsage, RunBudgetLedger

T = TypeVar("T", bound=BaseModel)


class LLMRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        mode: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.openrouter_api_key
        self._base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self._mode = mode or settings.llm_mode
        self._transport = transport

    @property
    def is_live_enabled(self) -> bool:
        if self._mode == "deterministic_only":
            return False
        return bool(self._api_key)

    async def generate_structured(
        self,
        component: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        ledger: RunBudgetLedger,
        tier: str = "fast",
    ) -> T:
        ledger.check_can_invoke()
        model_name = settings.model_fast if tier == "fast" else settings.model_synthesis
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_err: Exception | None = None
        for attempt in range(2):
            if attempt > 0:
                ledger.retries += 1
                ledger.check_can_invoke()
            t0 = time.perf_counter()
            async with httpx.AsyncClient(
                timeout=15.0, transport=self._transport
            ) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_name,
                        "temperature": 0.0,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                    },
                )
                resp.raise_for_status()
                payload = resp.json()

            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            usage_raw = payload.get("usage") or {}
            in_tok = int(usage_raw.get("prompt_tokens") or 0)
            out_tok = int(usage_raw.get("completion_tokens") or 0)
            details = usage_raw.get("prompt_tokens_details") or {}
            cached_tok = int(details.get("cached_tokens") or 0)
            actual_cost = Decimal(str(usage_raw.get("cost") or "0.000000"))

            ledger.record_call(
                ModelCallUsage(
                    component=component,
                    model_name=model_name,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cached_tokens=cached_tok,
                    cost_usd=actual_cost,
                    duration_ms=elapsed_ms,
                    is_billed_provider_cost=("cost" in usage_raw),
                )
            )

            content_str = payload["choices"][0]["message"]["content"]
            try:
                return response_model.model_validate_json(content_str)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_err = exc
                messages.append({"role": "assistant", "content": content_str})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Fix JSON schema validation errors and return valid JSON only: {exc}",
                    }
                )

        raise ValueError(f"Structured output validation failed after retries: {last_err}")

