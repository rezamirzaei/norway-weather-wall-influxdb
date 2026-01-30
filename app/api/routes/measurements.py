from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import ReadUser, WriteUser, get_measurement_repository
from app.repositories.base import MeasurementRepository
from app.schemas.measurements import (
    DEVICE_ID_PATTERN,
    METRIC_PATTERN,
    MeasurementCreate,
    MeasurementRead,
    MeasurementSummary,
    MeasurementWriteResponse,
)
from app.services.measurements import MeasurementService

router = APIRouter(prefix="/measurements")


def get_service(
    repo: Annotated[MeasurementRepository, Depends(get_measurement_repository)],
) -> MeasurementService:
    return MeasurementService(repo)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post(
    "",
    response_model=MeasurementWriteResponse,
    status_code=status.HTTP_201_CREATED,
)
def write_measurement(
    _: WriteUser,
    payload: MeasurementCreate,
    service: Annotated[MeasurementService, Depends(get_service)],
) -> MeasurementWriteResponse:
    try:
        written_at = service.write_measurement(payload)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - normalize storage failures
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return MeasurementWriteResponse(written_at=written_at)


@router.get("", response_model=list[MeasurementRead])
def list_measurements(
    _: ReadUser,
    device_id: Annotated[str, Query(min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)],
    metric: Annotated[str, Query(min_length=1, max_length=64, pattern=METRIC_PATTERN)],
    service: Annotated[MeasurementService, Depends(get_service)],
    start: Annotated[datetime | None, Query()] = None,
    stop: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[MeasurementRead]:
    start_dt = _to_utc(start) if start else datetime.now(tz=timezone.utc) - timedelta(hours=1)
    stop_dt = _to_utc(stop) if stop else datetime.now(tz=timezone.utc)
    if start_dt > stop_dt:
        raise HTTPException(status_code=400, detail="'start' must be <= 'stop'")
    try:
        records = service.list_measurements(
            device_id=device_id, metric=metric, start=start_dt, stop=stop_dt, limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - normalize storage failures
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return [MeasurementRead.model_validate(r.__dict__) for r in records]


@router.get("/summary", response_model=MeasurementSummary)
def summarize_measurements(
    _: ReadUser,
    device_id: Annotated[str, Query(min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)],
    metric: Annotated[str, Query(min_length=1, max_length=64, pattern=METRIC_PATTERN)],
    service: Annotated[MeasurementService, Depends(get_service)],
    start: Annotated[datetime | None, Query()] = None,
    stop: Annotated[datetime | None, Query()] = None,
) -> MeasurementSummary:
    start_dt = _to_utc(start) if start else datetime.now(tz=timezone.utc) - timedelta(hours=1)
    stop_dt = _to_utc(stop) if stop else datetime.now(tz=timezone.utc)
    if start_dt > stop_dt:
        raise HTTPException(status_code=400, detail="'start' must be <= 'stop'")
    try:
        summary = service.summarize_measurements(
            device_id=device_id, metric=metric, start=start_dt, stop=stop_dt
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - normalize storage failures
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return MeasurementSummary.model_validate(summary.__dict__)


@router.get("/health", tags=["meta"])
def health(
    repo: Annotated[MeasurementRepository, Depends(get_measurement_repository)],
) -> dict[str, str]:
    try:
        repo.ping()
    except Exception as e:  # noqa: BLE001 - expose as 503 without leaking internals
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return {"status": "ok"}
