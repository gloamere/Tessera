import { createHash } from 'node:crypto';
import { parseDocument } from 'yaml';

const WORK_STATUSES = new Set([
  'planned',
  'in_progress',
  'blocked',
  'waiting_clarification',
  'waiting_approval',
  'completed',
  'cancelled',
]);
const PRIORITIES = new Set(['low', 'medium', 'high', 'critical']);
const APPROVAL_STATES = new Set(['not_required', 'pending', 'approved', 'rejected']);
const DECISION_STATUSES = new Set(['pending', 'confirmed', 'rejected', 'superseded']);
const RESEARCH_MODES = new Set(['quick', 'standard', 'deep']);
const RESEARCH_STATUSES = new Set(['ready', 'awaiting_confirmation', 'researching', 'synthesizing', 'reviewing', 'completed', 'blocked', 'cancelled']);
const CONFIRMATION_STATES = new Set(['not_required', 'pending', 'approved', 'rejected']);

export function sha256(content) {
  return createHash('sha256').update(content).digest('hex');
}

export function inferDocumentKind(relativePath) {
  const normalized = relativePath.replaceAll('\\', '/');
  if (normalized.startsWith('docs/work/')) return 'work';
  if (normalized.startsWith('docs/decisions/')) return 'decision';
  if (normalized.startsWith('docs/research/')) return 'research';
  if (normalized.startsWith('docs/briefs/')) return 'brief';
  if (normalized === 'docs/PROJECT.md') return 'project';
  if (normalized === 'docs/NOW.md') return 'now';
  if (normalized === 'docs/INBOX.md') return 'inbox';
  return 'other';
}

export function isManagedRecordPath(relativePath) {
  const normalized = relativePath.replaceAll('\\', '/');
  return (normalized.startsWith('docs/work/') || normalized.startsWith('docs/decisions/') || normalized.startsWith('docs/research/'))
    && !normalized.endsWith('/README.md');
}

function titleFromMarkdown(content) {
  const match = content.match(/^#\s+(.+?)\s*$/m);
  return match?.[1]?.trim() ?? null;
}

function frontmatter(content) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) return { data: null, error: '缺少 YAML frontmatter（文件必须以 --- 开始和结束）。' };

  const yaml = parseDocument(match[1], { prettyErrors: false, uniqueKeys: true });
  if (yaml.errors.length > 0) {
    return { data: null, error: `YAML 无法解析：${yaml.errors[0].message}` };
  }
  const data = yaml.toJS();
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return { data: null, error: 'YAML frontmatter 必须是对象。' };
  }
  return { data, error: null };
}

function requiredString(data, name, errors) {
  const value = data[name];
  if (typeof value !== 'string' || value.trim() === '') {
    errors.push(`缺少或无效字段：${name}`);
    return null;
  }
  return value.trim();
}

function enumValue(data, name, accepted, errors) {
  const value = requiredString(data, name, errors);
  if (value && !accepted.has(value)) {
    errors.push(`${name} 必须是以下值之一：${[...accepted].join(', ')}`);
  }
  return value;
}

function isoTimestamp(data, name, errors) {
  const value = requiredString(data, name, errors);
  if (value && Number.isNaN(Date.parse(value))) errors.push(`${name} 必须是 ISO 日期或时间。`);
  return value;
}

function arrayOfStrings(data, name, errors) {
  const value = data[name] ?? [];
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || item.trim() === '')) {
    errors.push(`${name} 必须是字符串数组。`);
    return [];
  }
  return value.map((item) => item.trim());
}

function parseWork(data, title) {
  const errors = [];
  const schema = requiredString(data, 'schema', errors);
  if (schema && schema !== 'workflow-os/work-item@1') errors.push('schema 必须为 workflow-os/work-item@1。');
  const id = requiredString(data, 'id', errors);
  const type = requiredString(data, 'type', errors);
  const status = enumValue(data, 'status', WORK_STATUSES, errors);
  const priority = enumValue(data, 'priority', PRIORITIES, errors);
  const updatedAt = isoTimestamp(data, 'updated_at', errors);
  const approvalState = enumValue(data, 'approval_state', APPROVAL_STATES, errors);
  const clarificationSummary = data.clarification_summary == null
    ? null
    : requiredString(data, 'clarification_summary', errors);
  if (status === 'waiting_clarification' && !clarificationSummary) {
    errors.push('status 为 waiting_clarification 时必须填写 clarification_summary。');
  }
  const nextAction = data.next_action == null ? null : requiredString(data, 'next_action', errors);
  const dependsOn = arrayOfStrings(data, 'depends_on', errors);
  if (!title) errors.push('缺少一级标题。');

  if (errors.length > 0) return { error: errors.join(' ') };
  return {
    value: {
      id,
      type,
      status,
      priority,
      updatedAt,
      approvalStatus: approvalState,
      clarificationSummary,
      nextStep: nextAction,
      dependencies: dependsOn,
    },
  };
}

function parseDecision(data, title) {
  const errors = [];
  const schema = requiredString(data, 'schema', errors);
  if (schema && schema !== 'workflow-os/decision@1') errors.push('schema 必须为 workflow-os/decision@1。');
  const id = requiredString(data, 'id', errors);
  const workItemId = requiredString(data, 'work_item', errors);
  const status = enumValue(data, 'status', DECISION_STATUSES, errors);
  const updatedAt = isoTimestamp(data, 'updated_at', errors);
  if (!title) errors.push('缺少一级标题。');
  if (errors.length > 0) return { error: errors.join(' ') };
  return { value: { id, workItemId, status, updatedAt } };
}

