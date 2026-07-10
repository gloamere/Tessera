import { randomUUID } from 'node:crypto';
import {
  access,
  mkdir,
  open,
  readFile,
  readdir,
  stat,
  unlink,
  writeFile,
} from 'node:fs/promises';
import { constants } from 'node:fs';
import { dirname, join, relative } from 'node:path';

const AUTO_START = '<!-- workflow-os:auto:start -->';
const AUTO_END = '<!-- workflow-os:auto:end -->';
const LOCK_MAX_AGE_MS = 5 * 60 * 1000;

export function toProjectPath(root, absolutePath) {
  return relative(root, absolutePath).replaceAll('\\', '/');
}

export async function pathExists(path) {
  try {
    await access(path, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

async function collectMarkdown(directory, root, result) {
  if (!(await pathExists(directory))) return;
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    const absolutePath = join(directory, entry.name);
    if (entry.isDirectory()) {
      await collectMarkdown(absolutePath, root, result);
    } else if (entry.isFile() && entry.name.endsWith('.md') && entry.name !== 'README.md') {
      result.push({
        path: toProjectPath(root, absolutePath),
        content: await readFile(absolutePath, 'utf8'),
      });
    }
  }
}

export async function readProjectMarkdown(root) {
  const documents = [];
  await collectMarkdown(join(root, 'docs'), root, documents);
  return documents.sort((left, right) => left.path.localeCompare(right.path));
}

export async function withIndexLock(root, action) {
  const lockPath = join(root, '.workflow', 'index.lock');
  await mkdir(dirname(lockPath), { recursive: true });

  let handle;
  try {
    handle = await open(lockPath, 'wx');
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const age = Date.now() - (await stat(lockPath)).mtimeMs;
    if (age > LOCK_MAX_AGE_MS) {
      await unlink(lockPath);
      return withIndexLock(root, action);
    }
    const busy = new Error('索引繁忙：请等待总指挥完成同步后重试。');
    busy.code = 'WORKFLOW_INDEX_BUSY';
    throw busy;
  }

  try {
    await handle.writeFile(`${JSON.stringify({ pid: process.pid, createdAt: new Date().toISOString() })}\n`);
    return await action();
  } finally {
    await handle.close();
    await unlink(lockPath).catch(() => undefined);
  }
}

function markdownList(items, empty) {
  return items.length > 0 ? items.map((item) => `- ${item}`).join('\n') : `- ${empty}`;
}

export function renderNowSummary(status) {
  const active = status.workItems.filter((item) => ['planned', 'in_progress', 'blocked', 'waiting_approval'].includes(item.status));
  const decisions = status.decisions.filter((decision) => decision.status === 'pending');
  const blockers = active.filter((item) => item.status === 'blocked');
  const clarifications = status.workItems.filter((item) => item.status === 'waiting_clarification');
  const researchWaiting = (status.researchItems ?? []).filter((item) => item.status === 'awaiting_confirmation');
  const lines = [
    AUTO_START,
    '## 自动总览',
    '',
    `> 由 workflow-os 在 ${new Date().toISOString()} 生成。请不要手工编辑此区块。`,
    '',
    '### 正在推进',
    markdownList(active.map((item) => `**${item.title}** [${item.id}] — ${item.status}${item.nextStep ? `；下一步：${item.nextStep}` : ''}`), '暂无进行中的工作包。'),
    '',
    '### 卡点',
    markdownList(blockers.map((item) => `**${item.title}** [${item.id}] — ${item.nextStep ?? '未填写下一步'}`), '暂无已标记卡点。'),
    '',
    '### 待澄清',
    markdownList(clarifications.map((item) => `**${item.title}** [${item.id}] — ${item.clarificationSummary}`), '暂无待澄清事项。'),
    '',
    '### 待拍板决策',
    markdownList(decisions.map((decision) => `**${decision.title}** [${decision.id}] → [${decision.workItemId}]`), '暂无待拍板决策。'),
    '',
    '### 待确认调研',
    markdownList(researchWaiting.map((item) => `**${item.title}** [${item.id}] — deep 研究计划等待确认`), '暂无待确认调研。'),
    AUTO_END,
    '',
  ];
  return lines.join('\n');
}

export async function writeNowSummary(root, status) {
  const nowPath = join(root, 'docs', 'NOW.md');
  await mkdir(dirname(nowPath), { recursive: true });
  const existing = (await pathExists(nowPath)) ? await readFile(nowPath, 'utf8') : '# 当前状态\n\n## 人工备注\n\n';
  const rendered = renderNowSummary(status);
  const start = existing.indexOf(AUTO_START);
  const end = existing.indexOf(AUTO_END);
  let next;
  if (start >= 0 && end >= start) {
    next = `${existing.slice(0, start)}${rendered}${existing.slice(end + AUTO_END.length)}`;
  } else {
    const separator = existing.endsWith('\n') ? '\n' : '\n\n';
    next = `${existing}${separator}${rendered}`;
  }
  await writeFile(nowPath, next, 'utf8');
}

function safeFilePart(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
}

export function makeStableId(prefix) {
  return `${prefix}-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${randomUUID().slice(0, 8)}`;
}

function quoteYaml(value) {
  return JSON.stringify(value);
}

export function workMarkdown({ id, title, type, priority = 'medium', approvalState = 'not_required' }) {
  const now = new Date().toISOString();
  return `---\nschema: workflow-os/work-item@1\nid: ${quoteYaml(id)}\ntype: ${quoteYaml(type)}\nstatus: planned\npriority: ${priority}\nupdated_at: ${quoteYaml(now)}\nnext_action: null\ndepends_on: []\napproval_state: ${approvalState}\nclarification_summary: null\n---\n\n# ${title}\n\n## 目标\n\n- \n\n## 待澄清\n\n- \n\n## 已确认\n\n- \n\n## 待办与下一步\n\n- \n\n## 结果\n\n- \n`;
}

export function decisionMarkdown({ id, title, workItemId }) {
  const now = new Date().toISOString();
  return `---\nschema: workflow-os/decision@1\nid: ${quoteYaml(id)}\nwork_item: ${quoteYaml(workItemId)}\nstatus: pending\nupdated_at: ${quoteYaml(now)}\n---\n\n# ${title}\n\n## 需要拍板\n\n- \n\n## 备选方案\n\n- \n\n## 最终结论\n\n- \n`;
}

export async function createRecord(root, kind, options) {
  const prefix = kind === 'work' ? 'work' : 'decision';
  const id = options.id ?? makeStableId(prefix);
  const directory = join(root, 'docs', kind === 'work' ? 'work' : 'decisions');
  const filename = `${safeFilePart(options.slug ?? id) || id}.md`;
  const target = join(directory, filename);
  if (await pathExists(target)) throw new Error(`目标文件已存在：${toProjectPath(root, target)}`);
  await mkdir(directory, { recursive: true });
  const content = kind === 'work'
    ? workMarkdown({ id, title: options.title, type: options.type, priority: options.priority, approvalState: options.approvalState })
    : decisionMarkdown({ id, title: options.title, workItemId: options.workItemId });
  await writeFile(target, content, 'utf8');
  return { id, path: toProjectPath(root, target), content };
}
