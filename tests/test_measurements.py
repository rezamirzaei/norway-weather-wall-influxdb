from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def test_write_and_query_measurements(client: TestClient, token: str) -> None:
    write = client.post(
        "/api/v1/measurements",
        json={"device_id": "device-1", "readings": {"temperature": 21.5}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert write.status_code == 201, write.text

    resp = client.get(
        "/api/v1/measurements",
        params={
            "device_id": "device-1",
            "metric": "temperature",
            "limit": 10,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["device_id"] == "device-1"
    assert data[0]["metric"] == "temperature"
    assert data[0]["value"] == 21.5


def test_summary(client: TestClient, token: str) -> None:
    for value in [10.0, 20.0, 30.0]:
        client.post(
            "/api/v1/measurements",
            json={
                "device_id": "device-2",
                "readings": {"temperature": value},
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    start = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
    stop = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()

    resp = client.get(
        "/api/v1/measurements/summary",
        params={"device_id": "device-2", "metric": "temperature", "start": start, "stop": stop},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 3
    assert body["min"] == 10.0
    assert body["max"] == 30.0
    assert body["avg"] == 20.0


def test_auth_required(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/measurements",
        json={"device_id": "device-1", "readings": {"temperature": 21.5}},
    )
    assert resp.status_code in {401, 403}

