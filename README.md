# InfluxDB Weather Wall (FastAPI + MVC + Docker + Tests)

This repo is a small “real‑world” demo app that:

- securely logs you in (JWT for API + session/CSRF for UI)
- fetches **Norwegian city weather** (MET Norway) and stores it as **time‑series** in **InfluxDB v2**
- renders a server‑side MVC UI with a **live map** that updates every second
- includes an **InfluxDB analytics** panel (24h min/avg/max + 60m downsampled trend)

## The story

Imagine an operations team supporting systems across Norway. They need a “Weather Wall” to quickly see the latest
conditions in key cities. This app ingests weather data continuously into InfluxDB and shows the newest values on
a map and in a table, while also exposing a secured REST API for automation.

## Why InfluxDB?

Weather (and device metrics) are **time‑series**: timestamped measurements that you write frequently and query by
time windows and “dimensions” such as city/device.

InfluxDB is a good fit because:

- it’s optimized for high‑write time‑series ingestion
- it models “dimensions” naturally as **tags** (`city`, `country`, `device_id`)
- it makes “latest point”, “last N points”, and time‑window queries efficient (Flux)
- it supports built-in downsampling and aggregates (e.g. `aggregateWindow`, `reduce`) for dashboards

## Architecture (MVC + REST)

- UI (MVC): `app/web/routes/*` + Jinja2 templates in `app/web/templates/*`
- API (REST): `/api/v1/*` routes in `app/api/routes/*`
- Service layer: `app/services/*`
- Repository layer: `app/repositories/*` (InfluxDB implementation + test fakes)

Security features:

- JWT auth (OAuth2 password flow) for API endpoints
- session cookie + CSRF for UI form posts
- security headers + trusted hosts middleware

## Data model (InfluxDB)

- Measurement `norwegian_weather`
  - tags: `city`, `country=NO`
  - fields: `air_temperature`, `relative_humidity`, `wind_speed`, `air_pressure_at_sea_level`, …
- Measurement `device_metrics`
  - tags: `device_id`
  - fields: metric names like `temperature`, `humidity`, …

## “Live” updates (every second)

The app runs a background loop that writes one point per city per second into InfluxDB and keeps an in‑memory
cache for fast reads. The UI polls `/ui/weather/latest.json` every second and updates the Leaflet map markers and
table.

Upstream provider note:

- MET Norway data does not meaningfully change every second, and providers can rate‑limit clients.
- The app therefore **throttles upstream fetches** using `APP_WEATHER_MIN_REFRESH_INTERVAL_SECONDS` (default 300s)
  and re-emits the latest known values each second.
- If you *really* want to call MET every tick, set `APP_WEATHER_MIN_REFRESH_INTERVAL_SECONDS=0` (not recommended).

## InfluxDB analytics (why it matters)

The Weather Wall UI includes an “InfluxDB Analytics” panel that demonstrates common time-series query patterns:

- **Latest per city**: server queries the newest point per city (Flux `last()` + `pivot()`).
- **Downsampled trend**: “last 60m” temperature trend aggregated per minute (Flux `aggregateWindow(every: 60s, fn: mean)`).
- **Window summary**: last 24h temperature `min/max/avg/first/last` (Flux `reduce`).

These are the kinds of queries that become painful with generic SQL tables at high write rates, but are natural in
InfluxDB.

## Quick start (Docker)

1) Create `.env`:

```bash
cp .env.example .env
```

2) Start the stack:

```bash
docker compose up --build
```

3) Open the UI:

```text
http://127.0.0.1:8000/ui
```

Login defaults:

- username: `admin`
- password: `change_me`

## Scripts (bash)

Start Docker + force one provider refresh + print latest:

```bash
bash scripts/weather.sh
```

Device metrics demo (write + query):

```bash
bash scripts/demo.sh
```

## API usage

Get a JWT token:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=change_me"
```

Fetch latest weather:

```bash
TOKEN="paste_access_token_here"
curl -s "http://127.0.0.1:8000/api/v1/weather/latest" \
  -H "Authorization: Bearer ${TOKEN}"
```

24h temperature summary (per city):

```bash
curl -s "http://127.0.0.1:8000/api/v1/weather/temperature/summary?hours=24" \
  -H "Authorization: Bearer ${TOKEN}"
```

60m downsampled temperature trend (mean per minute):

```bash
curl -s "http://127.0.0.1:8000/api/v1/weather/temperature/trend?hours=1&window_seconds=60" \
  -H "Authorization: Bearer ${TOKEN}"
```

Force a provider refresh (bypasses throttling):

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/weather/refresh?force=true" \
  -H "Authorization: Bearer ${TOKEN}"
```

## Local dev (no Docker)

```bash
python -m pip install -U pip
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
```

## Configuration highlights

See `.env.example`. Important ones:

- `APP_SECRET_KEY`: session/JWT signing secret (32+ chars)
- `APP_INFLUX_URL`, `APP_INFLUX_TOKEN`, `APP_INFLUX_ORG`, `APP_INFLUX_BUCKET`
- `APP_WEATHER_USER_AGENT`: MET Norway requires a descriptive User‑Agent
- `APP_WEATHER_BACKGROUND_REFRESH_INTERVAL_SECONDS`: default `1` (live loop tick)
- `APP_WEATHER_MIN_REFRESH_INTERVAL_SECONDS`: default `300` (provider fetch throttle)
