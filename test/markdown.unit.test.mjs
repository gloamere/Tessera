import test from 'node:test';
import assert from 'node:assert/strict';
import {
  inferDocumentKind,
  isManagedRecordPath,
  parseMarkdownDocument,
  sha256,
} from '../src/markdown.mjs';

const INDEXED_AT = '2026-01-01T00:00:00.000Z';

function document(frontmatter, body = '# 标题\n') {
  const yaml = Object.entries(frontmatter)
    .map(([key, value]) => `${key}: ${value}`)
    .join('\n');
  return `---\n${yaml}\n---\n\n${body}`;
}

const WORK = {
  schema: 'workflow-os/work-item@1',
  id: '"work-1"',
  type: '"feature"',
  status: 'planned',
  priority: 'medium',
  updated_at: '"2026-01-01T00:00:00.000Z"',
  approval_state: 'not_required',
};

const DECISION = {
  schema: 'workflow-os/decision@1',
  id: '"decision-1"',
  work_item: '"work-1"',
  status: 'pending',
  updated_at: '"2026-01-01T00:00:00.000Z"',
};

const RESEARCH = {
  schema: 'workflow-os/research@1',
  id: '"research-1"',
  mode: 'standard',
  status: 'ready',
  question: '"哪个方案更省 token"',
  scope: '"public-web"',
  recency: '"current"',
  updated_at: '"2026-01-01T00:00:00.000Z"',
  confirmation: 'not_required',
};

// A card id is a bare slug; a citation prefixes it with `evidence-`.
function evidenceCard(id = 'official-docs', overrides = {}) {
  const fields = {
    Claim: '索引可以从 Markdown 重建',
    URL: 'https://example.com/a',
    'Source type': 'docs',
    Retrieved: '2026-01-01',
    Relevance: 'high',
    Caveat: '单一来源',
    ...overrides,
  };
  const lines = Object.entries(fields)
    .filter(([, value]) => value !== null)
    .map(([key, value]) => `- ${key}: ${value}`);
  return `### Evidence: ${id}\n${lines.join('\n')}\n`;
}

test('inferDocumentKind maps managed folders and well-known files', () => {
  const cases = [
    ['docs/work/a.md', 'work'],
    ['docs/decisions/a.md', 'decision'],
    ['docs/research/a.md', 'research'],
    ['docs/briefs/a.md', 'brief'],
    ['docs/PROJECT.md', 'project'],
    ['docs/NOW.md', 'now'],
    ['docs/INBOX.md', 'inbox'],
    ['docs/sources/a.md', 'other'],
    ['README.md', 'other'],
    ['docs\\work\\a.md', 'work'],
  ];
  for (const [path, expected] of cases) {
    assert.equal(inferDocumentKind(path), expected, path);
  }
});

test('only work, decision and research files are parsed as records', () => {
  const cases = [
    ['docs/work/a.md', true],
    ['docs/decisions/a.md', true],
    ['docs/research/a.md', true],
    ['docs/work/README.md', false],
    ['docs/briefs/a.md', false],
    ['docs/NOW.md', false],
  ];
  for (const [path, expected] of cases) {
    assert.equal(isManagedRecordPath(path), expected, path);
  }
});

test('an unmanaged document is indexed without frontmatter parsing', () => {
  const content = '# 项目\n\n没有 frontmatter。\n';
  const parsed = parseMarkdownDocument('docs/PROJECT.md', content, INDEXED_AT);
  assert.equal(parsed.kind, 'project');
  assert.equal(parsed.title, '项目');
  assert.equal(parsed.parseError, null);
  assert.equal(parsed.workItem, null);
  assert.equal(parsed.hash, sha256(content));
});

test('frontmatter shape errors are reported instead of thrown', () => {
  const cases = [
    ['# 只有标题\n', /缺少 YAML frontmatter/],
    ['---\nid: "a"\nid: "b"\n---\n\n# 标题\n', /YAML 无法解析/],
    ['---\n- a\n- b\n---\n\n# 标题\n', /必须是对象/],
    ['---\nid: "unterminated\n---\n\n# 标题\n', /YAML 无法解析/],
  ];
  for (const [content, expected] of cases) {
    const parsed = parseMarkdownDocument('docs/work/a.md', content, INDEXED_AT);
    assert.match(parsed.parseError ?? '', expected, JSON.stringify(content));
    assert.equal(parsed.workItem, null);
  }
});

