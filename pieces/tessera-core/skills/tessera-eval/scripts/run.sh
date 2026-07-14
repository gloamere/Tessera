#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNNER="$SCRIPT_DIR/run_routing_eval.py"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$RUNNER" "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$RUNNER" "$@"
fi

echo 'tessera-eval requires Python 3, but python3 and python were not found.' >&2
exit 127
