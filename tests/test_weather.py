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

