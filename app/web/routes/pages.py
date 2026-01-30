from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.api.deps import (
    authenticate_user,
    get_measurement_repository,
    get_settings,
    get_weather_service,
)
from app.core.config import Settings
from app.schemas.auth import User
from app.schemas.measurements import DEVICE_ID_PATTERN, METRIC_PATTERN, MeasurementCreate
from app.services.measurements import MeasurementService
from app.services.weather import WeatherIngestionService
from app.web.deps import csrf_protect, ensure_csrf_token, require_session_user
from app.web.templates import templates

router = APIRouter()


def get_service(
    repo=Depends(get_measurement_repository),
) -> MeasurementService:
    return MeasurementService(repo)


def _last_hour_range() -> tuple[datetime, datetime]:
    stop = datetime.now(tz=timezone.utc)
    start = stop - timedelta(hours=1)
    return start, stop


def _render_dashboard(
    *,
    request: Request,
    user: User,
    service: MeasurementService,
    device_id: str,
    metric: str,
    limit: int,
    message: str | None = None,
    error: str | None = None,
):
    csrf_token = ensure_csrf_token(request)
    start, stop = _last_hour_range()

    influx_error: str | None = None
    records = []
    summary = None
    try:
        records = service.list_measurements(
            device_id=device_id, metric=metric, start=start, stop=stop, limit=limit
        )
        summary = service.summarize_measurements(
            device_id=device_id, metric=metric, start=start, stop=stop
        )
    except Exception:
        influx_error = "InfluxDB unavailable"

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "title": "Dashboard",
            "user": user,
            "csrf_token": csrf_token,
            "device_id": device_id,
            "metric": metric,
            "limit": limit,
            "start": start,
            "stop": stop,
            "records": records,
            "summary": summary,
            "message": message,
            "error": error,
            "influx_error": influx_error,
        },
    )


def _weather_rows_payload(rows) -> list[dict[str, object]]:
    return [
        {
            "city": r.city,
            "lat": r.lat,
            "lon": r.lon,
            "timestamp": r.timestamp.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "air_temperature": r.air_temperature,
            "relative_humidity": r.relative_humidity,
            "air_pressure_at_sea_level": r.air_pressure_at_sea_level,
            "wind_speed": r.wind_speed,
            "wind_from_direction": r.wind_from_direction,
            "cloud_area_fraction": r.cloud_area_fraction,
            "precipitation_amount_1h": r.precipitation_amount_1h,
            "symbol_code": r.symbol_code,
        }
        for r in rows
    ]


@router.get("/", include_in_schema=False)
def ui_index(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/ui/weather", status_code=303)
    return RedirectResponse("/ui/login", status_code=303)


@router.get("/login", include_in_schema=False)
def login_page(request: Request):
    csrf_token = ensure_csrf_token(request)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "title": "Login", "csrf_token": csrf_token},
    )


@router.post("/login", include_in_schema=False, dependencies=[Depends(csrf_protect)])
def login_submit(
    request: Request,
    username: Annotated[str, Form(min_length=1, max_length=64)],
    password: Annotated[str, Form(min_length=1, max_length=256)],
    settings: Annotated[Settings, Depends(get_settings)],
    weather_service: WeatherIngestionService = Depends(get_weather_service),
):
    user = authenticate_user(username=username, password=password, settings=settings)
    if not user:
        csrf_token = ensure_csrf_token(request)
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "title": "Login",
                "csrf_token": csrf_token,
                "error": "Invalid username or password",
            },
            status_code=401,
        )

    request.session["user"] = user.model_dump()
    request.session["csrf_token"] = secrets.token_urlsafe(32)

    flash_message: str | None = None
    flash_error: str | None = None
    if settings.weather_fetch_on_login:
        try:
            result = weather_service.refresh(force=True)
            if result.skipped:
                flash_message = (
                    f"Weather refresh skipped (try again in {result.retry_after_seconds}s)."
                )
            else:
                flash_message = (
                    f"Weather refreshed (stored {result.stored}/{result.requested}, failed {result.failed})."
                )
        except Exception:
            flash_error = "Weather provider unavailable."

    redirect_url = "/ui/weather"
    query: dict[str, str] = {}
    if flash_message:
        query["message"] = flash_message
    if flash_error:
        query["error"] = flash_error
    if query:
        redirect_url = f"{redirect_url}?{urlencode(query)}"
    return RedirectResponse(redirect_url, status_code=303)


