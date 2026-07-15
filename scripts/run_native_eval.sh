#!/usr/bin/env sh
set -eu

REPEAT=${1:-3}
OUTPUT=${2:-eval-results/codex-native.json}

case "$REPEAT" in
  ''|*[!0-9]*|0) echo 'Repeat must be a positive integer.' >&2; exit 2 ;;
esac

if [ -n "${PYTHON:-}" ]; then
  PYTHON_BIN=$PYTHON
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo 'Python 3 was not found.' >&2
  exit 127
fi

if ! command -v codex >/dev/null 2>&1; then
  echo 'Codex CLI was not found. Install and sign in to Codex before running native eval.' >&2
  exit 127
fi

"$PYTHON_BIN" scripts/run_routing_eval.py \
  --host codex \
  --mode native \
  --cases pieces/tessera-core/skills/tessera-eval/references/personal-routing-cases.json \
  --repeat "$REPEAT" \
  --suggest-tuning \
  --output "$OUTPUT"
