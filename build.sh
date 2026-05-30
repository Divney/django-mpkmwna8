#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python viewmaster/manage.py collectstatic --no-input

python viewmaster/manage.py migrate

python viewmaster/manage.py import_catalog