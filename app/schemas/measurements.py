from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

DEVICE_ID_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9:_-]{0,63}$"
METRIC_PATTERN = r"^[a-zA-Z][a-zA-Z0-9:_-]{0,63}$"

DeviceId = Annotated[str, Field(pattern=DEVICE_ID_PATTERN)]
MetricName = Annotated[str, Field(pattern=METRIC_PATTERN)]


class MeasurementCreate(BaseModel):
    device_id: DeviceId
    timestamp: datetime | None = None
    readings: dict[MetricName, float] = Field(min_length=1, max_length=32)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_to_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("readings")
    @classmethod
    def _validate_readings(cls, v: dict[str, float]) -> dict[str, float]:
        for key, value in v.items():
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"Invalid value for '{key}' (must be finite number).")
        return v


class MeasurementWriteResponse(BaseModel):
    written_at: datetime


class MeasurementRead(BaseModel):
    device_id: DeviceId
    metric: MetricName
    value: float
    timestamp: datetime


class MeasurementSummary(BaseModel):
    device_id: DeviceId
    metric: MetricName
    start: datetime
    stop: datetime
    count: int = Field(ge=0)
    min: float | None = None
    max: float | None = None
    avg: float | None = None

