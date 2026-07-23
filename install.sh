#!/usr/bin/env sh
set -eu

SOURCE=${GLOAMERE_SOURCE:-gloamere/codex-plugins}
REF=${GLOAMERE_REF:-v4.0.0-beta.1}
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
  echo 'Codex CLI was not found. Install and sign in to Codex before installing Gloamere.' >&2
  exit 127
fi

# v3 and v4 use different marketplace identities. Coexisting installs can
# expose duplicate skills, so migration remains an explicit user action.
BEFORE_INSTALL=$(codex plugin list --json)
case "$BEFORE_INSTALL" in
  *'@tessera"'*)
    {
      echo 'Legacy Tessera plugins were detected. No installation changes were made.'
      echo 'Run these migration steps manually:'
      echo '  1. codex plugin remove <plugin>@tessera'
      echo '  2. codex plugin marketplace remove tessera'
      echo '  3. Re-run this pinned Gloamere installer'
      echo 'See MIGRATION.md for identity and data-preservation details.'
    } >&2
    exit 3
    ;;
esac

if [ -e "$SOURCE" ]; then
  codex plugin marketplace add "$SOURCE"
else
  codex plugin marketplace add "$SOURCE" --ref "$REF"
fi

PLUGINS='gloamere-eval'
if [ "$INSTALL_ALL" -eq 1 ]; then
  PLUGINS='gloamere-eval gloamere-workflows'
fi

for plugin in $PLUGINS; do
  codex plugin add "$plugin@gloamere"
done

AFTER_INSTALL=$(codex plugin list --json)
COMPACT_LIST=$(printf '%s' "$AFTER_INSTALL" | tr -d '[:space:]')
for plugin in $PLUGINS; do
  selector="$plugin@gloamere"
  case "$COMPACT_LIST" in
    *"\"pluginId\":\"$selector\""*) ;;
    *) echo "Codex did not report $selector as installed." >&2; exit 1 ;;
  esac
done

echo "Gloamere installed from ${SOURCE}@${REF}: $PLUGINS"
echo 'Start a new Codex task to load the installed skills.'
