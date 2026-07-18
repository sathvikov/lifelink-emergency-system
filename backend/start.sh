#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[start] Running bootstrap database helper before server startup..."
python scripts/bootstrap_database.py

echo "[start] Starting FastAPI server on port ${PORT:-3010}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-3010}"
