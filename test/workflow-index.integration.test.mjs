import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  utimesSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse as parseYaml, stringify as stringifyYaml } from 'yaml';

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const cli = join(packageRoot, 'bin', 'workflow-os.mjs');

function makeProject(t) {
  const root = mkdtempSync(join(tmpdir(), 'workflow-os-index-'));
  t.after(() => rmSync(root, { recursive: true, force: true, maxRetries: 3 }));
  return root;
}

function run(root, args, expectedStatus = 0) {
  const result = spawnSync(process.execPath, [cli, ...args], {
    cwd: root,
    encoding: 'utf8',
  });

  if (result.error) throw result.error;
  assert.equal(
    result.status,
    expectedStatus,
    `workflow-os ${args.join(' ')} exited unexpectedly.\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`,
  );
  return result;
}

function runJson(root, args, expectedStatus = 0) {
  const result = run(root, args, expectedStatus);
  try {
    return JSON.parse(result.stdout);
  } catch (error) {
    assert.fail(`Expected JSON from workflow-os ${args.join(' ')}.\n${error.message}\nstdout:\n${result.stdout}`);
  }
}

function initializedProject(t, options = []) {
  const root = makeProject(t);
  run(root, ['init', ...options]);
  return root;
}

function workPath(root, slug) {
  return join(root, 'docs', 'work', `${slug}.md`);
}

function validWorkMarkdown({ id, title = id, dependsOn = [], status = 'planned', clarificationSummary = null }) {
  return `---
schema: workflow-os/work-item@1
id: ${id}
type: feature
status: ${status}
priority: medium
updated_at: "2026-07-10T12:00:00.000Z"
next_action: null
depends_on: ${JSON.stringify(dependsOn)}
approval_state: not_required
clarification_summary: ${JSON.stringify(clarificationSummary)}
---

# ${title}
`;
}

test('init creates the local-only index ignore policy without creating a database', (t) => {
  const root = initializedProject(t, ['--codex', '--obsidian']);

  assert.equal(existsSync(join(root, '.workflow', 'index.sqlite')), false);
  const ignore = readFileSync(join(root, '.workflow', '.gitignore'), 'utf8');
  assert.match(ignore, /^index\.sqlite\*/m);
  assert.match(ignore, /^index\.lock$/m);
  assert.match(ignore, /^runtime\/$/m);
  assert.equal(existsSync(join(root, 'docs', 'NOW.md')), true);
  assert.equal(existsSync(join(root, 'AGENTS.md')), true);
  assert.equal(existsSync(join(root, 'docs', 'ui', 'TASTE.md')), true);
  assert.equal(existsSync(join(root, '.workflow', 'extensions', 'ui', 'registry.yaml')), true);
});

test('init injects a managed AGENTS block without overwriting project instructions or duplicating it', (t) => {
  const root = makeProject(t);
  const agentsPath = join(root, 'AGENTS.md');
  writeFileSync(agentsPath, '# Existing project rules\n\n- Keep this rule.\n', 'utf8');
  run(root, ['init', '--codex']);
  run(root, ['init', '--codex']);

  const agents = readFileSync(agentsPath, 'utf8');
  assert.match(agents, /Keep this rule/);
  assert.equal((agents.match(/<!-- workflow-os:start -->/g) ?? []).length, 1);
  assert.equal((agents.match(/<!-- workflow-os:end -->/g) ?? []).length, 1);
  const manifest = parseYaml(readFileSync(join(root, '.workflow', 'manifest.yaml'), 'utf8'));
  assert.equal(manifest.codex.enabled, true);
  assert.equal(typeof manifest.managed_files['workflow/agent-budget.yaml'].installed_hash, 'string');
});

test('guard records bounded agent rounds and stops repeated no-progress errors', (t) => {
  const root = initializedProject(t);
  const first = runJson(root, ['guard', 'work-loop', '--outcome', 'no-progress', '--error', 'same failure', '--json']);
  assert.equal(first.state.decision, 'continue');
  const second = runJson(root, ['guard', 'work-loop', '--outcome', 'no-progress', '--error', 'same failure', '--json'], 2);
  assert.equal(second.state.decision, 'stop');
  assert.ok(second.state.reasons.includes('达到 no_progress_limit'));
  assert.ok(second.state.reasons.includes('达到 repeated_error_limit'));
  assert.equal(existsSync(join(root, '.workflow', 'runtime', 'work-loop.json')), true);
});

