#!/usr/bin/env bash
set -e
cd /home/runner/workspace
export PYTHONPATH=/home/runner/workspace
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
