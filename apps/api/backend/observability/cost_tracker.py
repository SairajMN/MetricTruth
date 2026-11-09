from decimal import Decimal
from pydantic import BaseModel, Field
from backend.config import settings


class ModelCallUsage(BaseModel):
    component: str
    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: Decimal = Decimal("0.000000")
    duration_ms: float = 0.0
    is_billed_provider_cost: bool = False


class RunBudgetLedger(BaseModel):
    max_calls: int = Field(default_factory=lambda: settings.max_llm_calls_per_run)
    max_tokens: int = Field(default_factory=lambda: settings.max_tokens_per_run)
    max_cost_usd: Decimal = Field(default_factory=lambda: settings.max_cost_usd_per_run)

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    model_calls: int = 0
    retries: int = 0
    total_cost_usd: Decimal = Decimal("0.000000")
    calls: list[ModelCallUsage] = Field(default_factory=list)

    def check_can_invoke(self) -> None:
        if self.model_calls >= self.max_calls:
            raise RuntimeError(f"LLM call budget exceeded (max {self.max_calls} calls).")
        if (self.input_tokens + self.output_tokens) >= self.max_tokens:
            raise RuntimeError(f"Token budget exceeded (max {self.max_tokens} tokens).")
        if self.total_cost_usd >= self.max_cost_usd:
            raise RuntimeError(f"Cost budget exceeded (max ${self.max_cost_usd}).")

    def record_call(self, usage: ModelCallUsage) -> None:
        self.model_calls += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cached_tokens += usage.cached_tokens
        self.total_cost_usd = (self.total_cost_usd + usage.cost_usd).quantize(Decimal("0.000001"))
        self.calls.append(usage)