test('upgrade plans template changes and preserves a locally overridden file', (t) => {
  const root = initializedProject(t);
  const manifestPath = join(root, '.workflow', 'manifest.yaml');
  const manifest = parseYaml(readFileSync(manifestPath, 'utf8'));
  manifest.managed_files['docs/PROJECT.md'].source_hash = 'outdated-template-hash';
  writeFileSync(manifestPath, stringifyYaml(manifest), 'utf8');

  const plan = runJson(root, ['upgrade', '--plan', '--json']);
  assert.equal(plan.actions.find((action) => action.source === 'docs/PROJECT.md').kind, 'update');
  run(root, ['upgrade', '--apply']);

  const projectPath = join(root, 'docs', 'PROJECT.md');
  writeFileSync(projectPath, `${readFileSync(projectPath, 'utf8')}\nLocal project rule.\n`, 'utf8');
  const refreshed = parseYaml(readFileSync(manifestPath, 'utf8'));
  refreshed.managed_files['docs/PROJECT.md'].source_hash = 'outdated-template-hash-again';
  writeFileSync(manifestPath, stringifyYaml(refreshed), 'utf8');
  const overriddenPlan = runJson(root, ['upgrade', '--plan', '--json']);
  assert.equal(overriddenPlan.actions.find((action) => action.source === 'docs/PROJECT.md').kind, 'local_override');
  run(root, ['upgrade', '--apply']);
  assert.match(readFileSync(projectPath, 'utf8'), /Local project rule/);
});

test('clarification state is indexed and requires a concise summary', (t) => {
  const root = initializedProject(t);
  const target = workPath(root, 'mall-scope');
  writeFileSync(
    target,
    validWorkMarkdown({
      id: 'work-mall-scope',
      title: 'Clarify mall scope',
      status: 'waiting_clarification',
      clarificationSummary: '确认改造玩家客户端主界面还是后台配置。',
    }),
    'utf8',
  );

  const status = runJson(root, ['status', '--json']);
  assert.deepEqual(status.needsClarification.map((item) => item.id), ['work-mall-scope']);
  assert.equal(status.needsClarification[0].clarificationSummary, '确认改造玩家客户端主界面还是后台配置。');

  writeFileSync(target, readFileSync(target, 'utf8').replace(/clarification_summary: .+/, 'clarification_summary: null'), 'utf8');
  const validation = runJson(root, ['validate', '--json'], 1);
  assert.ok(validation.errors.some((error) => error.code === 'parse_error'));
  const invalidStatus = runJson(root, ['status', '--json']);
  assert.equal(invalidStatus.workItems.some((item) => item.id === 'work-mall-scope'), false);
});

test('created records are indexed, manual frontmatter edits update status, and context stays compact', (t) => {
  const root = initializedProject(t);

  run(root, [
    'work', 'create', 'Prepare assets',
    '--id', 'work-assets',
    '--slug', 'prepare-assets',
    '--type', 'research',
  ]);
  run(root, [
    'work', 'create', 'Improve mall UI',
    '--id', 'work-mall-ui',
    '--slug', 'mall-ui',
    '--type', 'ui',
    '--priority', 'high',
    '--approval-state', 'pending',
  ]);
  run(root, [
    'decision', 'create', 'Choose mall visual direction',
    '--id', 'decision-mall-ui',
    '--slug', 'mall-ui-direction',
    '--work-item', 'work-mall-ui',
  ]);

  const mallUiPath = workPath(root, 'mall-ui');
  const originalStat = statSync(mallUiPath);
  const edited = readFileSync(mallUiPath, 'utf8')
    .replace('status: planned', 'status: blocked')
    .replace(/^updated_at: .+$/m, 'updated_at: "2026-07-10T15:00:00.000Z"')
    .replace('next_action: null', 'next_action: "Resolve fixed-layout constraints"')
    .replace('depends_on: []', 'depends_on: [work-assets]');
  writeFileSync(mallUiPath, edited, 'utf8');
  // Keep the old mtime to prove the refresh is content-hash based rather than mtime based.
  utimesSync(mallUiPath, originalStat.atime, originalStat.mtime);

  const status = runJson(root, ['status', '--json']);
  const mallUi = status.workItems.find((item) => item.id === 'work-mall-ui');
  assert.deepEqual(
    {
      status: mallUi.status,
      priority: mallUi.priority,
      nextStep: mallUi.nextStep,
      approvalStatus: mallUi.approvalStatus,
    },
    {
      status: 'blocked',
      priority: 'high',
      nextStep: 'Resolve fixed-layout constraints',
      approvalStatus: 'pending',
    },
  );
  assert.ok(status.blocked.some((item) => item.id === 'work-mall-ui'));
  assert.ok(status.nextSteps.some((item) => item.id === 'work-mall-ui'));
  assert.ok(status.pendingApproval.some((item) => item.id === 'work-mall-ui'));
  assert.ok(status.pendingApproval.some((item) => item.id === 'decision-mall-ui'));

  const context = runJson(root, ['context', 'work-mall-ui', '--json']);
  assert.equal(context.error, null);
  assert.equal(context.workItem.id, 'work-mall-ui');
  assert.equal(context.workItem.path, 'docs/work/mall-ui.md');
  assert.deepEqual(
    context.dependencies.map((dependency) => dependency.workItem?.id),
    ['work-assets'],
  );
  assert.deepEqual(
    context.decisions.map((decision) => decision.id),
    ['decision-mall-ui'],
  );
  assert.equal(Object.hasOwn(context.workItem, 'body'), false);
});

