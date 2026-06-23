#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Ensure port 8700 is not occupied
PID=$(lsof -ti:8700 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "Port 8700 is already in use by PID $PID, stopping it first..."
    kill "$PID" 2>/dev/null || true
    sleep 1
fi

exec nohup .venv/bin/uvicorn src.printcode_guard.main:app --reload --host 0.0.0.0 --port 8700 >printcode_guard.log 2>&1 &
echo "PrintCode Guard started on http://0.0.0.0:8700"
