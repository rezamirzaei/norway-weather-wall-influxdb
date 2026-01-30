from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from app.models.weather import WeatherObservation
from app.repositories.flux import flux_str, to_rfc3339

WEATHER_FIELDS = [
    "lat",
    "lon",
    "air_temperature",
    "relative_humidity",
    "air_pressure_at_sea_level",
    "wind_speed",
    "wind_from_direction",
    "cloud_area_fraction",
    "precipitation_amount_1h",
    "symbol_code",
]


class InfluxWeatherRepository:
    def __init__(
        self,
        *,
        client: InfluxDBClient,
        org: str,
        bucket: str,
        measurement: str,
        timeout_ms: int,
    ) -> None:
        self._client = client
        self._org = org
        self._bucket = bucket
        self._measurement = measurement
        self._timeout_ms = timeout_ms

    def ping(self) -> None:
        self._client.ping()

    def write_observation(self, observation: WeatherObservation) -> None:
        ts = observation.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        point = (
            Point(self._measurement)
            .tag("city", observation.city)
            .tag("country", "NO")
            .field("lat", float(observation.lat))
            .field("lon", float(observation.lon))
        )

        for name, value in (
            ("air_temperature", observation.air_temperature),
            ("relative_humidity", observation.relative_humidity),
            ("air_pressure_at_sea_level", observation.air_pressure_at_sea_level),
            ("wind_speed", observation.wind_speed),
            ("wind_from_direction", observation.wind_from_direction),
            ("cloud_area_fraction", observation.cloud_area_fraction),
            ("precipitation_amount_1h", observation.precipitation_amount_1h),
        ):
            if value is not None:
                point = point.field(name, float(value))

        if observation.symbol_code is not None:
            point = point.field("symbol_code", observation.symbol_code)

        point = point.time(ts, WritePrecision.NS)
        write_api = self._client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=self._bucket, org=self._org, record=point)

    def query_latest(
        self, *, cities: list[str], start: datetime, stop: datetime
    ) -> list[WeatherObservation]:
        if not cities:
            return []

        city_predicate = " or ".join([f'r["city"] == {flux_str(c)}' for c in cities])
        field_predicate = " or ".join(
            [f'r["_field"] == {flux_str(f)}' for f in WEATHER_FIELDS]
        )
        keep_columns = ", ".join([flux_str("_time"), flux_str("city")] + [flux_str(f) for f in WEATHER_FIELDS])

        query = f"""
from(bucket: {flux_str(self._bucket)})
  |> range(start: time(v: {flux_str(to_rfc3339(start))}), stop: time(v: {flux_str(to_rfc3339(stop))}))
  |> filter(fn: (r) => r["_measurement"] == {flux_str(self._measurement)})
  |> filter(fn: (r) => {city_predicate})
  |> filter(fn: (r) => {field_predicate})
  |> group(columns: ["city", "_field"])
  |> last()
  |> pivot(rowKey: ["_time", "city"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: [{keep_columns}])
  |> sort(columns: ["city"])
"""

        query_api = self._client.query_api()
        tables = query_api.query(query=query, org=self._org)

        results: list[WeatherObservation] = []
        for table in tables:
            for record in table.records:
                values: dict[str, Any] = record.values
                city = values.get("city")
                ts = record.get_time()
                if not isinstance(city, str) or ts is None:
                    continue
                results.append(
                    WeatherObservation(
                        city=city,
                        lat=_float_or_default(values.get("lat"), 0.0),
                        lon=_float_or_default(values.get("lon"), 0.0),
                        timestamp=ts,
                        air_temperature=_float_or_none(values.get("air_temperature")),
                        relative_humidity=_float_or_none(values.get("relative_humidity")),
                        air_pressure_at_sea_level=_float_or_none(
                            values.get("air_pressure_at_sea_level")
                        ),
                        wind_speed=_float_or_none(values.get("wind_speed")),
                        wind_from_direction=_float_or_none(values.get("wind_from_direction")),
                        cloud_area_fraction=_float_or_none(values.get("cloud_area_fraction")),
                        precipitation_amount_1h=_float_or_none(
                            values.get("precipitation_amount_1h")
                        ),
                        symbol_code=_str_or_none(values.get("symbol_code")),
                    )
                )
        return results


def _float_or_none(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _float_or_default(v: Any, default: float) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)

