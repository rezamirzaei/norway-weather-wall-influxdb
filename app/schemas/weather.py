from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WeatherLatest(BaseModel):
    city: str = Field(min_length=1, max_length=64)
    lat: float
    lon: float
    timestamp: datetime

    air_temperature: float | None = None
    relative_humidity: float | None = None
    air_pressure_at_sea_level: float | None = None
    wind_speed: float | None = None
    wind_from_direction: float | None = None
    cloud_area_fraction: float | None = None
    precipitation_amount_1h: float | None = None
    symbol_code: str | None = None


class WeatherRefreshResponse(BaseModel):
    requested: int = Field(ge=0)
    stored: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: bool = False
    retry_after_seconds: int | None = Field(default=None, ge=1)
    cities: list[str] = Field(default_factory=list)


class WeatherTemperaturePoint(BaseModel):
    city: str = Field(min_length=1, max_length=64)
    timestamp: datetime
    value: float


class WeatherTemperatureSummary(BaseModel):
    city: str = Field(min_length=1, max_length=64)
    start: datetime
    stop: datetime
    count: int = Field(ge=0)
    min: float | None = None
    max: float | None = None
    avg: float | None = None
    first: float | None = None
    last: float | None = None
