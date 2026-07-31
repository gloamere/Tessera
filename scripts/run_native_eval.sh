#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNNER="$SCRIPT_DIR/../plugins/gloamere-eval/skills/gloamere-skill-eval/scripts/run.sh"
DEFAULT_MODE=release

# Named arguments are intentionally passed through unchanged so the POSIX
# wrapper exposes the same contract as run_native_eval.ps1 and the Python CLI.
case "${1:-}" in
  --*)
    # 根因：透传时依赖 Python 旧的 exhaustive 默认；修复要点：未指定模式时显式注入 release。
    MODE_WAS_SET=false
    for argument in "$@"; do
      case "$argument" in
        --mode|--mode=*) MODE_WAS_SET=true; break ;;
      esac
    done
    if [ "$MODE_WAS_SET" = false ]; then
      set -- --mode "$DEFAULT_MODE" "$@"
    fi
    exec sh "$RUNNER" native "$@"
    ;;
esac

# Keep the historical positional interface for existing automation.
if [ "$#" -lt 2 ] || [ "$#" -gt 4 ]; then
  echo 'Usage: run_native_eval.sh <suite.json> <target-lock.json> [repeat] [output.json]' >&2
  echo '   or: run_native_eval.sh --suite FILE --target-lock FILE [native options]' >&2
  echo 'Omitting --mode defaults to release; exhaustive must be selected explicitly.' >&2
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
    --mode "$DEFAULT_MODE" \
    --repeat "$REPEAT" \
    --output "$OUTPUT"
fi

if [ -n "$OUTPUT" ]; then
  exec sh "$RUNNER" native \
    --suite "$SUITE" \
    --target-lock "$TARGET_LOCK" \
    --mode "$DEFAULT_MODE" \
    --output "$OUTPUT"
fi

if [ -n "$REPEAT" ]; then
  exec sh "$RUNNER" native \
    --suite "$SUITE" \
    --target-lock "$TARGET_LOCK" \
    --mode "$DEFAULT_MODE" \
    --repeat "$REPEAT"
fi

exec sh "$RUNNER" native \
  --suite "$SUITE" \
  --target-lock "$TARGET_LOCK" \
  --mode "$DEFAULT_MODE"
