import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parse, stringify } from 'yaml';
import { makeStableId, pathExists, toProjectPath } from './project.mjs';

const MODES = new Set(['quick', 'standard', 'deep']);
const DISPATCH_START = '<!-- workflow-os:dispatch:start -->';
const DISPATCH_END = '<!-- workflow-os:dispatch:end -->';

function quote(value) { return JSON.stringify(value); }

export function researchMarkdown({ id, title, mode, scope, recency, workItemId }) {
  const now = new Date().toISOString();
  const deep = mode === 'deep';
  return `---\nschema: workflow-os/research@1\nid: ${quote(id)}\nmode: ${mode}\nstatus: ${deep ? 'awaiting_confirmation' : 'ready'}\nquestion: ${quote(title)}\nscope: ${quote(scope)}\nrecency: ${quote(recency)}\nupdated_at: ${quote(now)}\nnext_action: ${quote(deep ? '等待负责人确认研究计划。' : '生成 Dispatch Review 并派遣研究角色。')}\nconfirmation: ${deep ? 'pending' : 'not_required'}\nwork_item: ${workItemId ? quote(workItemId) : 'null'}\n---\n\n# ${title}\n\n## Research Brief\n\n- 要回答的问题：${title}\n- 范围：${scope}\n- 时效要求：${recency}\n\n## Dispatch Review\n\n${DISPATCH_START}\n尚未生成。运行 \`workflow-os research plan ${id}\`。\n${DISPATCH_END}\n\n## Evidence Cards\n\n<!-- 每张卡使用：### Evidence: evidence-1，随后 Claim、URL、Source type、Retrieved、Relevance、Caveat。 -->\n\n## Synthesis\n\n- 重要结论请写成：\`- Claim: ... [[evidence-evidence-1]]\`\n- 不确定性与冲突必须明确说明。\n\n## Sources\n\n- \n\n## Open Questions\n\n- \n`;
}

export async function createResearch(root, options) {
  if (!MODES.has(options.mode)) throw new Error('--mode 必须为 quick、standard 或 deep。');
  const id = options.id ?? makeStableId('research');
  const filename = `${(options.slug ?? id).trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48) || id}.md`;
  const target = join(root, 'docs', 'research', filename);
  if (await pathExists(target)) throw new Error(`目标文件已存在：${toProjectPath(root, target)}`);
  const { mkdir } = await import('node:fs/promises');
  await mkdir(join(root, 'docs', 'research'), { recursive: true });
  const content = researchMarkdown({ id, title: options.title, mode: options.mode, scope: options.scope, recency: options.recency, workItemId: options.workItemId });
  await writeFile(target, content, 'utf8');
  return { id, path: toProjectPath(root, target), content };
}

export function buildDispatchPlan(item) {
  const review = (role, task, sourceScope, model, reasoning, rounds, touchesApproval = false) => ({ role, task, source_scope: sourceScope, output: '结构化摘要 + Evidence Cards；不返回原始搜索日志。', model, reasoning, round_budget: rounds, independent: true, touches_human_signoff: touchesApproval });
  const scout = (suffix, sourceScope) => review('research-scout', `扫描${suffix}资料并提交可验证 Evidence Cards。`, sourceScope, 'gpt-5.6-terra', 'low', 1);
  const plan = item.mode === 'quick'
    ? [scout('本地项目、GitHub 与公开网页', 'local-project, github, public-web')]
    : [scout('本地项目与 GitHub', 'local-project, github'), scout('公开网页', 'public-web'), review('research-analyst', '比较证据、记录冲突并撰写 Synthesis。', 'evidence-cards only', 'gpt-5.6', 'medium', 1)];
  if (item.mode === 'deep') plan.push(review('research-auditor', '审计引用覆盖、冲突、时效和不确定性标记。', 'report and evidence-cards', 'gpt-5.6', 'high', 1, true));
  const executable = item.mode !== 'deep' || item.confirmation === 'approved';
  return { research_id: item.id, mode: item.mode, executable, dispatch_status: executable ? 'ready' : 'awaiting_confirmation', fallback: { model: 'available equivalent', rule: '总指挥记录不可用模型与降级理由；不得静默替换。' }, tasks: plan };
}

export function renderDispatchPlan(plan) {
  const lines = [`- 状态：${plan.dispatch_status}`, `- 可执行：${plan.executable ? '是' : '否'}`, '- 模型不可用：记录实际替代模型与理由，禁止静默降级。', '', '### Tasks'];
  for (const task of plan.tasks) lines.push(`- ${task.role}：${task.task}（${task.model} / ${task.reasoning} / ${task.round_budget} 轮；来源：${task.source_scope}；独立：${task.independent ? '是' : '否'}；触及拍板：${task.touches_human_signoff ? '是' : '否'}）`);
  return `${DISPATCH_START}\n${lines.join('\n')}\n${DISPATCH_END}`;
}

export async function saveDispatchPlan(root, path, plan) {
  const target = join(root, path);
  const current = await readFile(target, 'utf8');
  const rendered = renderDispatchPlan(plan);
  const start = current.indexOf(DISPATCH_START);
  const end = current.indexOf(DISPATCH_END);
  if (start < 0 || end < start) throw new Error(`${path} 缺少 Dispatch Review 托管区。`);
  await writeFile(target, `${current.slice(0, start)}${rendered}${current.slice(end + DISPATCH_END.length)}`, 'utf8');
}

export async function approveResearch(root, path) {
  const target = join(root, path);
  const content = await readFile(target, 'utf8');
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) throw new Error(`${path} 缺少 YAML frontmatter。`);
  const data = parse(match[1]);
  data.confirmation = 'approved';
  data.status = 'ready';
  data.updated_at = new Date().toISOString();
  data.next_action = '派遣经审查的 deep 研究角色。';
  const frontmatter = `---\n${stringify(data).trimEnd()}\n---`;
  await writeFile(target, `${frontmatter}${content.slice(match[0].length)}`, 'utf8');
}
