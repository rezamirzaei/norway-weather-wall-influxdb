from __future__ import annotations

from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from app.models.measurement import MeasurementRecord, MeasurementSummaryRecord
from app.repositories.flux import flux_str, to_rfc3339


class InfluxMeasurementRepository:
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

    def write_measurement(
        self, *, device_id: str, readings: dict[str, float], timestamp: datetime
    ) -> None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        point = Point(self._measurement).tag("device_id", device_id)
        for metric, value in readings.items():
            point = point.field(metric, float(value))
        point = point.time(timestamp, WritePrecision.NS)

        write_api = self._client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=self._bucket, org=self._org, record=point)

    def query_measurements(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
        limit: int,
    ) -> list[MeasurementRecord]:
        query = f"""
from(bucket: {flux_str(self._bucket)})
  |> range(start: time(v: {flux_str(to_rfc3339(start))}), stop: time(v: {flux_str(to_rfc3339(stop))}))
  |> filter(fn: (r) => r["_measurement"] == {flux_str(self._measurement)})
  |> filter(fn: (r) => r["device_id"] == {flux_str(device_id)})
  |> filter(fn: (r) => r["_field"] == {flux_str(metric)})
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {int(limit)})
"""
        query_api = self._client.query_api()
        tables = query_api.query(query=query, org=self._org)

        results: list[MeasurementRecord] = []
        for table in tables:
            for record in table.records:
                ts = record.get_time()
                if ts is None:
                    continue
                results.append(
                    MeasurementRecord(
                        device_id=device_id,
                        metric=metric,
                        value=float(record.get_value()),
                        timestamp=ts,
                    )
                )
        return results

    def query_summary(
        self,
        *,
        device_id: str,
        metric: str,
        start: datetime,
        stop: datetime,
    ) -> MeasurementSummaryRecord:
        query = f"""
from(bucket: {flux_str(self._bucket)})
  |> range(start: time(v: {flux_str(to_rfc3339(start))}), stop: time(v: {flux_str(to_rfc3339(stop))}))
  |> filter(fn: (r) => r["_measurement"] == {flux_str(self._measurement)})
  |> filter(fn: (r) => r["device_id"] == {flux_str(device_id)})
  |> filter(fn: (r) => r["_field"] == {flux_str(metric)})
  |> keep(columns: ["_value"])
  |> reduce(
    identity: {{count: 0, sum: 0.0, min: 0.0, max: 0.0}},
    fn: (r, accumulator) => ({{
	      count: accumulator.count + 1,
	      sum: accumulator.sum + float(v: r._value),
	      min: if accumulator.count == 0 or float(v: r._value) < accumulator.min then float(v: r._value) else accumulator.min,
	      max: if accumulator.count == 0 or float(v: r._value) > accumulator.max then float(v: r._value) else accumulator.max,
	    }}),
	  )
  |> map(fn: (r) => ({{ r with avg: if r.count == 0 then 0.0 else r.sum / float(v: r.count) }}))
"""
        query_api = self._client.query_api()
        tables = query_api.query(query=query, org=self._org)

        if not tables or not tables[0].records:
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

        values = tables[0].records[0].values
        count = int(values.get("count", 0))
        if count <= 0:
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

        return MeasurementSummaryRecord(
            device_id=device_id,
            metric=metric,
            start=start,
            stop=stop,
            count=count,
            min=float(values.get("min")),
            max=float(values.get("max")),
            avg=float(values.get("avg")),
        )
