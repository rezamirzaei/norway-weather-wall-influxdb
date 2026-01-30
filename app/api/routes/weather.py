from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import WeatherReadUser, WeatherWriteUser, get_weather_service
from app.schemas.weather import WeatherLatest, WeatherRefreshResponse
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
