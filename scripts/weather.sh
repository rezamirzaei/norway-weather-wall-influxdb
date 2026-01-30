#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

API_URL="${API_URL:-http://127.0.0.1:8000}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-change_me}"

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo "Starting Docker stack..."
docker compose up -d --build

echo "Waiting for API at ${API_URL}..."
for _ in $(seq 1 60); do
  if curl -fsS "${API_URL}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "Requesting JWT token..."
TOKEN_JSON="$(
  curl -fsS -X POST "${API_URL}/api/v1/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "username=${USERNAME}" \
    --data-urlencode "password=${PASSWORD}"
)"

TOKEN="$(
  python -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))' <<<"${TOKEN_JSON}"
)"

echo "Refreshing weather (fetch MET Norway + write InfluxDB)..."
curl -fsS -X POST "${API_URL}/api/v1/weather/refresh?force=true" \
  -H "Authorization: Bearer ${TOKEN}" | python -m json.tool

echo "Latest weather points:"
curl -fsS "${API_URL}/api/v1/weather/latest" \
  -H "Authorization: Bearer ${TOKEN}" | python -m json.tool

echo "UI: ${API_URL}/ui"
