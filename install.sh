#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RELEASE_MANIFEST="$SCRIPT_DIR/release-manifest.json"
if [ "${GLOAMERE_SOURCE+x}" = x ]; then
  SOURCE_WAS_EXPLICIT=true
else
  SOURCE_WAS_EXPLICIT=false
fi
SOURCE=${GLOAMERE_SOURCE:-gloamere/codex-plugins}
REF=${GLOAMERE_REF:-v4.0.0}
PROFILE=${GLOAMERE_PROFILE:-workflows}

# The default is the tagged Git marketplace. --source also accepts a local
# marketplace path or another HTTPS Git host without changing the plugin IDs.
while [ "$#" -gt 0 ]; do
  case "$1" in
    --all) PROFILE=complete ;;
    --profile) shift; PROFILE=${1:?--profile requires a value} ;;
    --source) shift; SOURCE=${1:?--source requires a value}; SOURCE_WAS_EXPLICIT=true ;;
    --ref) shift; REF=${1:?--ref requires a value} ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ ! -f "$RELEASE_MANIFEST" ]; then
  echo 'release-manifest.json was not found beside install.sh. Run the installer from a complete repository checkout.' >&2
  exit 4
fi
RELEASE_STATUS=$(
  sed -n 's/^[[:space:]]*"releaseStatus":[[:space:]]*"\([^"]*\)".*/\1/p' \
    "$RELEASE_MANIFEST" |
    sed -n '1p'
)
if [ -z "$RELEASE_STATUS" ]; then
  echo 'Could not read distribution.releaseStatus from release-manifest.json.' >&2
  exit 4
fi
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

# 根因：候选版默认指向尚不存在的 tag；修复要点：完成只读迁移检查后，published 前只允许显式本地 marketplace。
if [ "$RELEASE_STATUS" != published ]; then
  if [ "$SOURCE_WAS_EXPLICIT" != true ] || [ ! -d "$SOURCE" ]; then
    echo "Gloamere is ${RELEASE_STATUS}; remote installation is unavailable. Pass --source with an existing local repository checkout." >&2
    exit 4
  fi
fi

if [ -d "$SOURCE" ]; then
  codex plugin marketplace add "$SOURCE"
else
  codex plugin marketplace add "$SOURCE" --ref "$REF"
fi

case "$PROFILE" in
  workflows) PLUGINS='gloamere-workflows' ;;
  maintainer) PLUGINS='gloamere-eval' ;;
  complete) PLUGINS='gloamere-workflows gloamere-eval' ;;
  *) echo "Unknown install profile: $PROFILE" >&2; exit 2 ;;
esac

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

if [ -d "$SOURCE" ]; then
  SOURCE_DESCRIPTION=$SOURCE
else
  SOURCE_DESCRIPTION="${SOURCE}@${REF}"
fi
echo "Gloamere ${PROFILE} profile installed from marketplace ${SOURCE_DESCRIPTION}: $PLUGINS"
echo 'Start a new Codex task to load the installed skills.'
