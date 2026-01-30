from __future__ import annotations

from fastapi.testclient import TestClient


def test_token_success(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_token_wrong_password(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401

