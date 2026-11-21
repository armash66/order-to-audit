#!/bin/sh
set -eu
python -m alembic upgrade head
python -m api.cli seed
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
