#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

API_URL="${API_URL:-http://localhost:8000}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-change_me}"

DEVICE_ID="${DEVICE_ID:-device-1}"
METRIC="${METRIC:-temperature}"
VALUE="${VALUE:-21.5}"

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

if [[ -z "${TOKEN}" ]]; then
  echo "Failed to obtain token. Response:"
  echo "${TOKEN_JSON}"
  exit 1
fi

echo "Writing metric: device_id=${DEVICE_ID} ${METRIC}=${VALUE}"
curl -fsS -X POST "${API_URL}/api/v1/measurements" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"${DEVICE_ID}\",\"readings\":{\"${METRIC}\":${VALUE}}}" \
  >/dev/null

echo "Latest points:"
curl -fsS "${API_URL}/api/v1/measurements?device_id=${DEVICE_ID}&metric=${METRIC}&limit=5" \
  -H "Authorization: Bearer ${TOKEN}" | python -m json.tool

echo "Summary (last hour):"
curl -fsS "${API_URL}/api/v1/measurements/summary?device_id=${DEVICE_ID}&metric=${METRIC}" \
  -H "Authorization: Bearer ${TOKEN}" | python -m json.tool

echo "UI: ${API_URL}/ui"
