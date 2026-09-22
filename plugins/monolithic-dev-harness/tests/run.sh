#!/usr/bin/env bash
# Run every suite. Needs Python 3.10+ with pytest (e.g. `python3 -m venv .venv && .venv/bin/pip install pytest`).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
cd "$ROOT"
PYTHONPATH=runtime:tests/backlog "$PY" -m pytest tests/backlog -q -p no:cacheprovider
PYTHONPATH=.:scripts "$PY" -m pytest tests/delivery tests/harness -q -p no:cacheprovider
