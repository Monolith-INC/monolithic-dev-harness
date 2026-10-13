#!/usr/bin/env bash
# Run every suite. Needs Python 3.12+ and the repository's requirements-dev.txt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/bin/harness-python}"
if [[ "$PY" == */* && "$PY" != /* ]]; then
  PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")"
fi
cd "$ROOT"
PYTHONPATH=runtime:tests/backlog:. "$PY" -m pytest tests/backlog -q -p no:cacheprovider
PYTHONPATH=.:scripts "$PY" -m pytest tests/core tests/integrations tests/delivery tests/harness -q -p no:cacheprovider
bash tests/test_installer_confirmation.sh
bash tests/test_installer_kimi.sh
