from __future__ import annotations

import re

from fastapi.testclient import TestClient


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "CSRF token input not found"
    return match.group(1)


def test_ui_login_and_write_flow(client: TestClient) -> None:
    login = client.get("/ui/login")
    assert login.status_code == 200
    csrf = _extract_csrf_token(login.text)

    resp = client.post(
        "/ui/login",
        data={"username": "admin", "password": "password", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/ui/weather"

    weather = client.get("/ui/weather")
    assert weather.status_code == 200

    dashboard = client.get("/ui/dashboard")
    assert dashboard.status_code == 200
    csrf2 = _extract_csrf_token(dashboard.text)

    write = client.post(
        "/ui/measurements",
        data={
            "device_id": "device-1",
            "metric": "temperature",
            "value": "12.3",
            "csrf_token": csrf2,
        },
        follow_redirects=False,
    )
    assert write.status_code == 303

    dashboard2 = client.get("/ui/dashboard?device_id=device-1&metric=temperature&limit=20")
    assert dashboard2.status_code == 200
    assert "12.3" in dashboard2.text
