---
schema: wfos/decision@1
id: bd-install-channel
status: approved
created: 2026-07-11
approved: 2026-07-11
---

# bd 安装通道统一

## 背景
本机双安装:C:\env\beads_0.62.0_windows_amd64\bd.exe(PATH 首位,0.62.0)遮蔽 npm 全局 @beads/bd(1.0.2 shim)。上游已迁 gastownhall/beads,最新 1.1.0。不统一则升级流死循环(npm 升级后 version 探测仍由旧 exe 应答)。

## 选项
- **A(推荐)**:统一到 npm 通道——`npm install -g @beads/bd@latest` 升至 1.x,从 PATH 移除 C:\env\beads_0.62.0_windows_amd64,删除该目录。0.62→1.x 有大版本跨越,升级后跑 `bd doctor` 与 `bd ready` 验证数据无损。
- **B**:维持手解 exe,bd 升级永远 manual,wfos 升级链对 bd 只提醒不执行。

## 结论
选 **A**:统一到 npm 通道。执行记录如下。

**PATH 处理**:`beads_0.62.0` 条目实际登记在 **Machine(系统)PATH**,不在 User PATH。写回前已将原始 Machine/User PATH 完整备份至 `.superpowers/sdd/path-backup.txt`。仅移除 `;C:\env\beads_0.62.0_windows_amd64` 这一段,其余内容(含一处历史遗留的双分号 `;;`)原样保留未动。

**目录处理(谨慎化执行)**:决策文案原写「删除该目录」,实际执行时改为**重命名**而非删除——`C:\env\beads_0.62.0_windows_amd64` → `C:\env\beads_0.62.0_backup`,保留一周作回退用,到期后可安全物理删除。这是对原决策的谨慎化落地,非决策内容变更。

**升级尝试**:`npm install -g @beads/bd@latest` 执行失败——npm 包本身从 registry.npmjs.org 正常解析(该源可达),但 postinstall 脚本需从 GitHub Releases(github.com / objects.githubusercontent.com)下载 v1.1.0 二进制,该域名在本机网络环境下连接超时(`curl` 反复验证:`Connection timed out`,registry.npmjs.org 同时段可正常 200)。判断为本机网络对 github.com 的出站限制,非命令或凭证问题,未做代理等范围外操作。npm 安装失败后**自动回滚,未破坏原有安装**——`npm list -g @beads/bd` 确认仍为 `@beads/bd@1.0.2`,`bd.cmd` 可正常运行。

**验证结果**:
- 新开进程读取更新后的 Machine+User PATH,`where bd` 仅解析到 `C:\Users\Administrator\AppData\Roaming\npm\bd`(.cmd),`C:\env` 路径已不在候选中,通道统一目标达成。
- `bd --version` → `bd version 1.0.2 (a3f834b3)`,满足「1.x」要求(未达到 latest 1.1.0,因上述网络限制,如实记录,未强行绕过)。
- 在 G:\Claude\workflow-os 下 `bd ready`:退出码 0,读取到既有 .beads 数据,输出「🔄 bd upgraded from v0.62.0 to v1.0.2 since last use」「✨ No ready work found (all issues have blocking dependencies)」,无报错。
- `bd doctor`:67 passed / 7 warnings / 0 errors。7 条 warning 均为 git hooks 版本落后、.gitignore 缺失新增排除项、Claude 插件未装、无 upstream 等配置类提示,与数据完整性无关,未见数据丢失或损坏迹象。
- 副作用记录:`bd ready`/`bd doctor` 运行时 bd 自身触发了一次 auto-export,产生 `.beads/export-state.json`(新文件)并将 `.beads/issues.jsonl` 暂存入 git index(新文件)。为避免本次决策提交范围扩大,已执行 `git restore --staged .beads/issues.jsonl` 撤销暂存,两个文件保留为 untracked,不随本次 docs/decisions 提交带入。

**遗留事项**:bd 版本仍停留在 1.0.2,未达 latest 1.1.0;待网络环境可达 github.com 后,可重新执行 `npm install -g @beads/bd@latest` 完成完整升级并跑 `bd doctor` 复核。`C:\env\beads_0.62.0_backup` 建议一周后(约 2026-07-18)确认无需回退后再物理删除。
