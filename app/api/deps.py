from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from app.clients.metno import MetNoClient
from app.core.config import Settings
from app.core.security import verify_password
from app.repositories.base import MeasurementRepository
from app.repositories.influx import InfluxMeasurementRepository
from app.repositories.weather import WeatherRepository
from app.repositories.weather_influx import InfluxWeatherRepository
from app.schemas.auth import User
from app.services.weather import WeatherCache, WeatherIngestionService, WeatherRefreshLimiter

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    scopes={
        "metrics:read": "Read metrics",
        "metrics:write": "Write metrics",
        "weather:read": "Read weather",
        "weather:write": "Fetch/write weather",
    },
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_measurement_repository(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> MeasurementRepository:
    return InfluxMeasurementRepository(
        client=request.app.state.influx_client,
        org=settings.influx_org,
        bucket=settings.influx_bucket,
        measurement=settings.influx_measurement,
        timeout_ms=settings.influx_timeout_ms,
    )


def authenticate_user(*, username: str, password: str, settings: Settings) -> User | None:
    if username != settings.admin_username:
        return None
    if not verify_password(password, settings.admin_password_hash):
        return None
    return User(
        username=username,
        scopes=["metrics:read", "metrics:write", "weather:read", "weather:write"],
    )


def get_metno_client(request: Request) -> MetNoClient:
    return request.app.state.metno_client


def get_weather_refresh_limiter(request: Request) -> WeatherRefreshLimiter | None:
    limiter = getattr(request.app.state, "weather_refresh_limiter", None)
    if limiter is None:
        return None
    if not isinstance(limiter, WeatherRefreshLimiter):
        return None
    return limiter


def get_weather_cache(request: Request) -> WeatherCache | None:
    cache = getattr(request.app.state, "weather_cache", None)
    if cache is None:
        return None
    if not isinstance(cache, WeatherCache):
        return None
    return cache


def get_weather_repository(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> WeatherRepository:
    return InfluxWeatherRepository(
        client=request.app.state.influx_client,
        org=settings.influx_org,
        bucket=settings.influx_bucket,
        measurement=settings.weather_measurement,
        timeout_ms=settings.influx_timeout_ms,
    )


def get_weather_service(
    repo: Annotated[WeatherRepository, Depends(get_weather_repository)],
    met: Annotated[MetNoClient, Depends(get_metno_client)],
    limiter: Annotated[
        WeatherRefreshLimiter | None, Depends(get_weather_refresh_limiter)
    ],
    cache: Annotated[WeatherCache | None, Depends(get_weather_cache)],
) -> WeatherIngestionService:
    return WeatherIngestionService(
        repo=repo, met_client=met, refresh_limiter=limiter, cache=cache
    )


def get_current_user(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    authenticate_value = "Bearer"
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as e:  # noqa: BLE001 - normalize to 401
        raise credentials_exception from e

    sub = payload.get("sub")
    token_scopes = payload.get("scopes", [])
    if not isinstance(sub, str) or not isinstance(token_scopes, list):
        raise credentials_exception

    # Exp is checked by PyJWT, but keep a defensive check for odd clocks.
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < datetime.now(tz=timezone.utc).timestamp():
        raise credentials_exception

    user = User(username=sub, scopes=[str(s) for s in token_scopes])

    for scope in security_scopes.scopes:
        if scope not in user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user


CurrentUser = Annotated[User, Security(get_current_user)]

ReadUser = Annotated[User, Security(get_current_user, scopes=["metrics:read"])]
WriteUser = Annotated[User, Security(get_current_user, scopes=["metrics:write"])]

WeatherReadUser = Annotated[User, Security(get_current_user, scopes=["weather:read"])]
WeatherWriteUser = Annotated[User, Security(get_current_user, scopes=["weather:write"])]