@router.get("/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/ui/login", status_code=303)


@router.get("/dashboard", include_in_schema=False)
def dashboard(
    request: Request,
    user: Annotated[User, Depends(require_session_user)],
    device_id: Annotated[
        str, Query(min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)
    ] = "device-1",
    metric: Annotated[str, Query(min_length=1, max_length=64, pattern=METRIC_PATTERN)] = (
        "temperature"
    ),
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    service: MeasurementService = Depends(get_service),
):
    return _render_dashboard(
        request=request,
        user=user,
        service=service,
        device_id=device_id,
        metric=metric,
        limit=limit,
    )


@router.get("/weather", include_in_schema=False)
def weather_page(
    request: Request,
    user: Annotated[User, Depends(require_session_user)],
    weather_service: WeatherIngestionService = Depends(get_weather_service),
    message: Annotated[str | None, Query(max_length=200)] = None,
    flash_error: Annotated[str | None, Query(max_length=200, alias="error")] = None,
):
    csrf_token = ensure_csrf_token(request)
    error: str | None = flash_error
    rows = []
    rows_payload = []
    try:
        rows = weather_service.latest()
        rows_payload = _weather_rows_payload(rows)
    except Exception:
        error = error or "InfluxDB unavailable"
    return templates.TemplateResponse(
        request,
        "weather.html",
        {
            "request": request,
            "title": "Weather",
            "user": user,
            "csrf_token": csrf_token,
            "rows": rows,
            "rows_payload": rows_payload,
            "message": message,
            "error": error,
        },
    )


@router.get("/weather/latest.json", include_in_schema=False)
def weather_latest_json(
    _: Annotated[User, Depends(require_session_user)],
    weather_service: WeatherIngestionService = Depends(get_weather_service),
) -> list[dict[str, object]]:
    try:
        rows = weather_service.latest()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="InfluxDB unavailable",
        ) from e
    return _weather_rows_payload(rows)


@router.post(
    "/weather/refresh",
    include_in_schema=False,
    dependencies=[Depends(csrf_protect)],
)
def refresh_weather(
    request: Request,
    _: Annotated[User, Depends(require_session_user)],
    weather_service: WeatherIngestionService = Depends(get_weather_service),
):
    flash_message: str | None = None
    flash_error: str | None = None
    try:
        result = weather_service.refresh(force=True)
        if result.skipped:
            flash_message = (
                f"Weather refresh skipped (try again in {result.retry_after_seconds}s)."
            )
        else:
            flash_message = (
                f"Weather refreshed (stored {result.stored}/{result.requested}, failed {result.failed})."
            )
    except Exception:
        flash_error = "Weather provider unavailable."

    redirect_url = "/ui/weather"
    query: dict[str, str] = {}
    if flash_message:
        query["message"] = flash_message
    if flash_error:
        query["error"] = flash_error
    if query:
        redirect_url = f"{redirect_url}?{urlencode(query)}"
    return RedirectResponse(redirect_url, status_code=303)


@router.post(
    "/measurements",
    include_in_schema=False,
    dependencies=[Depends(csrf_protect)],
)
def write_measurement(
    request: Request,
    user: Annotated[User, Depends(require_session_user)],
    device_id: Annotated[str, Form(min_length=1, max_length=64)],
    metric: Annotated[str, Form(min_length=1, max_length=64)],
    value: Annotated[float, Form()],
    service: MeasurementService = Depends(get_service),
):
    limit = 20
    try:
        payload = MeasurementCreate(device_id=device_id, readings={metric: value})
        service.write_measurement(payload)
    except ValidationError:
        return _render_dashboard(
            request=request,
            user=user,
            service=service,
            device_id=device_id,
            metric=metric,
            limit=limit,
            error="Invalid input (check device id, metric name, and numeric value).",
        )
    except Exception:
        return _render_dashboard(
            request=request,
            user=user,
            service=service,
            device_id=device_id,
            metric=metric,
            limit=limit,
            error="Could not write to InfluxDB (unavailable).",
        )

    return RedirectResponse(
        url=f"/ui/dashboard?device_id={device_id}&metric={metric}&limit={limit}",
        status_code=303,
    )
