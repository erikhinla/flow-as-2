#!/usr/bin/env bash
# Bring up the client diagnostic and operator desk on a Netcup VPS.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Copy deploy/live/env.example to .env and set the secrets." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine, then rerun this script." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

python3 shared/live_secrets.py

profile=()
if [[ -n "${DIAGNOSTIC_HOST:-}" || -n "${DESK_HOST:-}" ]]; then
  export DIAGNOSTIC_PUBLIC_URL="${DIAGNOSTIC_PUBLIC_URL:-https://${DIAGNOSTIC_HOST}/diagnostic?type=bizbuilders}"
  export LIVE_BIND="${LIVE_BIND:-127.0.0.1}"
  profile=(--profile tls)
else
  export LIVE_BIND="${LIVE_BIND:-0.0.0.0}"
fi

compose=(docker compose --env-file .env -f deploy/live/docker-compose.yml "${profile[@]}")
"${compose[@]}" up -d --build
"${compose[@]}" ps

if [[ ${#profile[@]} -gt 0 ]]; then
  echo "Diagnostic: https://${DIAGNOSTIC_HOST}/diagnostic?type=bizbuilders"
  echo "Desk: https://${DESK_HOST}/"
else
  echo "Diagnostic: http://SERVER:8080/diagnostic?type=bizbuilders"
  echo "Desk: http://SERVER:5173/"
  echo "The desk also serves the form at /diagnostic without its password."
fi
