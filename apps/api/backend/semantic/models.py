from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ALLOWED_SOURCES = frozenset({
    "campaigns",
    "daily_campaign_performance",
    "customer_acquisitions",
    "operating_expenses_monthly",
})

ALLOWED_MEASURES = frozenset({
    "total_paid_media_spend",
    "paid_attributed_new_customers",
    "total_valid_new_customers",
    "total_loaded_acquisition_spend",
    "total_ad_clicks",
    "total_ad_impressions",
    "paid_attributed_revenue",
})


class FormulaSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numerator: str
    denominator: str
    aggregation: Literal["ratio", "percentage"]


class AttributionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    lookback_days: int = Field(ge=0, le=365)


class FreshnessSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    maximum_age_hours: int = Field(ge=1, le=720)


class CertifiedMetricSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    ambiguity_group: str | None = None
    description: str
    formula: FormulaSpec
    unit: Literal["USD", "PERCENT", "RATIO", "COUNT"]
    grain: Literal["daily", "weekly", "monthly"]
    attribution: AttributionSpec
    time_dimension: Literal["report_date", "acquired_at"]
    dimensions: list[Literal["campaign", "channel", "date"]]
    sources: list[str]
    exclusions: list[str] = Field(default_factory=list)
    driver_metrics: list[str] = Field(default_factory=list)
    freshness: FreshnessSpec
    timezone: str = "America/New_York"
    owner: str
    status: Literal["draft", "approved", "retired"]
    version: int = Field(ge=1)

    def validate_semantic_integrity(self) -> None:
        if self.formula.numerator not in ALLOWED_MEASURES:
            raise ValueError(f"Unsupported numerator measure: {self.formula.numerator}")
        if self.formula.denominator not in ALLOWED_MEASURES:
            raise ValueError(f"Unsupported denominator measure: {self.formula.denominator}")
        unknown_sources = [s for s in self.sources if s not in ALLOWED_SOURCES]
        if unknown_sources:
            raise ValueError(f"Unauthorized sources in metric {self.metric_id}: {unknown_sources}")

