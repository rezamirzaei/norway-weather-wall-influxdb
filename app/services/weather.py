from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.clients.metno import MetNoClient
from app.models.weather import City, WeatherObservation
from app.repositories.weather import WeatherRepository

NORWEGIAN_CITIES: list[City] = [
    City("Oslo", 59.9139, 10.7522),
    City("Bergen", 60.39299, 5.32415),
    City("Trondheim", 63.4305, 10.3951),
    City("Tromsø", 69.6492, 18.9553),
    City("Stavanger", 58.969975, 5.733107),
]


@dataclass(frozen=True)
class WeatherRefreshResult:
    requested: int
    stored: int
    failed: int
    skipped: bool
    retry_after_seconds: int | None
    cities: list[str]


class WeatherRefreshLimiter:
    def __init__(self, *, min_interval_seconds: int) -> None:
        self._min_interval_seconds = max(int(min_interval_seconds), 0)
        self._lock = threading.Lock()
        self._last_attempt: datetime | None = None

    @property
    def min_interval_seconds(self) -> int:
        return self._min_interval_seconds

    def try_acquire(self, *, now: datetime) -> tuple[bool, int]:
        if self._min_interval_seconds <= 0:
            return True, 0

        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        with self._lock:
            if self._last_attempt is None:
                self._last_attempt = now
                return True, 0

            elapsed = (now - self._last_attempt).total_seconds()
            if elapsed >= self._min_interval_seconds:
                self._last_attempt = now
                return True, 0

            retry_after = int(self._min_interval_seconds - elapsed)
            return False, max(retry_after, 1)


class WeatherCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_city: dict[str, WeatherObservation] = {}

    def update(self, observation: WeatherObservation) -> None:
        with self._lock:
            self._by_city[observation.city] = observation

    def get(self, *, city: str) -> WeatherObservation | None:
        with self._lock:
            return self._by_city.get(city)

    def snapshot(self, *, cities: list[str] | None = None) -> list[WeatherObservation]:
        with self._lock:
            if cities is None:
                rows = list(self._by_city.values())
            else:
                rows = [self._by_city[c] for c in cities if c in self._by_city]
        rows.sort(key=lambda r: r.city)
        return rows

    def has_any(self) -> bool:
        with self._lock:
            return bool(self._by_city)


class WeatherIngestionService:
    def __init__(
        self,
        *,
        repo: WeatherRepository,
        met_client: MetNoClient,
        cities: list[City] | None = None,
        refresh_limiter: WeatherRefreshLimiter | None = None,
        cache: WeatherCache | None = None,
    ) -> None:
        self._repo = repo
        self._met = met_client
        self._cities = cities or NORWEGIAN_CITIES
        self._refresh_limiter = refresh_limiter
        self._cache = cache

    def refresh(self, *, force: bool = False) -> WeatherRefreshResult:
        now = datetime.now(tz=timezone.utc)
        if not force and self._refresh_limiter is not None:
            allowed, retry_after = self._refresh_limiter.try_acquire(now=now)
            if not allowed:
                return WeatherRefreshResult(
                    requested=0,
                    stored=0,
                    failed=0,
                    skipped=True,
                    retry_after_seconds=retry_after,
                    cities=[c.name for c in self._cities],
                )

        stored = 0
        failed = 0
        names: list[str] = []
        for city in self._cities:
            names.append(city.name)
            try:
                fetched = self._met.fetch_current_observation(city)
                observation = WeatherObservation(
                    city=fetched.city,
                    lat=fetched.lat,
                    lon=fetched.lon,
                    timestamp=now,
                    air_temperature=fetched.air_temperature,
                    relative_humidity=fetched.relative_humidity,
                    air_pressure_at_sea_level=fetched.air_pressure_at_sea_level,
                    wind_speed=fetched.wind_speed,
                    wind_from_direction=fetched.wind_from_direction,
                    cloud_area_fraction=fetched.cloud_area_fraction,
                    precipitation_amount_1h=fetched.precipitation_amount_1h,
                    symbol_code=fetched.symbol_code,
                )
                self._repo.write_observation(observation)
                if self._cache is not None:
                    self._cache.update(observation)
                stored += 1
            except Exception:
                failed += 1
        return WeatherRefreshResult(
            requested=len(self._cities),
            stored=stored,
            failed=failed,
            skipped=False,
            retry_after_seconds=None,
            cities=names,
        )

    def tick(self) -> None:
        now = datetime.now(tz=timezone.utc)
        cities = list(self._cities)

        provider_allowed = True
        if self._refresh_limiter is not None:
            provider_allowed, _ = self._refresh_limiter.try_acquire(now=now)

        for city in cities:
            observation: WeatherObservation | None = None
            if provider_allowed:
                try:
                    fetched = self._met.fetch_current_observation(city)
                    observation = WeatherObservation(
                        city=fetched.city,
                        lat=fetched.lat,
                        lon=fetched.lon,
                        timestamp=now,
                        air_temperature=fetched.air_temperature,
                        relative_humidity=fetched.relative_humidity,
                        air_pressure_at_sea_level=fetched.air_pressure_at_sea_level,
                        wind_speed=fetched.wind_speed,
                        wind_from_direction=fetched.wind_from_direction,
                        cloud_area_fraction=fetched.cloud_area_fraction,
                        precipitation_amount_1h=fetched.precipitation_amount_1h,
                        symbol_code=fetched.symbol_code,
                    )
                except Exception:
                    observation = None

            if observation is None and self._cache is not None:
                cached = self._cache.get(city=city.name)
                if cached is not None:
                    observation = WeatherObservation(
                        city=cached.city,
                        lat=cached.lat,
                        lon=cached.lon,
                        timestamp=now,
                        air_temperature=cached.air_temperature,
                        relative_humidity=cached.relative_humidity,
                        air_pressure_at_sea_level=cached.air_pressure_at_sea_level,
                        wind_speed=cached.wind_speed,
                        wind_from_direction=cached.wind_from_direction,
                        cloud_area_fraction=cached.cloud_area_fraction,
                        precipitation_amount_1h=cached.precipitation_amount_1h,
                        symbol_code=cached.symbol_code,
                    )

            if observation is None:
                continue

            try:
                self._repo.write_observation(observation)
                if self._cache is not None:
                    self._cache.update(observation)
            except Exception:
                continue

    def latest(self) -> list[WeatherObservation]:
        if self._cache is not None and self._cache.has_any():
            return self._cache.snapshot(cities=[c.name for c in self._cities])

        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=1)
        stop = now
        return self._repo.query_latest(
            cities=[c.name for c in self._cities], start=start, stop=stop
        )
