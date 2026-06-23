#!/usr/bin/env bash
set -euo pipefail

PID=$(lsof -ti:8700 2>/dev/null || true)
if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
    echo "PrintCode Guard stopped (PID $PID)"
else
    echo "PrintCode Guard is not running on port 8700"
fi