test('validate reports malformed, duplicate, and dangling Markdown without retaining stale work state', (t) => {
  const root = initializedProject(t);

  run(root, [
    'work', 'create', 'Valid before corruption',
    '--id', 'work-corrupted',
    '--slug', 'corrupted',
  ]);
  run(root, [
    'decision', 'create', 'Decision tied to corrupted work',
    '--id', 'decision-corrupted',
    '--slug', 'corrupted-decision',
    '--work-item', 'work-corrupted',
  ]);

  // This file was previously indexed as a valid work item. A subsequent sync must
  // remove that structured row and retain only its parse error.
  writeFileSync(workPath(root, 'corrupted'), '# Broken frontmatter\n', 'utf8');
  writeFileSync(
    workPath(root, 'dangling'),
    validWorkMarkdown({ id: 'work-duplicated', title: 'Dangling dependency', dependsOn: ['work-missing'] }),
    'utf8',
  );
  writeFileSync(
    workPath(root, 'duplicate'),
    validWorkMarkdown({ id: 'work-duplicated', title: 'Duplicate identifier' }),
    'utf8',
  );

  const validation = runJson(root, ['validate', '--json'], 1);
  assert.equal(validation.valid, false);
  const codes = new Set(validation.errors.map((error) => error.code));
  assert.ok(codes.has('parse_error'));
  assert.ok(codes.has('duplicate_work_item_id'));
  assert.ok(codes.has('broken_link'));
  assert.ok(codes.has('invalid_decision_work_item'));

  const status = runJson(root, ['status', '--json']);
  assert.equal(status.workItems.some((item) => item.id === 'work-corrupted'), false);
  assert.equal(status.parseErrors.length, 1);
  assert.equal(status.parseErrors[0].path, 'docs/work/corrupted.md');
});

test('rebuild restores a deleted local index and render-now preserves manual NOW notes', (t) => {
  const root = initializedProject(t);
  run(root, [
    'work', 'create', 'Ship weekend event',
    '--id', 'work-weekend-event',
    '--slug', 'weekend-event',
    '--type', 'activity',
  ]);
  run(root, [
    'decision', 'create', 'Approve weekend rewards',
    '--id', 'decision-weekend-rewards',
    '--slug', 'weekend-rewards',
    '--work-item', 'work-weekend-event',
  ]);

  const nowPath = join(root, 'docs', 'NOW.md');
  const manualNote = 'Keep this hand-written handoff note.';
  writeFileSync(nowPath, `${readFileSync(nowPath, 'utf8')}\n## Manual notes\n\n${manualNote}\n`, 'utf8');

  const databasePath = join(root, '.workflow', 'index.sqlite');
  assert.equal(existsSync(databasePath), true);
  rmSync(databasePath, { force: true });
  rmSync(`${databasePath}-wal`, { force: true });
  rmSync(`${databasePath}-shm`, { force: true });

  run(root, ['rebuild', '--render-now']);
  assert.equal(existsSync(databasePath), true);
  const rebuiltStatus = runJson(root, ['status', '--json']);
  assert.deepEqual(
    rebuiltStatus.workItems.map((item) => item.id),
    ['work-weekend-event'],
  );
  assert.deepEqual(
    rebuiltStatus.decisions.map((decision) => decision.id),
    ['decision-weekend-rewards'],
  );

  const now = readFileSync(nowPath, 'utf8');
  assert.match(now, new RegExp(manualNote));
  assert.equal((now.match(/<!-- workflow-os:auto:start -->/g) ?? []).length, 1);
  assert.equal((now.match(/<!-- workflow-os:auto:end -->/g) ?? []).length, 1);
  assert.match(now, /Ship weekend event/);
});

test('a fresh index lock causes an actionable busy failure instead of concurrent indexing', (t) => {
  const root = initializedProject(t);
  const lockPath = join(root, '.workflow', 'index.lock');
  mkdirSync(dirname(lockPath), { recursive: true });
  writeFileSync(lockPath, '{"pid":12345}\n', 'utf8');

  const result = run(root, ['sync'], 1);
  assert.match(`${result.stdout}\n${result.stderr}`, /索引繁忙/);
});

