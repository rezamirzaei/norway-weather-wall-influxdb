from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.models.weather import City, WeatherObservation

METNO_LOCATIONFORECAST_COMPACT_URL = (
    "https://api.met.no/weatherapi/locationforecast/2.0/compact"
)


def _parse_time(value: str) -> datetime:
    # Example: "2026-01-30T22:00:00Z"
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class MetNoClient:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        base_url: str = METNO_LOCATIONFORECAST_COMPACT_URL,
    ) -> None:
        self._base_url = base_url
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def fetch_current_observation(self, city: City) -> WeatherObservation:
        resp = self._client.get(self._base_url, params={"lat": city.lat, "lon": city.lon})
        resp.raise_for_status()
        payload = resp.json()

        ts = self._extract_timeseries_now(payload)
        timestamp = _parse_time(ts["time"])

        data: dict[str, Any] = ts.get("data", {})
        instant_details: dict[str, Any] = (
            data.get("instant", {}).get("details", {}) if isinstance(data, dict) else {}
        )

        next_1h: dict[str, Any] = data.get("next_1_hours", {}) if isinstance(data, dict) else {}
        next_1h_details: dict[str, Any] = (
            next_1h.get("details", {}) if isinstance(next_1h, dict) else {}
        )
        next_1h_summary: dict[str, Any] = (
            next_1h.get("summary", {}) if isinstance(next_1h, dict) else {}
        )

        return WeatherObservation(
            city=city.name,
            lat=float(city.lat),
            lon=float(city.lon),
            timestamp=timestamp,
            air_temperature=_float_or_none(instant_details.get("air_temperature")),
            relative_humidity=_float_or_none(instant_details.get("relative_humidity")),
            air_pressure_at_sea_level=_float_or_none(
                instant_details.get("air_pressure_at_sea_level")
            ),
            wind_speed=_float_or_none(instant_details.get("wind_speed")),
            wind_from_direction=_float_or_none(instant_details.get("wind_from_direction")),
            cloud_area_fraction=_float_or_none(instant_details.get("cloud_area_fraction")),
            precipitation_amount_1h=_float_or_none(
                next_1h_details.get("precipitation_amount")
            ),
            symbol_code=_str_or_none(next_1h_summary.get("symbol_code")),
        )

    @staticmethod
    def _extract_timeseries_now(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            series = payload["properties"]["timeseries"]
        except Exception as e:  # noqa: BLE001
            raise ValueError("Unexpected MET Norway response shape") from e
        if not isinstance(series, list) or not series:
            raise ValueError("MET Norway response contained no timeseries")
        first = series[0]
        if not isinstance(first, dict) or "time" not in first:
            raise ValueError("Unexpected timeseries entry shape")
        return first


def _float_or_none(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)

