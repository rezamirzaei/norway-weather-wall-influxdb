from __future__ import annotations

from datetime import datetime, timezone

from app.models.measurement import MeasurementRecord, MeasurementSummaryRecord
from app.repositories.base import MeasurementRepository
from app.schemas.measurements import MeasurementCreate


class MeasurementService:
    def __init__(self, repo: MeasurementRepository) -> None:
        self._repo = repo

    def write_measurement(self, payload: MeasurementCreate) -> datetime:
        timestamp = payload.timestamp or datetime.now(tz=timezone.utc)
        self._repo.write_measurement(
            device_id=payload.device_id, readings=payload.readings, timestamp=timestamp
        )
        return timestamp

    def list_measurements(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
        limit: int,
    ) -> list[MeasurementRecord]:
        return self._repo.query_measurements(
            device_id=device_id, metric=metric, start=start, stop=stop, limit=limit
        )

    def summarize_measurements(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
    ) -> MeasurementSummaryRecord:
        return self._repo.query_summary(
            device_id=device_id, metric=metric, start=start, stop=stop
        )

