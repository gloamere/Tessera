#!/usr/bin/env sh
# Tessera 新机引导(macOS / Linux)。Windows 用 scripts/bootstrap-machine.ps1。
# 薄壳:检测前置 → clone 固定 tag → 构建门二进制 → 跑 tessera setup(dry-run)。
# 重活在 Go 的 `tessera setup` 里(跨平台)。
set -eu

INSTALL_ROOT="${INSTALL_ROOT:-$HOME/tessera}"
REPO="${REPO:-https://github.com/gloamere/Tessera.git}"
REF="${REF:-v2.0.0-beta.1}"
INSTALL_CODEX=0
SKIP_TESTS=0

for arg in "$@"; do
  case "$arg" in
    --install-codex) INSTALL_CODEX=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    --root=*) INSTALL_ROOT="${arg#--root=}" ;;
    --ref=*) REF="${arg#--ref=}" ;;
    *) echo "未知参数:$arg" >&2; exit 2 ;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "缺少必需命令:$1" >&2; exit 1; }; }
need git
need go

# 拒绝覆盖已有非空目录
if [ -d "$INSTALL_ROOT" ] && [ -n "$(ls -A "$INSTALL_ROOT" 2>/dev/null)" ]; then
  echo "安装目录已存在且非空,拒绝覆盖:$INSTALL_ROOT" >&2
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_ROOT")"
git clone --branch "$REF" --depth 1 --single-branch "$REPO" "$INSTALL_ROOT"

cd "$INSTALL_ROOT"
RESOLVED="$(git rev-parse --verify HEAD)"
echo "Tessera installed at $INSTALL_ROOT ($RESOLVED)"

# 构建当前平台门二进制(零依赖、离线可编)
GOTOOLCHAIN=local go build -o "pieces/tessera-core/bin/tessera" ./cmd/tessera
echo "built tessera -> pieces/tessera-core/bin/tessera"

if [ "$SKIP_TESTS" -eq 0 ]; then
  GOTOOLCHAIN=local go test ./...
fi

# 展示六阶段计划 + 信任复核(dry-run,不注册)
CODEX_FLAG=""
[ "$INSTALL_CODEX" -eq 1 ] && CODEX_FLAG="--codex"
./pieces/tessera-core/bin/tessera setup --root . $CODEX_FLAG

echo ""
echo "下一步:"
echo "  审阅上面的信任复核后,注册市集:"
echo "    ./pieces/tessera-core/bin/tessera setup --root \"$INSTALL_ROOT\" --register $CODEX_FLAG"
echo "  新建项目:"
echo "    ./pieces/tessera-core/bin/tessera init --target <project-path> --name \"Project Name\""
