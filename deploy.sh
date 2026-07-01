#!/usr/bin/env bash
#
# Fraud Detection dashboard — production deploy (static SPA, no backend).
#
#   host nginx (TLS :7777) ──/fraud-detection/──► 127.0.0.1:4779 ──► dashboard :8080
#   Public entrypoint: https://ai.arttechgroup.com:7777/fraud-detection/
#   Local health:      http://127.0.0.1:4779/healthz
#
# Usage:
#   ./deploy.sh           # pull, build, (re)start the container
#   ./deploy.sh --no-pull # skip git pull (deploy current checkout)
#
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE_FILE="docker-compose.prod.yml"
PORT=4779

PULL=1
for arg in "$@"; do
  case "$arg" in
    --no-pull) PULL=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# docker compose v2 (plugin) preferred, fall back to legacy docker-compose.
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "❌ Docker Compose not found. Install Docker first." >&2
  exit 1
fi
COMPOSE="$COMPOSE -f $COMPOSE_FILE"

if [ "$PULL" -eq 1 ] && [ -d .git ]; then
  echo "▶ Pulling latest changes..."
  git pull --ff-only
fi

echo "▶ Building image (runs the Python pipeline + builds the React SPA)..."
$COMPOSE build

echo "▶ Starting the dashboard container..."
$COMPOSE up -d

echo "▶ Waiting for the dashboard to come up..."
ok=0
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${PORT}/healthz || true)"
  if [ "$code" = "200" ]; then ok=1; break; fi
  sleep 2
done

echo
$COMPOSE ps
echo
if [ "$ok" -eq 1 ]; then
  echo "✅ Deploy complete."
  echo "   Local  : http://127.0.0.1:${PORT}/fraud-detection/ (200 via /healthz)"
  echo "   Public : https://ai.arttechgroup.com:7777/fraud-detection/ (after host nginx is configured — see NGINX-DEPLOY-GUIDE.md)"
else
  echo "⚠️  Container started but /healthz did not return 200 in time."
  echo "   Check logs:  $COMPOSE logs -f dashboard"
  exit 1
fi
