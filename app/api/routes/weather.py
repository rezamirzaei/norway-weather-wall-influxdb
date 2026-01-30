from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import WeatherReadUser, WeatherWriteUser, get_weather_service
from app.schemas.weather import (
    WeatherLatest,
    WeatherRefreshResponse,
    WeatherTemperaturePoint,
    WeatherTemperatureSummary,
)
from app.services.weather import WeatherIngestionService

router = APIRouter(prefix="/weather")


@router.post("/refresh", response_model=WeatherRefreshResponse)
def refresh_weather(
    _: WeatherWriteUser,
    service: Annotated[WeatherIngestionService, Depends(get_weather_service)],
    force: bool = False,
) -> WeatherRefreshResponse:
    try:
        result = service.refresh(force=force)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weather provider unavailable",
        ) from e
    return WeatherRefreshResponse(
        requested=result.requested,
        stored=result.stored,
        failed=result.failed,
        skipped=result.skipped,
        retry_after_seconds=result.retry_after_seconds,
        cities=result.cities,
    )


@router.get("/latest", response_model=list[WeatherLatest])
def latest_weather(
    _: WeatherReadUser,
    service: Annotated[WeatherIngestionService, Depends(get_weather_service)],
) -> list[WeatherLatest]:
    try:
        rows = service.latest()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return [WeatherLatest.model_validate(r.__dict__) for r in rows]


@router.get("/temperature/summary", response_model=list[WeatherTemperatureSummary])
def temperature_summary(
    _: WeatherReadUser,
    service: Annotated[WeatherIngestionService, Depends(get_weather_service)],
    hours: Annotated[int, Query(ge=1, le=24 * 14)] = 24,
) -> list[WeatherTemperatureSummary]:
    try:
        rows = service.temperature_summary(hours=hours)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return [WeatherTemperatureSummary.model_validate(r.__dict__) for r in rows]


@router.get("/temperature/trend", response_model=list[WeatherTemperaturePoint])
def temperature_trend(
    _: WeatherReadUser,
    service: Annotated[WeatherIngestionService, Depends(get_weather_service)],
    hours: Annotated[int, Query(ge=1, le=24 * 2)] = 1,
    window_seconds: Annotated[int, Query(ge=1, le=3600)] = 60,
) -> list[WeatherTemperaturePoint]:
    try:
        rows = service.temperature_trend(hours=hours, window_seconds=window_seconds)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return [WeatherTemperaturePoint.model_validate(r.__dict__) for r in rows]
