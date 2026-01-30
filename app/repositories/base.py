from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.models.measurement import MeasurementRecord, MeasurementSummaryRecord


class MeasurementRepository(Protocol):
    def ping(self) -> None: ...

    def write_measurement(
        self, *, device_id: str, readings: dict[str, float], timestamp: datetime
    ) -> None: ...

    def query_measurements(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
        limit: int,
    ) -> list[MeasurementRecord]: ...

    def query_summary(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
    ) -> MeasurementSummaryRecord: ...

