from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.measurement import MeasurementRecord, MeasurementSummaryRecord
from app.models.weather import (
    City,
    WeatherObservation,
    WeatherTemperaturePoint,
    WeatherTemperatureSummary,
)


@dataclass
class FakeMeasurementRepository:
    _records: list[MeasurementRecord]

    def __init__(self) -> None:
        self._records = []

    def ping(self) -> None:
        return None

    def write_measurement(
        self, *, device_id: str, readings: dict[str, float], timestamp: datetime
    ) -> None:
        for metric, value in readings.items():
            self._records.append(
                MeasurementRecord(
                    device_id=device_id,
                    metric=metric,
                    value=float(value),
                    timestamp=timestamp,
                )
            )

    def query_measurements(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
        limit: int,
    ) -> list[MeasurementRecord]:
        filtered = [
            r
            for r in self._records
            if r.device_id == device_id
            and r.metric == metric
            and start <= r.timestamp <= stop
        ]
        filtered.sort(key=lambda r: r.timestamp, reverse=True)
        return filtered[:limit]

    def query_summary(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
    ) -> MeasurementSummaryRecord:
        rows = self.query_measurements(
            device_id=device_id, metric=metric, start=start, stop=stop, limit=10**9
        )
        if not rows:
            return MeasurementSummaryRecord(
                device_id=device_id,
                metric=metric,
                start=start,
                stop=stop,
                count=0,
                min=None,
                max=None,
                avg=None,
            )
        values = [r.value for r in rows]
        return MeasurementSummaryRecord(
            device_id=device_id,
            metric=metric,
            start=start,
            stop=stop,
            count=len(values),
            min=min(values),
            max=max(values),
            avg=sum(values) / len(values),
        )


@dataclass
class FakeWeatherRepository:
    _records: list[WeatherObservation]

    def __init__(self) -> None:
        self._records = []

    def ping(self) -> None:
        return None

    def write_observation(self, observation: WeatherObservation) -> None:
        self._records.append(observation)

    def query_latest(
        self, *, cities: list[str], start: datetime, stop: datetime
    ) -> list[WeatherObservation]:
        results: list[WeatherObservation] = []
        for city in cities:
            candidates = [
                r
                for r in self._records
                if r.city == city and start <= r.timestamp <= stop
            ]
            if not candidates:
                continue
            candidates.sort(key=lambda r: r.timestamp, reverse=True)
            results.append(candidates[0])
        results.sort(key=lambda r: r.city)
        return results

    def query_temperature_series(
        self,
        *,
        cities: list[str],
        start: datetime,
        stop: datetime,
        window_seconds: int,
    ) -> list[WeatherTemperaturePoint]:
        window_seconds = max(int(window_seconds), 1)
        buckets: dict[tuple[str, int], list[float]] = {}
        for r in self._records:
            if r.city not in cities:
                continue
            if r.air_temperature is None:
                continue
            if not (start <= r.timestamp <= stop):
                continue
            idx = int((r.timestamp - start).total_seconds() // window_seconds)
            buckets.setdefault((r.city, idx), []).append(float(r.air_temperature))

        points: list[WeatherTemperaturePoint] = []
        for (city, idx), values in buckets.items():
            ts = start + timedelta(seconds=idx * window_seconds)
            points.append(
                WeatherTemperaturePoint(
                    city=city,
                    timestamp=ts,
                    value=sum(values) / len(values),
                )
            )
        points.sort(key=lambda p: (p.city, p.timestamp))
        return points

    def query_temperature_summary(
        self, *, cities: list[str], start: datetime, stop: datetime
    ) -> list[WeatherTemperatureSummary]:
        rows: list[WeatherTemperatureSummary] = []
        for city in cities:
            values = [
                r
                for r in self._records
                if r.city == city
                and r.air_temperature is not None
                and start <= r.timestamp <= stop
            ]
            if not values:
                continue
            values.sort(key=lambda r: r.timestamp)
            temps = [float(r.air_temperature) for r in values if r.air_temperature is not None]
            if not temps:
                continue
            rows.append(
                WeatherTemperatureSummary(
                    city=city,
                    start=start,
                    stop=stop,
                    count=len(temps),
                    min=min(temps),
                    max=max(temps),
                    avg=sum(temps) / len(temps),
                    first=temps[0],
                    last=temps[-1],
                )
            )
        rows.sort(key=lambda r: r.city)
        return rows


class FakeMetNoClient:
    def close(self) -> None:
        return None

    def fetch_current_observation(self, city: City) -> WeatherObservation:
        now = datetime.now(tz=timezone.utc).replace(microsecond=0)
        # Deterministic-ish values based on city name.
        base = float(sum(ord(c) for c in city.name) % 20)
        return WeatherObservation(
            city=city.name,
            lat=city.lat,
            lon=city.lon,
            timestamp=now - timedelta(minutes=1),
            air_temperature=5.0 + base,
            relative_humidity=50.0,
            air_pressure_at_sea_level=1010.0,
            wind_speed=3.0,
            wind_from_direction=180.0,
            cloud_area_fraction=30.0,
            precipitation_amount_1h=0.0,
            symbol_code="clearsky_day",
        )
