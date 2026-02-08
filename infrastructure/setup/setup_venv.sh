#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python not found. Please install Python 3.10+." >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ required.")
PY

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment at .venv..."
  "$PYTHON_BIN" -m venv .venv
else
  echo "Using existing virtual environment at .venv."
fi

source ".venv/bin/activate"
python -m pip install --upgrade pip

REQ_ROOT="requirements.txt"
REQ_BACKEND="backend/requirements.txt"
if [ -f "$REQ_ROOT" ]; then
  python -m pip install -r "$REQ_ROOT"
fi
if [ -f "$REQ_BACKEND" ]; then
  python -m pip install -r "$REQ_BACKEND"
fi

python -m pip check || true

echo ""
echo "Venv ready. Activate with: source .venv/bin/activate"
