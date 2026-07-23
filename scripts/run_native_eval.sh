#!/usr/bin/env sh
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 4 ]; then
  echo 'Usage: run_native_eval.sh <suite.json> <target-lock.json> [repeat] [output.json]' >&2
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

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNNER="$SCRIPT_DIR/../plugins/gloamere-eval/skills/gloamere-skill-eval/scripts/run.sh"

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
