from __future__ import annotations

from influxdb_client import InfluxDBClient

from app.core.config import Settings


def create_influx_client(settings: Settings) -> InfluxDBClient:
    return InfluxDBClient(
        url=str(settings.influx_url),
        token=settings.influx_token,
        org=settings.influx_org,
        timeout=settings.influx_timeout_ms,
    )

