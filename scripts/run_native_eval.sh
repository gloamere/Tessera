#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNNER="$SCRIPT_DIR/../plugins/gloamere-eval/skills/gloamere-skill-eval/scripts/run.sh"

# Named arguments are intentionally passed through unchanged so the POSIX
# wrapper exposes the same contract as run_native_eval.ps1 and the Python CLI.
case "${1:-}" in
  --*)
    exec sh "$RUNNER" native "$@"
    ;;
esac

# Keep the historical positional interface for existing automation.
if [ "$#" -lt 2 ] || [ "$#" -gt 4 ]; then
  echo 'Usage: run_native_eval.sh <suite.json> <target-lock.json> [repeat] [output.json]' >&2
  echo '   or: run_native_eval.sh --suite FILE --target-lock FILE [native options]' >&2
  exit 2
fi

SUITE=$1
TARGET_LOCK=$2
REPEAT=${3:-}
OUTPUT=${4:-}

if [ -n "$REPEAT" ]; then
  case "$REPEAT" in
    *[!0-9]*) echo 'Repeat must be an integer from 1 to 10.' >&2; exit 2 ;;
  esac
  if [ "$REPEAT" -lt 1 ] || [ "$REPEAT" -gt 10 ]; then
    echo 'Repeat must be an integer from 1 to 10.' >&2
    exit 2
  fi
fi

if [ -n "$REPEAT" ] && [ -n "$OUTPUT" ]; then
  exec sh "$RUNNER" native \
    --suite "$SUITE" \
    --target-lock "$TARGET_LOCK" \
    --repeat "$REPEAT" \
    --output "$OUTPUT"
fi

if [ -n "$OUTPUT" ]; then
  exec sh "$RUNNER" native \
    --suite "$SUITE" \
    --target-lock "$TARGET_LOCK" \
    --output "$OUTPUT"
fi

if [ -n "$REPEAT" ]; then
  exec sh "$RUNNER" native \
    --suite "$SUITE" \
    --target-lock "$TARGET_LOCK" \
    --repeat "$REPEAT"
fi

exec sh "$RUNNER" native \
  --suite "$SUITE" \
  --target-lock "$TARGET_LOCK"
