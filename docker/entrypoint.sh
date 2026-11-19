#!/bin/sh
set -eu

# Compose waits for PostgreSQL; migrations are safe to run again on restart.
python manage.py migrate --noinput
exec "$@"
