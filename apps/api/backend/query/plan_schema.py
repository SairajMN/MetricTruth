import calendar
from datetime import date, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

AllowedDimension = Literal["campaign", "channel", "date"]
AllowedOrderBy = Literal[
    "metric_desc",
    "metric_asc",
    "absolute_change_desc",
    "percentage_change_desc",
    "spend_desc",
    "customers_desc",
]


class Period(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_window(self) -> "Period":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("Analysis period exceeds maximum permitted window of 366 days.")
        return self


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["previous_period", "previous_month", "previous_year", "none"] = "none"


class MetricQueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_id: str
    period: Period
    comparison: Comparison = Field(default_factory=Comparison)
    group_by: list[AllowedDimension] = Field(default_factory=list)
    filters: dict[str, str | list[str]] = Field(default_factory=dict)
    order_by: list[AllowedOrderBy] = Field(default_factory=lambda: ["metric_desc"])
    limit: int = Field(default=20, ge=1, le=100)
    include_driver_analysis: bool = True


def resolve_comparison_period(period: Period, comparison_type: str) -> Period | None:
    if comparison_type == "none":
        return None
    if comparison_type in ("previous_month", "previous_period"):
        first_of_cur = period.start_date.replace(day=1)
        if period.start_date.day == 1:
            prev_end = first_of_cur - timedelta(days=1)
            prev_start = prev_end.replace(day=1)
            return Period(start_date=prev_start, end_date=prev_end)
        span_days = (period.end_date - period.start_date).days + 1
        prev_end = period.start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span_days - 1)
        return Period(start_date=prev_start, end_date=prev_end)
    if comparison_type == "previous_year":
        prev_year = period.start_date.year - 1
        end_day = min(period.end_date.day, calendar.monthrange(prev_year, period.end_date.month)[1])
        return Period(
            start_date=period.start_date.replace(year=prev_year),
            end_date=period.end_date.replace(year=prev_year, day=end_day),
        )
    return None

