from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MeasurementRecord:
    device_id: str
    metric: str
    value: float
    timestamp: datetime


@dataclass(frozen=True)
class MeasurementSummaryRecord:
    device_id: str
    metric: str
    start: datetime
    stop: datetime
    count: int
    min: float | None
    max: float | None
    avg: float | None

