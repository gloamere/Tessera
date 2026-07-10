import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const cli = join(packageRoot, 'bin', 'workflow-os.mjs');

function makeProject(t) {
  const root = mkdtempSync(join(tmpdir(), 'workflow-os-research-'));
  t.after(() => rmSync(root, { recursive: true, force: true, maxRetries: 3 }));
  return root;
}

function run(root, args, expectedStatus = 0) {
  const result = spawnSync(process.execPath, [cli, ...args], { cwd: root, encoding: 'utf8' });
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

function researchPath(root, slug) {
  return join(root, 'docs', 'research', `${slug}.md`);
}

test('init --codex installs research agent profiles and research routing guidance', (t) => {
  const root = initializedProject(t, ['--codex']);

  for (const agent of ['research-scout', 'research-analyst', 'research-auditor']) {
    const path = join(root, '.codex', 'agents', `${agent}.toml`);
    assert.equal(existsSync(path), true, `${agent} profile should be installed`);
    assert.match(readFileSync(path, 'utf8'), new RegExp(`name = "${agent}"`));
  }
  const guidance = readFileSync(join(root, 'AGENTS.md'), 'utf8');
  assert.match(guidance, /workflow-os research create/);
  assert.match(guidance, /Evidence Cards/);
  assert.match(readFileSync(join(root, '.workflow', 'agent-budget.yaml'), 'utf8'), /deep:/);
});

test('quick, standard, and deep research create focused context and dispatch plans', (t) => {
  const root = initializedProject(t, ['--codex']);
  run(root, ['work', 'create', 'Improve game market', '--id', 'work-market', '--slug', 'market']);
  run(root, [
    'research', 'create', 'Which market layout works best?',
    '--mode', 'quick',
    '--scope', 'local project only',
    '--recency', 'current release',
    '--id', 'research-quick',
    '--slug', 'quick-layout',
  ]);
  run(root, [
    'research', 'create', 'Compare market UI approaches',
    '--mode', 'standard',
    '--work-item', 'work-market',
    '--id', 'research-standard',
    '--slug', 'standard-layout',
  ]);
  run(root, [
    'research', 'create', 'Audit the game economy changes',
    '--mode', 'deep',
    '--id', 'research-deep',
    '--slug', 'deep-economy',
  ]);

  const status = runJson(root, ['status', '--json']);
  const researchById = new Map(status.researchItems.map((item) => [item.id, item]));
  assert.deepEqual(
    {
      mode: researchById.get('research-quick').mode,
      status: researchById.get('research-quick').status,
      confirmation: researchById.get('research-quick').confirmation,
    },
    { mode: 'quick', status: 'ready', confirmation: 'not_required' },
  );
  assert.deepEqual(
    {
      mode: researchById.get('research-standard').mode,
      workItemId: researchById.get('research-standard').workItemId,
      confirmation: researchById.get('research-standard').confirmation,
    },
    { mode: 'standard', workItemId: 'work-market', confirmation: 'not_required' },
  );
  assert.deepEqual(
    {
      mode: researchById.get('research-deep').mode,
      status: researchById.get('research-deep').status,
      confirmation: researchById.get('research-deep').confirmation,
    },
    { mode: 'deep', status: 'awaiting_confirmation', confirmation: 'pending' },
  );

  const researchContext = runJson(root, ['research', 'context', 'research-standard', '--json']);
  assert.equal(researchContext.error, null);
  assert.equal(researchContext.researchItem.path, 'docs/research/standard-layout.md');
  assert.equal(researchContext.researchItem.question, 'Compare market UI approaches');
  assert.equal(Object.hasOwn(researchContext.researchItem, 'body'), false);
  assert.deepEqual(
    researchContext.workItems.map((entry) => entry.workItem?.id),
    ['work-market'],
  );
  const workContext = runJson(root, ['context', 'work-market', '--json']);
  assert.deepEqual(workContext.researchItems.map((item) => item.id), ['research-standard']);

  const quickPlan = runJson(root, ['research', 'plan', 'research-quick', '--json']);
  assert.equal(quickPlan.executable, true);
  assert.deepEqual(quickPlan.tasks.map((task) => task.role), ['research-scout']);
  const standardPlan = runJson(root, ['research', 'plan', 'research-standard', '--json']);
  assert.equal(standardPlan.executable, true);
  assert.deepEqual(
    standardPlan.tasks.map((task) => task.role),
    ['research-scout', 'research-scout', 'research-analyst'],
  );

  const deepPlanBeforeApproval = runJson(root, ['research', 'plan', 'research-deep', '--json']);
  assert.equal(deepPlanBeforeApproval.executable, false);
  assert.equal(deepPlanBeforeApproval.dispatch_status, 'awaiting_confirmation');
  assert.ok(deepPlanBeforeApproval.tasks.some((task) => task.role === 'research-auditor'));
  assert.match(readFileSync(researchPath(root, 'deep-economy'), 'utf8'), /research-auditor/);

  run(root, ['research', 'approve', 'research-deep']);
  const approvedContext = runJson(root, ['research', 'context', 'research-deep', '--json']);
  assert.deepEqual(
    {
      status: approvedContext.researchItem.status,
      confirmation: approvedContext.researchItem.confirmation,
    },
    { status: 'ready', confirmation: 'approved' },
  );
  const deepPlanAfterApproval = runJson(root, ['research', 'plan', 'research-deep', '--json']);
  assert.equal(deepPlanAfterApproval.executable, true);
  assert.equal(deepPlanAfterApproval.dispatch_status, 'ready');
});

test('research validate accepts a completed dossier with a complete, referenced Evidence Card', (t) => {
  const root = initializedProject(t);
  run(root, [
    'research', 'create', 'Is the UI framework actively maintained?',
    '--mode', 'standard',
    '--id', 'research-evidence',
    '--slug', 'evidence',
  ]);

  const dossierPath = researchPath(root, 'evidence');
  const completedDossier = readFileSync(dossierPath, 'utf8')
    .replace('status: ready', 'status: completed')
    .replace(
      '## Evidence Cards',
      `## Evidence Cards

### Evidence: official-docs
- Claim: The framework publishes current official documentation.
- URL: https://example.com/framework/docs
- Source type: official documentation
- Retrieved: 2026-07-10
- Relevance: Establishes that an authoritative source is available.
- Caveat: Documentation alone does not prove production adoption.`,
    )
    .replaceAll('[[evidence-evidence-1]]', '[[evidence-official-docs]]');
  writeFileSync(dossierPath, completedDossier, 'utf8');

  const validation = runJson(root, ['research', 'validate', 'research-evidence', '--json']);
  assert.equal(validation.valid, true);
  assert.deepEqual(validation.errors, []);
  const context = runJson(root, ['research', 'context', 'research-evidence', '--json']);
  assert.equal(context.researchItem.status, 'completed');
});
