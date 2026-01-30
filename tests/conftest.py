from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import get_password_hash
from app.factory import create_app
from app.api import deps
from tests.fakes import FakeMeasurementRepository, FakeMetNoClient, FakeWeatherRepository


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        debug=True,
        docs_enabled=False,
        secret_key="test_secret_key_must_be_32_chars_minimum",
        admin_username="admin",
        admin_password_hash=get_password_hash("password"),
        cors_origins=["http://localhost"],
        trusted_hosts=["testserver", "localhost"],
        influx_url="http://example.com:8086",
        influx_token="test-token-1234567890",
        influx_org="test",
        influx_bucket="test",
        influx_measurement="device_metrics",
        influx_timeout_ms=5000,
        weather_user_agent="test-agent",
        weather_timeout_seconds=1.0,
        weather_measurement="norwegian_weather",
        weather_fetch_on_login=False,
        weather_background_refresh_enabled=False,
        weather_background_refresh_interval_seconds=1.0,
    )


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    app = create_app(settings)
    fake_repo = FakeMeasurementRepository()
    fake_weather_repo = FakeWeatherRepository()
    fake_met = FakeMetNoClient()
    app.dependency_overrides[deps.get_measurement_repository] = lambda: fake_repo
    app.dependency_overrides[deps.get_weather_repository] = lambda: fake_weather_repo
    app.dependency_overrides[deps.get_metno_client] = lambda: fake_met
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def now() -> datetime:
    return datetime.now(tz=timezone.utc)
