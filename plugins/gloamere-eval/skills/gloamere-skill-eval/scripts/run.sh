#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNNER="$SCRIPT_DIR/run_routing_eval.py"
VERSION_PROBE='import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'

try_python() {
  candidate=$1
  shift
  if command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c "$VERSION_PROBE" >/dev/null 2>&1; then
    exec "$candidate" "$RUNNER" "$@"
  fi
}

if [ -n "${PYTHON:-}" ]; then
  try_python "$PYTHON" "$@"
fi
try_python python3 "$@"
try_python python "$@"

echo 'gloamere-skill-eval requires Python 3.10 or newer; no compatible python3 or python command was found.' >&2
exit 127