function parseEvidenceCards(content, errors) {
  const cards = [];
  const headings = [...content.matchAll(/^###\s+Evidence:\s*([^\r\n]+)\r?\n([\s\S]*?)(?=^###\s+Evidence:|^##\s|(?![\s\S]))/gm)];
  for (const heading of headings) {
    const id = heading[1].trim();
    const fields = Object.fromEntries([...heading[2].matchAll(/^-\s+([^:]+):\s*(.+?)\s*$/gm)].map((match) => [match[1].trim().toLowerCase(), match[2].trim()]));
    if (!id || !fields.claim || !fields.url || !fields['source type'] || !fields.retrieved || !fields.relevance || !fields.caveat) {
      errors.push(`Evidence Card ${id || '(missing id)'} 缺少 Claim、URL、Source type、Retrieved、Relevance 或 Caveat。`);
      continue;
    }
    if (!/^https?:\/\//i.test(fields.url)) errors.push(`Evidence Card ${id} 的 URL 必须是 http(s) URL。`);
    if (Number.isNaN(Date.parse(fields.retrieved))) errors.push(`Evidence Card ${id} 的 Retrieved 必须是 ISO 日期或时间。`);
    cards.push({ id, ...fields });
  }
  return cards;
}

function parseResearch(data, title, content) {
  const errors = [];
  const schema = requiredString(data, 'schema', errors);
  if (schema && schema !== 'workflow-os/research@1') errors.push('schema 必须为 workflow-os/research@1。');
  const id = requiredString(data, 'id', errors);
  const mode = enumValue(data, 'mode', RESEARCH_MODES, errors);
  const status = enumValue(data, 'status', RESEARCH_STATUSES, errors);
  const question = requiredString(data, 'question', errors);
  const scope = requiredString(data, 'scope', errors);
  const recency = requiredString(data, 'recency', errors);
  const updatedAt = isoTimestamp(data, 'updated_at', errors);
  const nextAction = data.next_action == null ? null : requiredString(data, 'next_action', errors);
  const confirmation = enumValue(data, 'confirmation', CONFIRMATION_STATES, errors);
  const workItemId = data.work_item == null ? null : requiredString(data, 'work_item', errors);
  if (!title) errors.push('缺少一级标题。');
  if (mode === 'deep' && confirmation === 'not_required') errors.push('deep 研究必须等待或记录人工确认。');
  if (mode !== 'deep' && confirmation === 'pending') errors.push('只有 deep 研究可以使用 pending 确认状态。');
  const cards = parseEvidenceCards(content, errors);
  if (['reviewing', 'completed'].includes(status) && cards.length === 0) errors.push('处于 reviewing 或 completed 的研究至少需要一张 Evidence Card。');
  if (['reviewing', 'completed'].includes(status)) {
    const evidenceIds = new Set(cards.map((card) => card.id));
    for (const reference of content.matchAll(/\[\[evidence-([^\]]+)\]\]/g)) {
      if (!evidenceIds.has(reference[1])) errors.push(`结论引用了不存在的 Evidence Card: evidence-${reference[1]}。`);
    }
  }
  if (errors.length > 0) return { error: errors.join(' ') };
  return { value: { id, mode, status, question, scope, recency, updatedAt, nextAction, confirmation, workItemId } };
}

/**
 * Convert one Markdown file into the tiny, derived payload that is stored in
 * SQLite. Its body deliberately never enters the database.
 */
export function parseMarkdownDocument(relativePath, content, indexedAt = new Date().toISOString()) {
  const kind = inferDocumentKind(relativePath);
  const base = {
    path: relativePath.replaceAll('\\', '/'),
    kind,
    title: titleFromMarkdown(content),
    hash: sha256(content),
    indexedAt,
    parseError: null,
    workItem: null,
    decision: null,
    researchItem: null,
    links: [],
  };

  if (!isManagedRecordPath(relativePath)) return base;

  const parsedFrontmatter = frontmatter(content);
  if (parsedFrontmatter.error) return { ...base, parseError: parsedFrontmatter.error };
  const parsed = kind === 'work'
    ? parseWork(parsedFrontmatter.data, base.title)
    : kind === 'decision'
      ? parseDecision(parsedFrontmatter.data, base.title)
      : parseResearch(parsedFrontmatter.data, base.title, content);
  if (parsed.error) return { ...base, parseError: parsed.error };

  if (kind === 'work') {
    const workItem = parsed.value;
    return {
      ...base,
      workItem,
      links: workItem.dependencies.map((targetId) => ({
        sourceKind: 'work_item',
        sourceId: workItem.id,
        relation: 'depends_on',
        targetKind: 'work_item',
        targetId,
      })),
    };
  }
  if (kind === 'decision') return { ...base, decision: parsed.value };
  const researchItem = parsed.value;
  return {
    ...base,
    researchItem,
    links: researchItem.workItemId ? [{
      sourceKind: 'research', sourceId: researchItem.id, relation: 'research_for', targetKind: 'work_item', targetId: researchItem.workItemId,
    }] : [],
  };
}

export const metadataVocabulary = {
  workStatuses: [...WORK_STATUSES],
  priorities: [...PRIORITIES],
  approvalStates: [...APPROVAL_STATES],
  decisionStatuses: [...DECISION_STATUSES],
  researchModes: [...RESEARCH_MODES],
  researchStatuses: [...RESEARCH_STATUSES],
};
