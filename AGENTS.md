# Agent Instructions

## ⚠️ 分支工作流(Codex 必读)

**统一在 `main` 分支开发与同步。**

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
# … 开发、提交 …
git push origin main
```

- `main` 是唯一工作分支与事实来源；不要创建或依赖 `codex-dev`。
- 开工前先同步 `main`。有未提交改动时先确认其归属，不要用重置命令覆盖它。

---

## 任务规划

- 会话内的规划、检查清单和执行顺序使用宿主 Agent 的原生能力；不要为了简单、明确的任务引入外部任务后端。

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var
