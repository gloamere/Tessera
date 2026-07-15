#!/usr/bin/env sh
set -eu

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

"$PYTHON_BIN" scripts/validate_marketplace.py
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py'
"$PYTHON_BIN" scripts/run_routing_eval.py \
  --host claude \
  --case direct-small-edit \
  --case multi-intent \
  --case evaluate-routing \
  --adapter-executable "$PYTHON_BIN" \
  --adapter-arg tests/fixtures/fake_eval_host.py \
  --output eval-results/ci-routing.json
"$PYTHON_BIN" scripts/run_routing_eval.py \
  --host claude \
  --mode native \
  --case multi-intent \
  --repeat 3 \
  --suggest-tuning \
  --adapter-executable "$PYTHON_BIN" \
  --adapter-arg tests/fixtures/fake_eval_host.py \
  --output eval-results/ci-native.json
"$PYTHON_BIN" scripts/run_routing_eval.py \
  --host codex \
  --mode native \
  --cases pieces/tessera-core/skills/tessera-eval/references/personal-routing-cases.json \
  --dry-run

echo 'All Tessera checks passed.'
