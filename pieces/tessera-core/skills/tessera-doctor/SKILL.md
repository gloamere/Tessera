---
name: tessera-doctor
description: 当用户要全面体检 Tessera、诊断市集/插件/版本/registry/trust/依赖漂移，或问“为什么 Tessera 状态不一致”时使用。只读检查并给修复建议，不自动安装、升级或改文件。
---

# Tessera Doctor

执行只读体检；无法取得的证据标为 `UNKNOWN`，不得猜测或把未知写成失败。

## 检查顺序

1. **识别宿主与根目录**：确认 Codex/Claude、当前 skill 插件根，以及能否定位 Tessera 市集仓库根。仓库根不可见时继续检查插件自身，不报假故障。
2. **当前会话与 CLI**：按 `tessera-status` 的宿主命令读取插件列表。CLI 失败但本 skill 已加载时，`tessera-core` 记为 `PASS（当前会话已加载）`，CLI 能见度记为 `UNKNOWN`。
3. **市集与结构**：仓库根可见时检查双市集拼图集合、source、piece 目录、双端 manifest 名称与版本是否一致；不可见则 `UNKNOWN`。
4. **版本状态**：比较已装版与市集/manifest 版：
   - 完全相同 → `current`。
   - `+` 前基础版本相同、build metadata 不同 → `refresh-available`。
   - 两端都是 `major.minor.patch` 且市集更高 → `update-available`；已装更高 → `ahead`。
   - 缺值、预发布版本无法可靠比较或格式不明 → `unknown`。
5. **registry / trust**：可见时检查 `availability`、`not-integrated` 隔离、`trust_ref` 与安装命令完全匹配；未集成候选只记 `INFO`，不算故障。
6. **外部依赖**：只运行已安装拼图在 `piece.yaml` 明确声明的 `version_check`。未声明即 `PASS（无外部依赖）`。

## 严重度与总状态

- `FAIL`：结构/manifest 损坏、双市集不一致、trust 命令不一致、已安装拼图的明确依赖缺失。
- `WARN`：存在可验证的刷新/升级、配置漂移或非致命异常。
- `UNKNOWN`：证据不可得；不等于失败。
- `PASS`：检查有证据且一致。`INFO` 不影响总状态。

总状态按 `FAIL → error`、否则 `WARN → warning`、否则存在 `UNKNOWN → unknown`、其余 `healthy`。

## 输出

先给总状态，再输出：`检查项 | 结果 | 证据 | 建议`。最后只列必要修复动作；安装/刷新命令必须来自 `tessera-setup` 与 `trust.yaml`，执行前仍需用户确认。doctor 自身永不修改文件、安装插件、升级依赖或写入遥测。
