from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.models.weather import WeatherObservation


class WeatherRepository(Protocol):
    def ping(self) -> None: ...

    def write_observation(self, observation: WeatherObservation) -> None: ...

    def query_latest(
        self, *, cities: list[str], start: datetime, stop: datetime
    ) -> list[WeatherObservation]: ...

