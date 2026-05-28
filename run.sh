#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

uv run python manage.py migrate --noinput

echo "Starting ViewMaster at http://127.0.0.1:8000/"
echo "Create a login with: uv run python manage.py createsuperuser"
uv run python -m gunicorn viewmaster.wsgi:application --chdir viewmaster --bind 127.0.0.1:8000
