#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/viewmaster"

uv run python manage.py migrate --noinput

echo "Starting ViewMaster at http://127.0.0.1:8000/"
echo "Create a login with: cd viewmaster && uv run python manage.py createsuperuser"
uv run gunicorn viewmaster.wsgi:application --bind 127.0.0.1:8000
