---
name: tessera-doctor
description: 全面诊断 Tessera 市集、插件、版本、启用状态、registry/trust 与依赖漂移；默认只读，用户明确要求 remediation 时才逐项确认并委托 setup 修复。
---

# Tessera Doctor

默认执行只读体检；无法取得的证据标为 `UNKNOWN`。只有用户明确说“修复”“remediate”或同义意图时才能进入 remediation 模式。

## 诊断模式（默认）

1. 识别宿主、当前插件根和市集仓库根；仓库不可见时继续检查插件自身。
2. 按 `tessera-status` 读取安装版本与启用状态。当前 skill 已加载可证明 core active，但不能替代 CLI 对其它拼图的证据。
3. 检查双市集拼图集合、source、piece 目录、双端 manifest 名称与版本；检查 registry availability、候选隔离、trust_ref 与安装命令完全匹配。
4. 使用既有版本规则；只运行已安装拼图明确声明的 `version_check`。
5. 先给总状态，再输出 `检查项 | 结果 | 证据 | 建议`，最后列必要动作。诊断模式永不确认、执行或修改。

严重度保持：结构/trust 损坏或明确依赖缺失为 `FAIL`；可验证更新、禁用异常或非致命漂移为 `WARN`；证据不可得为 `UNKNOWN`；候选信息为 `INFO`。总状态仍按 `FAIL → error`、否则 `WARN → warning`、否则 `UNKNOWN → unknown`、其余 `healthy`。

## Remediation 模式（显式）

1. 必须先完成一轮只读诊断快照，再生成候选表：`id | 诊断 | scope | 动作/命令 | 影响 | 可逆性 | 验证 | 依赖`。
2. scope 只有以下语义：
   - `host-lifecycle`、trust 完全匹配的 `trusted-install`：可交给 `tessera-setup` 执行。
   - `repository-structure`、`trust`、`rollback`：只能输出 `plan-only`，不得在 doctor 内改文件或重配市集。
3. 每个可执行项单独请求确认；确认前再次展示完整命令。用户拒绝或未确认记为 `skipped`。
4. setup 执行后立即复查对应检查项；命令成功但状态未达到目标仍记为 `failed`。
5. 失败项的依赖后续记为 `blocked`；无依赖项可继续。最终输出 `succeeded / failed / skipped / blocked / plan-only`，并重新计算 doctor 总状态。

## 硬规则

- 默认模式始终零写入；remediation 不是批量同意，一次确认只授权一项。
- 只执行 setup 动作矩阵或与 `trust.yaml` 完全匹配的安装命令。
- 不自动修复 manifest/marketplace/trust，不执行 Git 回滚，不写遥测。
