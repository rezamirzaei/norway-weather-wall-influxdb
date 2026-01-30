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

