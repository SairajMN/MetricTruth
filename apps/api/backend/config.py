from datetime import date
from decimal import Decimal
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
(ROOT_DIR / "data").mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_database_url: str = f"sqlite+aiosqlite:///{ROOT_DIR / 'data' / 'metrictruth.db'}"
    readonly_database_url: str = f"sqlite+aiosqlite:///{ROOT_DIR / 'data' / 'metrictruth.db'}"
    redis_url: str = "redis://localhost:6379/0"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_fast: str = "google/gemini-2.5-flash"
    model_synthesis: str = "google/gemini-2.5-flash"
    llm_mode: str = "auto"

    viewer_api_key: str = "mt-viewer-key-2026"
    analyst_api_key: str = "mt-analyst-key-2026"
    admin_api_key: str = "mt-admin-key-2026"

    reporting_timezone: str = "America/New_York"
    reference_today: date = date(2026, 11, 30)
    otel_capture_content: bool = False

    max_llm_calls_per_run: int = 5
    max_tokens_per_run: int = 12000
    max_cost_usd_per_run: Decimal = Decimal("0.05")
    sql_timeout_ms: int = 5000


settings = Settings()
