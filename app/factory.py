from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.clients.metno import MetNoClient
from app.core.config import Settings, load_settings
from app.db.influx import create_influx_client
from app.repositories.weather_influx import InfluxWeatherRepository
from app.services.weather import (
    WeatherCache,
    WeatherIngestionService,
    WeatherRefreshLimiter,
)
from app.web.router import ui_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop_event: threading.Event | None = None
        bg_thread: threading.Thread | None = None

        app.state.settings = settings
        app.state.influx_client = create_influx_client(settings)
        app.state.weather_refresh_limiter = WeatherRefreshLimiter(
            min_interval_seconds=settings.weather_min_refresh_interval_seconds
        )
        app.state.weather_cache = WeatherCache()
        app.state.metno_client = MetNoClient(
            user_agent=settings.weather_user_agent,
            timeout_seconds=settings.weather_timeout_seconds,
        )

        if (
            settings.weather_background_refresh_enabled
            and settings.weather_background_refresh_interval_seconds > 0
        ):
            stop_event = threading.Event()
            repo = InfluxWeatherRepository(
                client=app.state.influx_client,
                org=settings.influx_org,
                bucket=settings.influx_bucket,
                measurement=settings.weather_measurement,
                timeout_ms=settings.influx_timeout_ms,
            )
            bg_service = WeatherIngestionService(
                repo=repo,
                met_client=app.state.metno_client,
                refresh_limiter=app.state.weather_refresh_limiter,
                cache=app.state.weather_cache,
            )

            def _loop() -> None:
                while stop_event is not None and not stop_event.is_set():
                    try:
                        bg_service.tick()
                    except Exception:
                        pass
                    stop_event.wait(settings.weather_background_refresh_interval_seconds)

            bg_thread = threading.Thread(
                target=_loop, name="weather-background-refresh", daemon=True
            )
            bg_thread.start()

        yield
        if stop_event is not None:
            stop_event.set()
        if bg_thread is not None and bg_thread.is_alive():
            bg_thread.join(timeout=2.0)
        app.state.metno_client.close()
        app.state.influx_client.close()

    docs_enabled = settings.docs_enabled and not settings.is_production
    app = FastAPI(
        title="InfluxDB Metrics API",
        version="0.1.0",
        debug=settings.debug,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.weather_refresh_limiter = WeatherRefreshLimiter(
        min_interval_seconds=settings.weather_min_refresh_interval_seconds
    )
    app.state.weather_cache = WeatherCache()

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.is_production,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    if settings.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    @app.get("/", tags=["meta"])
    def root():
        return {"name": "influx-db-demo", "status": "ok"}

    app.include_router(api_router)
    app.include_router(ui_router)

    static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app
