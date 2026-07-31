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
  echo 'Python 3 was not found.' >&2
  exit 127
fi

CHECK_TMP=$(mktemp -d "${TMPDIR:-/tmp}/gloamere-check.XXXXXX")
cleanup() {
  rm -rf -- "$CHECK_TMP"
}
trap cleanup EXIT HUP INT TERM
TARGET_LOCK="$CHECK_TMP/target-lock.json"

"$PYTHON_BIN" scripts/generate_release_files.py --check
"$PYTHON_BIN" scripts/validate_marketplace.py
"$PYTHON_BIN" scripts/validate_release_evidence.py
"$PYTHON_BIN" scripts/validate_directory_submission.py
"$PYTHON_BIN" scripts/validate_quality_evidence.py
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py'
# Root cause: a stale user-global plugin can contaminate repository checks.
# The fixed empty catalog validates local identities; real eval still observes Codex.
"$PYTHON_BIN" scripts/run_routing_eval.py inspect \
  --catalog tests/fixtures/empty_plugin_catalog.json \
  --plugin-root plugins/gloamere-eval \
  --plugin-root plugins/gloamere-workflows \
  --marketplace gloamere \
  --output "$TARGET_LOCK" >/dev/null
"$PYTHON_BIN" scripts/run_routing_eval.py lint \
  --target-lock "$TARGET_LOCK"

echo 'All Gloamere checks passed.'
