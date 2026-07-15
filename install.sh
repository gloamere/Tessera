#!/usr/bin/env sh
set -eu

SOURCE=${TESSERA_SOURCE:-gloamere/Tessera}
REF=${TESSERA_REF:-main}
INSTALL_ALL=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --all) INSTALL_ALL=1 ;;
    --source) shift; SOURCE=${1:?--source requires a value} ;;
    --ref) shift; REF=${1:?--ref requires a value} ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if ! command -v codex >/dev/null 2>&1; then
  echo 'Codex CLI was not found. Install and sign in to Codex before installing Tessera.' >&2
  exit 127
fi

if [ -e "$SOURCE" ]; then
  codex plugin marketplace add "$SOURCE"
else
  codex plugin marketplace add "$SOURCE" --ref "$REF"
fi

PLUGINS='tessera-core'
if [ "$INSTALL_ALL" -eq 1 ]; then
  PLUGINS='tessera-core taste frontend-design knowledge-base finance-ops growth-ops product-planning business-ops'
fi

for plugin in $PLUGINS; do
  codex plugin add "$plugin@tessera"
done

LIST=$(codex plugin list --json)
for plugin in $PLUGINS; do
  case "$LIST" in
    *"\"pluginId\": \"$plugin@tessera\""*) ;;
    *) echo "Codex did not report $plugin@tessera as installed." >&2; exit 1 ;;
  esac
done

echo "Tessera installed: $PLUGINS"
echo 'Start a new Codex task to load the installed skills.'
