from __future__ import annotations

from fastapi.testclient import TestClient


def test_weather_refresh_and_latest(client: TestClient, token: str) -> None:
    refresh = client.post(
        "/api/v1/weather/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert refresh.status_code == 200, refresh.text
    body = refresh.json()
    assert body["requested"] >= 1
    assert body["stored"] >= 1

    latest = client.get(
        "/api/v1/weather/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert latest.status_code == 200, latest.text
    rows = latest.json()
    assert isinstance(rows, list) and rows
    assert "city" in rows[0]
    assert "air_temperature" in rows[0]


def test_weather_temperature_analytics(client: TestClient, token: str) -> None:
    client.post(
        "/api/v1/weather/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )

    summary = client.get(
        "/api/v1/weather/temperature/summary?hours=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert isinstance(body, list) and body
    assert {"city", "min", "max", "avg", "first", "last"} <= set(body[0].keys())

    trend = client.get(
        "/api/v1/weather/temperature/trend?hours=1&window_seconds=60",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert trend.status_code == 200, trend.text
    points = trend.json()
    assert isinstance(points, list) and points
    assert {"city", "timestamp", "value"} <= set(points[0].keys())