function writeStaleLock(root) {
  const lockPath = join(root, '.workflow', 'index.lock');
  mkdirSync(dirname(lockPath), { recursive: true });
  writeFileSync(lockPath, '{"pid":12345,"createdAt":"2020-01-01T00:00:00.000Z"}\n', 'utf8');
  const stale = new Date(Date.now() - 60 * 60 * 1000);
  utimesSync(lockPath, stale, stale);
  return lockPath;
}

test('a lock left behind by a crashed process is reclaimed', (t) => {
  const root = initializedProject(t);
  const lockPath = writeStaleLock(root);

  run(root, ['sync']);
  assert.equal(existsSync(lockPath), false, 'the reclaimed lock must be released again');
});

test('racing writers over a stale lock leave no debris and never both proceed', async (t) => {
  const root = initializedProject(t);
  run(root, ['work', 'create', 'Ship weekend event', '--slug', 'weekend-event']);
  writeStaleLock(root);

  const results = await Promise.all(Array.from({ length: 3 }, () => new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [cli, 'sync'], { cwd: root });
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stderr }));
  })));

  assert.ok(results.some((result) => result.code === 0), 'at least one writer must reclaim the stale lock');
  for (const result of results) {
    if (result.code !== 0) assert.match(result.stderr, /索引繁忙/, `unexpected failure:\n${result.stderr}`);
  }

  const leftovers = readdirSync(join(root, '.workflow')).filter((name) => name.includes('.stale-'));
  assert.deepEqual(leftovers, [], 'lock reclamation must not leave temporary files behind');
  assert.equal(existsSync(join(root, '.workflow', 'index.lock')), false);
  assert.equal(runJson(root, ['validate', '--json']).valid, true);
});

test('read-only queries succeed while another process holds the index lock', (t) => {
  const root = initializedProject(t);
  run(root, ['work', 'create', 'Ship weekend event', '--slug', 'weekend-event']);
  const workId = runJson(root, ['status', '--json']).workItems[0].id;

  const lockPath = join(root, '.workflow', 'index.lock');
  mkdirSync(dirname(lockPath), { recursive: true });
  writeFileSync(lockPath, '{"pid":12345}\n', 'utf8');

  assert.equal(runJson(root, ['status', '--json']).totals.workItems, 1);
  assert.equal(runJson(root, ['context', workId, '--json']).workItem.id, workId);
  assert.equal(runJson(root, ['validate', '--json']).valid, true);
  assert.ok(existsSync(lockPath), 'a reader must not remove the writer lock');
});

test('concurrent read-only queries never report the index as busy', async (t) => {
  const root = initializedProject(t);
  run(root, ['work', 'create', 'Ship weekend event', '--slug', 'weekend-event']);

  const results = await Promise.all(Array.from({ length: 4 }, () => new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [cli, 'status', '--json'], { cwd: root });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  })));

  for (const result of results) {
    assert.doesNotMatch(result.stderr, /索引繁忙/);
    assert.equal(result.code, 0, `status failed:\n${result.stderr}`);
    assert.equal(JSON.parse(result.stdout).totals.workItems, 1);
  }
});

test('options may precede positionals, and a malformed option never parses silently', (t) => {
  const root = initializedProject(t);
  run(root, ['work', 'create', 'Ship weekend event', '--slug', 'weekend-event']);
  const workId = runJson(root, ['status', '--json']).workItems[0].id;

  // `--json` must not swallow the work id that follows it.
  assert.equal(runJson(root, ['context', '--json', workId]).workItem.id, workId);

  // A string option must not swallow the next flag as its value.
  const ambiguous = run(root, ['guard', workId, '--outcome', '--error', 'boom'], 1);
  assert.match(ambiguous.stderr, /参数解析失败/);

  // A misspelled option must fail loudly rather than be ignored.
  const unknown = run(root, ['status', '--jsonn'], 1);
  assert.match(unknown.stderr, /参数解析失败/);

  // A value that genuinely starts with a dash still has an escape hatch.
  run(root, ['guard', workId, '--outcome', 'no-progress', '--error=--weird-signature']);
});

test('--no-sync reads the existing index without touching the lock', (t) => {
  const root = initializedProject(t);
  run(root, ['work', 'create', 'Ship weekend event', '--slug', 'weekend-event']);

  // A Markdown edit that has not been synced must stay invisible to a pure read.
  const file = workPath(root, 'weekend-event');
  writeFileSync(file, readFileSync(file, 'utf8').replace('status: planned', 'status: in_progress'), 'utf8');

  const stale = runJson(root, ['status', '--json', '--no-sync']);
  assert.equal(stale.workItems[0].status, 'planned');

  const fresh = runJson(root, ['status', '--json']);
  assert.equal(fresh.workItems[0].status, 'in_progress');
});
