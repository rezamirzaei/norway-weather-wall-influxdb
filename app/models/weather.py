from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class City:
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class WeatherObservation:
    city: str
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


@dataclass(frozen=True)
class WeatherTemperaturePoint:
    city: str
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class WeatherTemperatureSummary:
    city: str
    start: datetime
    stop: datetime
    count: int
    min: float | None
    max: float | None
    avg: float | None
    first: float | None
    last: float | None
