#!/usr/bin/env sh
set -eu
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if [ -n "${PYTHON:-}" ]; then
  PYTHON_BIN=$PYTHON
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo 'Python 3 was not found. Install Python 3 before using frontend-design search.' >&2
  exit 127
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$PYTHON_BIN" "$SCRIPT_DIR/search.py" "$@"
