from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.models.weather import WeatherObservation, WeatherTemperaturePoint, WeatherTemperatureSummary


class WeatherRepository(Protocol):
    def ping(self) -> None: ...

    def write_observation(self, observation: WeatherObservation) -> None: ...

    def query_latest(
        self, *, cities: list[str], start: datetime, stop: datetime
    ) -> list[WeatherObservation]: ...

    def query_temperature_series(
        self,
        *,
        cities: list[str],
        start: datetime,
        stop: datetime,
        window_seconds: int,
    ) -> list[WeatherTemperaturePoint]: ...

    def query_temperature_summary(
        self, *, cities: list[str], start: datetime, stop: datetime
    ) -> list[WeatherTemperatureSummary]: ...