test('a valid work item yields metadata and depends_on links', () => {
  const content = document({ ...WORK, depends_on: '["work-2", "work-3"]', next_action: '"写测试"' });
  const parsed = parseMarkdownDocument('docs/work/a.md', content, INDEXED_AT);

  assert.equal(parsed.parseError, null);
  assert.equal(parsed.workItem.id, 'work-1');
  assert.equal(parsed.workItem.status, 'planned');
  assert.equal(parsed.workItem.nextStep, '写测试');
  assert.deepEqual(parsed.workItem.dependencies, ['work-2', 'work-3']);
  assert.deepEqual(parsed.links.map((link) => link.targetId), ['work-2', 'work-3']);
  assert.equal(parsed.links[0].relation, 'depends_on');
});

test('work item field validation rejects each malformed field', () => {
  const cases = [
    [{ schema: 'workflow-os/other@1' }, /schema 必须为 workflow-os\/work-item@1/],
    [{ id: '""' }, /缺少或无效字段：id/],
    [{ status: 'shipped' }, /status 必须是以下值之一/],
    [{ priority: 'urgent' }, /priority 必须是以下值之一/],
    [{ approval_state: 'maybe' }, /approval_state 必须是以下值之一/],
    [{ updated_at: '"not-a-date"' }, /updated_at 必须是 ISO 日期或时间/],
    [{ depends_on: '["", "work-2"]' }, /depends_on 必须是字符串数组/],
    [{ depends_on: '"work-2"' }, /depends_on 必须是字符串数组/],
    [{ status: 'waiting_clarification' }, /必须填写 clarification_summary/],
  ];
  for (const [override, expected] of cases) {
    const parsed = parseMarkdownDocument('docs/work/a.md', document({ ...WORK, ...override }), INDEXED_AT);
    assert.match(parsed.parseError ?? '', expected, JSON.stringify(override));
  }
});

test('a work item missing its level-one heading is rejected', () => {
  const content = document(WORK, '没有一级标题。\n');
  const parsed = parseMarkdownDocument('docs/work/a.md', content, INDEXED_AT);
  assert.match(parsed.parseError, /缺少一级标题/);
});

test('waiting_clarification is accepted once a summary is present', () => {
  const content = document({ ...WORK, status: 'waiting_clarification', clarification_summary: '"范围是否含后台"' });
  const parsed = parseMarkdownDocument('docs/work/a.md', content, INDEXED_AT);
  assert.equal(parsed.parseError, null);
  assert.equal(parsed.workItem.clarificationSummary, '范围是否含后台');
});

test('decision records validate their work item reference', () => {
  const valid = parseMarkdownDocument('docs/decisions/a.md', document(DECISION), INDEXED_AT);
  assert.equal(valid.parseError, null);
  assert.equal(valid.decision.workItemId, 'work-1');

  const cases = [
    [{ work_item: '""' }, /缺少或无效字段：work_item/],
    [{ status: 'maybe' }, /status 必须是以下值之一/],
    [{ schema: 'workflow-os/work-item@1' }, /schema 必须为 workflow-os\/decision@1/],
  ];
  for (const [override, expected] of cases) {
    const parsed = parseMarkdownDocument('docs/decisions/a.md', document({ ...DECISION, ...override }), INDEXED_AT);
    assert.match(parsed.parseError ?? '', expected, JSON.stringify(override));
  }
});

test('research confirmation rules distinguish deep from quick and standard', () => {
  const cases = [
    [{ mode: 'deep', confirmation: 'not_required' }, /deep 研究必须等待或记录人工确认/],
    [{ mode: 'standard', confirmation: 'pending' }, /只有 deep 研究可以使用 pending 确认状态/],
    [{ mode: 'quick', confirmation: 'pending' }, /只有 deep 研究可以使用 pending 确认状态/],
  ];
  for (const [override, expected] of cases) {
    const parsed = parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, ...override }), INDEXED_AT);
    assert.match(parsed.parseError ?? '', expected, JSON.stringify(override));
  }

  const deep = parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, mode: 'deep', confirmation: 'pending' }), INDEXED_AT);
  assert.equal(deep.parseError, null);
  assert.equal(deep.researchItem.confirmation, 'pending');
});

