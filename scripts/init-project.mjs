#!/usr/bin/env node
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { dirname, resolve } from 'node:path';

const START = '<!-- workflow-os:v2:start -->';
const END = '<!-- workflow-os:v2:end -->';

function usage() {
  console.log('Usage: node scripts/init-project.mjs --target <project-path> [--name <name>] [--dry-run]');
}

function options(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) continue;
    const [key, inline] = token.slice(2).split('=', 2);
    const next = argv[index + 1];
    values.set(key, inline ?? (next && !next.startsWith('--') ? (index += 1, next) : true));
  }
  return values;
}

async function exists(path) {
  try {
    await access(path, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

function managedGuidance() {
  return `${START}
# workflow-os v2

- 方向性 UI、数值、活动与技术选型先写入 \`docs/decisions/\`，负责人确认后才能实施。
- 调研、策划和实现可并行；同一文件或存在依赖的任务不可并行修改。
- 使用已安装的 \`wfos-core\` skill 路由能力；不可逆命令仍受 Codex/Claude 原生权限与项目 hook 约束。
- 运行 \`node <workflow-os-repo>/scripts/init-project.mjs\` 只补缺，不覆盖此项目的人类规则。
${END}
`;
}

async function copyMissing(path, content, dryRun, changes) {
  if (await exists(path)) {
    changes.push(`skip    ${path}`);
    return;
  }
  changes.push(`create  ${path}`);
  if (!dryRun) {
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, content, 'utf8');
  }
}

async function installGuidance(path, dryRun, changes) {
  const block = managedGuidance();
  if (!(await exists(path))) {
    changes.push(`create  ${path}`);
    if (!dryRun) await writeFile(path, block, 'utf8');
    return;
  }
  const current = await readFile(path, 'utf8');
  const start = current.indexOf(START);
  const end = current.indexOf(END);
  if ((start >= 0) !== (end >= 0) || (start >= 0 && end < start)) {
    throw new Error(`托管区标记损坏，拒绝修改：${path}`);
  }
  if (start >= 0) {
    const next = `${current.slice(0, start)}${block}${current.slice(end + END.length)}`;
    if (next !== current) changes.push(`update  ${path} (managed block)`);
    if (!dryRun && next !== current) await writeFile(path, next, 'utf8');
    return;
  }
  changes.push(`append  ${path} (managed block)`);
  if (!dryRun) await writeFile(path, `${current}${current.endsWith('\n') ? '\n' : '\n\n'}${block}`, 'utf8');
}

async function main() {
  const values = options(process.argv.slice(2));
  if (values.has('help') || !values.get('target')) {
    usage();
    process.exitCode = values.has('help') ? 0 : 1;
    return;
  }
  const root = resolve(String(values.get('target')));
  const name = String(values.get('name') ?? root.split(/[\\/]/).at(-1));
  const dryRun = values.has('dry-run');
  const changes = [];
  await copyMissing(`${root}/.workflow-os/project.yaml`, `schema: workflow-os/project@2\nname: ${JSON.stringify(name)}\ninitialized_at: ${JSON.stringify(new Date().toISOString())}\n`, dryRun, changes);
  await copyMissing(`${root}/docs/PROJECT.md`, `# ${name}\n\n## 目标\n\n- \n\n## 约束\n\n- \n`, dryRun, changes);
  await copyMissing(`${root}/docs/NOW.md`, '# 当前状态\n\n- \n', dryRun, changes);
  await copyMissing(`${root}/docs/INBOX.md`, '# 收集箱\n\n- \n', dryRun, changes);
  await copyMissing(`${root}/docs/decisions/README.md`, '# 决策\n\n方向性决策在确认前保持 pending。\n', dryRun, changes);
  await copyMissing(`${root}/docs/research/README.md`, '# 调研\n\n研究结论应保留来源与不确定性。\n', dryRun, changes);
  await installGuidance(`${root}/AGENTS.md`, dryRun, changes);
  console.log(`${dryRun ? 'Preview' : 'Initialized'} workflow-os project: ${root}`);
  for (const change of changes) console.log(change);
}

main().catch((error) => {
  console.error(`workflow-os init-project: ${error.message}`);
  process.exitCode = 1;
});