test('research links to its work item when one is declared', () => {
  const linked = parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, work_item: '"work-1"' }), INDEXED_AT);
  assert.deepEqual(linked.links, [{
    sourceKind: 'research',
    sourceId: 'research-1',
    relation: 'research_for',
    targetKind: 'work_item',
    targetId: 'work-1',
  }]);

  const unlinked = parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, work_item: 'null' }), INDEXED_AT);
  assert.deepEqual(unlinked.links, []);
  assert.equal(unlinked.researchItem.workItemId, null);
});

test('a reviewing dossier needs at least one complete Evidence Card', () => {
  const empty = parseMarkdownDocument(
    'docs/research/a.md',
    document({ ...RESEARCH, status: 'reviewing' }, '# 标题\n\n## Evidence Cards\n'),
    INDEXED_AT,
  );
  assert.match(empty.parseError, /至少需要一张 Evidence Card/);

  const complete = parseMarkdownDocument(
    'docs/research/a.md',
    document({ ...RESEARCH, status: 'reviewing' }, `# 标题\n\n## Evidence Cards\n\n${evidenceCard()}`),
    INDEXED_AT,
  );
  assert.equal(complete.parseError, null);
});

test('Evidence Card fields are validated individually', () => {
  const cases = [
    [{ Caveat: null }, /缺少 Claim、URL、Source type、Retrieved、Relevance 或 Caveat/],
    [{ Claim: null }, /缺少 Claim、URL、Source type、Retrieved、Relevance 或 Caveat/],
    [{ URL: 'ftp://example.com/a' }, /URL 必须是 http\(s\) URL/],
    [{ Retrieved: '不是日期' }, /Retrieved 必须是 ISO 日期或时间/],
  ];
  for (const [override, expected] of cases) {
    const body = `# 标题\n\n## Evidence Cards\n\n${evidenceCard('official-docs', override)}`;
    const parsed = parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, status: 'reviewing' }, body), INDEXED_AT);
    assert.match(parsed.parseError ?? '', expected, JSON.stringify(override));
  }
});

test('a completed dossier may cite a card that exists and may not cite one that does not', () => {
  const cited = `# 标题\n\n## Evidence Cards\n\n${evidenceCard('official-docs')}\n## Synthesis\n\n- Claim: 甲 [[evidence-official-docs]]\n`;
  assert.equal(parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, status: 'completed' }, cited), INDEXED_AT).parseError, null);

  const dangling = `${cited}- Claim: 乙 [[evidence-missing]]\n`;
  const parsed = parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, status: 'completed' }, dangling), INDEXED_AT);
  assert.match(parsed.parseError, /结论引用了不存在的 Evidence Card: evidence-missing/);
});

test('a dangling citation is tolerated before the dossier reaches review', () => {
  const body = '# 标题\n\n## Synthesis\n\n- Claim: 草稿 [[evidence-missing]]\n';
  const parsed = parseMarkdownDocument('docs/research/a.md', document({ ...RESEARCH, status: 'researching' }, body), INDEXED_AT);
  assert.equal(parsed.parseError, null);
});

test('a parse error keeps the document indexable and its hash stable', () => {
  const content = document({ ...WORK, status: 'shipped' });
  const parsed = parseMarkdownDocument('docs/work/a.md', content, INDEXED_AT);
  assert.equal(parsed.path, 'docs/work/a.md');
  assert.equal(parsed.kind, 'work');
  assert.equal(parsed.title, '标题');
  assert.equal(parsed.hash, sha256(content));
  assert.equal(parsed.indexedAt, INDEXED_AT);
  assert.deepEqual(parsed.links, []);
  assert.ok(parsed.parseError);
});

test('backslash paths are normalized before indexing', () => {
  const parsed = parseMarkdownDocument('docs\\work\\a.md', document(WORK), INDEXED_AT);
  assert.equal(parsed.path, 'docs/work/a.md');
  assert.equal(parsed.parseError, null);
});
