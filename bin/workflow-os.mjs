#!/usr/bin/env node
import {
  cp,
  mkdir,
  readdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from 'node:fs/promises';
import { constants } from 'node:fs';
import { access } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import {
  openIndex,
  openIndexForRead,
  queryContext,
  queryDocumentHashes,
  queryResearchContext,
  queryStatus,
  queryValidation,
  rebuildSchema,
  removeMissingDocuments,
  replaceDocumentIndex,
} from '../src/index-db.mjs';
import { metadataVocabulary, parseMarkdownDocument } from '../src/markdown.mjs';
import {
  applyUpgradePlan,
  adapterStatus,
  buildUpgradePlan,
  ensureManifest,
  installAdapter,
  recordAdapterDetection,
  installCodexGuidance,
  recordGuard,
  recordAdapterCheck,
} from '../src/maintenance.mjs';
import {
  createRecord,
  pathExists,
  readProjectMarkdown,
  withIndexLock,
  withOptionalIndexLock,
  writeNowSummary,
} from '../src/project.mjs';
import { approveResearch, buildDispatchPlan, createResearch, saveDispatchPlan } from '../src/research.mjs';
import { ingestWithMarkItDown } from '../src/ingest.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const templates = join(here, '..', 'templates');
const AUTO_RENDER_FLAG = '--render-now';

function usage() {
  console.log(`workflow-os — Markdown-first local workflow index

Usage:
  workflow-os init [--codex] [--obsidian] [--dry-run]
  workflow-os work create <title> [--type <type>] [--priority <priority>] [--approval-state <state>] [--id <id>] [--slug <slug>]
  workflow-os decision create <title> --work-item <work-id> [--id <id>] [--slug <slug>]
  workflow-os research create <question> [--mode quick|standard|deep] [--scope <scope>] [--recency <requirement>] [--work-item <work-id>] [--id <id>] [--slug <slug>]
  workflow-os research plan <research-id> [--json]
  workflow-os research context <research-id> [--json]
  workflow-os research validate [research-id] [--json]
  workflow-os research approve <research-id>
  workflow-os sync [${AUTO_RENDER_FLAG}]
  workflow-os status [--json] [--no-sync]
  workflow-os context <work-id> [--json] [--no-sync]
  workflow-os validate [--json] [--no-sync]
  workflow-os rebuild [${AUTO_RENDER_FLAG}]
  workflow-os upgrade [--check|--plan] [--apply] [--json]
  workflow-os adapter status [<adapter-id>] [--json]
  workflow-os adapter doctor [--json]
  workflow-os adapter check <adapter-id> --version <version> [--release-url <https-url>] [--json]
  workflow-os adapter install <adapter-id> --authorized [--json]
  workflow-os ingest <local-file> [--title <title>] [--research <research-id>] [--work-item <work-id>] [--id <id>] [--slug <slug>]
  workflow-os guard <work-id> --outcome progress|no-progress [--error <signature>] [--json]
`);
}

function requireNode24() {
  const major = Number.parseInt(process.versions.node.split('.')[0], 10);
  if (major < 24) throw new Error('workflow-os 需要 Node.js 24 或更高版本（使用 node:sqlite）。');
}

async function exists(path) {
  try {
    await access(path, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

const BOOLEAN_OPTIONS = [
  'apply',
  'authorized',
  'check',
  'codex',
  'dry-run',
  'help',
  'json',
  'no-sync',
  'obsidian',
  'plan',
  'render-now',
];
const STRING_OPTIONS = [
  'approval-state',
  'error',
  'id',
  'mode',
  'outcome',
  'priority',
  'recency',
  'release-url',
  'research',
  'scope',
  'slug',
  'title',
  'type',
  'version',
  'work-item',
];
const OPTION_CONFIG = Object.fromEntries([
  ...BOOLEAN_OPTIONS.map((name) => [name, { type: 'boolean' }]),
  ...STRING_OPTIONS.map((name) => [name, { type: 'string' }]),
]);

/**
 * Parse one command's arguments.  Strict mode rejects unknown options, and
 * `parseArgs` refuses a value-taking option whose value looks like another
 * flag, so `--outcome --error x` fails instead of quietly setting
 * `outcome="--error"`.  A value that really starts with a dash uses `--error=-5`.
 */
function parseCli(tokens) {
  try {
    const { positionals, values } = parseArgs({
      args: tokens,
      options: OPTION_CONFIG,
      allowPositionals: true,
      strict: true,
    });
    return { positionals, options: new Map(Object.entries(values)) };
  } catch (error) {
    throw new Error(`参数解析失败：${error.message}`);
  }
}

function optionValue(options, name) {
  const value = options.get(name);
  return value === true || value === undefined ? null : value;
}

function enumOption(options, name, fallback, values) {
  const value = optionValue(options, name) ?? fallback;
  if (!values.includes(value)) {
    throw new Error(`--${name} 必须是以下值之一：${values.join(', ')}。`);
  }
  return value;
}

async function copyMissing(source, target, dryRun, changes) {
  const sourceStat = await stat(source);
  if (sourceStat.isDirectory()) {
    if (!(await exists(target))) {
      changes.push(`create  ${target}`);
      if (!dryRun) await mkdir(target, { recursive: true });
    }
    for (const entry of await readdir(source, { withFileTypes: true })) {
      await copyMissing(join(source, entry.name), join(target, entry.name), dryRun, changes);
    }
    return;
  }

  if (await exists(target)) {
    changes.push(`skip    ${target}`);
    return;
  }
  changes.push(`create  ${target}`);
  if (!dryRun) {
    await mkdir(dirname(target), { recursive: true });
    await cp(source, target, { errorOnExist: false });
  }
}

async function packageVersion() {
  return JSON.parse(await readFile(join(here, '..', 'package.json'), 'utf8')).version;
}

async function install(root, options, version) {
  const dryRun = options.has('dry-run');
  const entries = [
    ['workflow', '.workflow'],
    ['workflow-gitignore.template', '.workflow/.gitignore'],
    ['docs', 'docs'],
  ];
  if (options.has('obsidian')) entries.push(['obsidian-workflow', '.obsidian-workflow']);
  if (options.has('codex')) entries.push(['codex-agents', '.codex/agents']);

  const changes = [];
  for (const [source, target] of entries) {
    await copyMissing(join(templates, source), join(root, target), dryRun, changes);
  }
  await ensureIndexIgnoreRules(root, dryRun, changes);
  const codex = options.has('codex')
    ? await installCodexGuidance(root, join(templates, 'codex'), dryRun, changes)
    : { enabled: false, sourceHash: null };
  await ensureManifest(root, templates, version, codex, dryRun, changes);
  const adapterDetection = dryRun ? null : await recordAdapterDetection(root);
  return { dryRun, changes, adapterDetection };
}

async function ensureIndexIgnoreRules(root, dryRun, changes) {
  const ignorePath = join(root, '.workflow', '.gitignore');
  const requiredRules = ['index.sqlite*', 'index.lock', 'runtime/'];
  if (dryRun && !(await exists(ignorePath))) return;
  const current = (await exists(ignorePath)) ? await readFile(ignorePath, 'utf8') : '';
  const existingRules = new Set(current.split(/\r?\n/).map((line) => line.trim()));
  const missingRules = requiredRules.filter((rule) => !existingRules.has(rule));
  if (missingRules.length === 0) return;
  changes.push(`append  ${ignorePath} (${missingRules.join(', ')})`);
  if (!dryRun) {
    await mkdir(dirname(ignorePath), { recursive: true });
    const separator = current === '' || current.endsWith('\n') ? '' : '\n';
    await writeFile(ignorePath, `${current}${separator}${missingRules.join('\n')}\n`, 'utf8');
  }
}

function indexPath(root) {
  return join(root, '.workflow', 'index.sqlite');
}

async function requireInstalled(root) {
  if (!(await pathExists(join(root, '.workflow')))) {
    throw new Error('未发现 .workflow/。请先在项目根目录运行 workflow-os init。');
  }
}

function parseProjectDocuments(markdownDocuments) {
  const indexedAt = new Date().toISOString();
  return markdownDocuments.map((document) => parseMarkdownDocument(document.path, document.content, indexedAt));
}

function indexParsedDocuments(db, documents, { force = false } = {}) {
  const knownHashes = new Map(queryDocumentHashes(db).map((document) => [document.path, document.hash]));
  let indexedCount = 0;
  for (const document of documents) {
    if (force || knownHashes.get(document.path) !== document.hash) {
      replaceDocumentIndex(db, document);
      indexedCount += 1;
    }
  }
  const removed = removeMissingDocuments(db, documents.map((document) => document.path));
  return { indexedCount, removed };
}

async function syncProject(root, { renderNow = false, optional = false } = {}) {
  await requireInstalled(root);
  const refresh = async () => {
    const documents = parseProjectDocuments(await readProjectMarkdown(root));
    const db = openIndex(indexPath(root));
    try {
      const sync = indexParsedDocuments(db, documents);
      const status = queryStatus(db);
      const validation = queryValidation(db);
      if (renderNow) await writeNowSummary(root, status);
      return { ...sync, status, validation };
    } finally {
      db.close();
    }
  };
  if (!optional) return withIndexLock(root, refresh);
  const { ran, value } = await withOptionalIndexLock(root, refresh);
  return ran ? value : null;
}

/**
 * Open the index for a read-only command.
 *
 * The refresh is best effort: when another process already holds the index
 * lock it is skipped, because that process is refreshing the very index this
 * caller is about to read.  A query therefore never fails just because agents
 * run concurrently.  `--no-sync` skips the refresh outright for a pure read.
 */
async function openForQuery(root, { noSync = false } = {}) {
  await requireInstalled(root);
  if (!(await exists(indexPath(root)))) await syncProject(root);
  else if (!noSync) await syncProject(root, { optional: true });
  return openIndexForRead(indexPath(root));
}

async function rebuildProject(root, { renderNow = false } = {}) {
  await requireInstalled(root);
  return withIndexLock(root, async () => {
    const documents = parseProjectDocuments(await readProjectMarkdown(root));
    const target = indexPath(root);
    const temporary = `${target}.rebuild-${process.pid}-${Date.now()}`;
    const backup = `${target}.previous-${process.pid}-${Date.now()}`;
    await rm(temporary, { force: true });
    await rm(`${temporary}-wal`, { force: true });
    await rm(`${temporary}-shm`, { force: true });

    let temporaryDb;
    try {
      temporaryDb = openIndex(temporary);
      rebuildSchema(temporaryDb);
      const sync = indexParsedDocuments(temporaryDb, documents, { force: true });
      temporaryDb.exec('PRAGMA wal_checkpoint(TRUNCATE);');
      temporaryDb.close();
      temporaryDb = null;

      const hadCurrentIndex = await exists(target);
      if (hadCurrentIndex) await rename(target, backup);
      await rm(`${target}-wal`, { force: true });
      await rm(`${target}-shm`, { force: true });
      try {
        await rename(temporary, target);
      } catch (error) {
        if (hadCurrentIndex && !(await exists(target)) && (await exists(backup))) await rename(backup, target);
        throw error;
      }
      await rm(backup, { force: true });

      const db = openIndex(target);
      try {
        const status = queryStatus(db);
        const validation = queryValidation(db);
        if (renderNow) await writeNowSummary(root, status);
        return { ...sync, status, validation };
      } finally {
        db.close();
      }
    } finally {
      if (temporaryDb) temporaryDb.close();
      await rm(temporary, { force: true }).catch(() => undefined);
      await rm(`${temporary}-wal`, { force: true }).catch(() => undefined);
      await rm(`${temporary}-shm`, { force: true }).catch(() => undefined);
    }
  });
}

function printStatus(status) {
  const active = status.workItems.filter((item) => ['planned', 'in_progress', 'blocked', 'waiting_approval'].includes(item.status));
  const pendingDecisions = status.decisions.filter((decision) => decision.status === 'pending');
  const researchAwaitingConfirmation = (status.researchItems ?? []).filter((item) => item.status === 'awaiting_confirmation');
  console.log(`工作包：${status.totals.workItems}；决策：${status.totals.decisions}；调研：${status.totals.researchItems ?? 0}；解析错误：${status.totals.parseErrors}`);
  console.log('\n正在推进：');
  for (const item of active) console.log(`- ${item.title} [${item.id}] — ${item.status}${item.nextStep ? `；下一步：${item.nextStep}` : ''}`);
  if (active.length === 0) console.log('- 暂无。');
  console.log('\n待澄清：');
  for (const item of status.needsClarification) console.log(`- ${item.title} [${item.id}] — ${item.clarificationSummary}`);
  if (status.needsClarification.length === 0) console.log('- 暂无。');
  console.log('\n待拍板：');
  for (const decision of pendingDecisions) console.log(`- ${decision.title} [${decision.id}] → ${decision.workItemId}`);
  if (pendingDecisions.length === 0) console.log('- 暂无。');
  console.log('\n待确认调研：');
  for (const item of researchAwaitingConfirmation) console.log(`- ${item.title} [${item.id}] — deep 计划等待确认`);
  if (researchAwaitingConfirmation.length === 0) console.log('- 暂无。');
  if (status.parseErrors.length > 0) {
    console.log('\n解析错误：');
    for (const error of status.parseErrors) console.log(`- ${error.path}: ${error.parseError}`);
  }
}

function printValidation(validation) {
  if (validation.valid) {
    console.log('校验通过。');
    return;
  }
  console.log(`校验失败：${validation.errors.length} 项问题。`);
  for (const error of validation.errors) {
    const location = error.path ? `${error.path}: ` : '';
    const detail = error.message ?? error.reason ?? error.id ?? '未知问题';
    console.log(`- [${error.code}] ${location}${detail}`);
  }
}

function printContext(context) {
  if (context.error) {
    console.error(context.error.message);
    return;
  }
  const workItem = context.workItem;
  console.log(`# ${workItem.title}`);
  console.log(`工作包：${workItem.id}`);
  console.log(`文件：${workItem.path}`);
  console.log(`状态：${workItem.status}；优先级：${workItem.priority}`);
  if (workItem.nextStep) console.log(`下一步：${workItem.nextStep}`);
  console.log('\n依赖：');
  if (context.dependencies.length === 0) console.log('- 无。');
  for (const dependency of context.dependencies) {
    console.log(`- ${dependency.workItem ? `${dependency.workItem.title} [${dependency.workItem.id}]` : `[缺失] ${dependency.link.targetId}`}`);
  }
  console.log('\n决策：');
  if (context.decisions.length === 0) console.log('- 无。');
  for (const decision of context.decisions) console.log(`- ${decision.title} [${decision.id}] — ${decision.status}`);
}

async function run() {
  requireNode24();
  const [command, ...rest] = process.argv.slice(2);
  const root = process.cwd();
  if (!command || command === '--help' || command === 'help') {
    usage();
    return;
  }
  if (rest.includes('--help')) {
    usage();
    return;
  }

  const { positionals, options } = parseCli(rest);

  if (command === 'init') {
    const result = await install(root, options, await packageVersion());
    console.log(`${result.dryRun ? '预览安装' : '已安装'}：${resolve(root)}`);
    for (const change of result.changes) console.log(change);
    if (result.adapterDetection) {
      for (const [id, status] of Object.entries(result.adapterDetection)) {
        console.log(`adapter ${id}: ${status.availability}${status.availability === 'missing' ? '（如任务需要，Codex 将先请求安装授权）' : ''}`);
      }
    }
    if (result.dryRun) console.log('未修改文件。');
    return;
  }

  if (command === 'work' || command === 'decision') {
    const [subcommand, ...titleWords] = positionals;
    if (subcommand !== 'create') throw new Error(`${command} 仅支持 create。`);
    await requireInstalled(root);
    const title = titleWords.join(' ').trim();
    if (!title) throw new Error('请提供记录标题。');
    const workItemId = optionValue(options, 'work-item');
    if (command === 'decision' && !workItemId) throw new Error('decision create 需要 --work-item <work-id>。');
    const record = command === 'work'
      ? await createRecord(root, 'work', {
        title,
        type: optionValue(options, 'type') ?? 'feature',
        priority: enumOption(options, 'priority', 'medium', metadataVocabulary.priorities),
        approvalState: enumOption(options, 'approval-state', 'not_required', metadataVocabulary.approvalStates),
        id: optionValue(options, 'id'),
        slug: optionValue(options, 'slug'),
      })
      : await createRecord(root, 'decision', {
        title,
        workItemId,
        id: optionValue(options, 'id'),
        slug: optionValue(options, 'slug'),
      });
    await syncProject(root);
    console.log(`已创建 ${record.path} [${record.id}]。`);
    return;
  }

  if (command === 'research') {
    await requireInstalled(root);
    const [subcommand, ...researchArgs] = positionals;
    if (subcommand === 'create') {
      const title = researchArgs.join(' ').trim();
      if (!title) throw new Error('research create 需要研究问题。');
      const record = await createResearch(root, {
        title,
        mode: enumOption(options, 'mode', 'standard', metadataVocabulary.researchModes),
        scope: optionValue(options, 'scope') ?? 'GitHub + public web',
        recency: optionValue(options, 'recency') ?? 'current',
        workItemId: optionValue(options, 'work-item'),
        id: optionValue(options, 'id'),
        slug: optionValue(options, 'slug'),
      });
      await syncProject(root);
      console.log(`已创建 ${record.path} [${record.id}]。`);
      return;
    }
    const researchId = researchArgs[0];
    if (!researchId && subcommand !== 'validate') throw new Error(`research ${subcommand ?? ''} 需要 <research-id>。`);

    // Read first, then release the connection.  `plan` and `approve` rewrite
    // Markdown afterwards and re-sync, which must not nest inside an open handle.
    const db = await openForQuery(root, { noSync: options.has('no-sync') });
    let context;
    try {
      if (subcommand === 'validate') {
        const validation = queryValidation(db);
        if (options.has('json')) console.log(JSON.stringify(validation, null, 2));
        else printValidation(validation);
        if (!validation.valid) process.exitCode = 1;
        return;
      }
      context = queryResearchContext(db, researchId);
    } finally {
      db.close();
    }
    if (context.error) throw new Error(context.error.message);

    if (subcommand === 'context') {
      if (options.has('json')) console.log(JSON.stringify(context, null, 2));
      else console.log(`# ${context.researchItem.title}\n研究：${context.researchItem.id}\n状态：${context.researchItem.status}\n模式：${context.researchItem.mode}\n下一步：${context.researchItem.nextAction ?? '未填写'}\n档案：${context.researchItem.path}`);
      return;
    }
    if (subcommand === 'plan') {
      const plan = buildDispatchPlan(context.researchItem);
      await saveDispatchPlan(root, context.researchItem.path, plan);
      await syncProject(root);
      if (options.has('json')) console.log(JSON.stringify(plan, null, 2));
      else console.log(plan.executable ? 'Dispatch Review 已生成，可由总指挥派遣。' : 'Deep 研究计划已生成，等待负责人确认。');
      return;
    }
    if (subcommand === 'approve') {
      if (context.researchItem.mode !== 'deep') throw new Error('只有 deep 研究需要确认。');
      await approveResearch(root, context.researchItem.path);
      await syncProject(root);
      console.log('已记录负责人确认；现在可运行 research plan。');
      return;
    }
    throw new Error(`research 不支持 ${subcommand}。`);
  }

  if (command === 'sync') {
    const result = await syncProject(root, { renderNow: options.has('render-now') });
    console.log(`同步完成：更新 ${result.indexedCount} 个文件，移除 ${result.removed.removedCount} 个索引记录。`);
    if (!result.validation.valid) console.log(`提示：发现 ${result.validation.errors.length} 项校验问题；运行 workflow-os validate 查看。`);
    return;
  }

  if (command === 'rebuild') {
    const result = await rebuildProject(root, { renderNow: options.has('render-now') });
    console.log(`索引已重建：索引 ${result.indexedCount} 个文件，移除 ${result.removed.removedCount} 个记录。`);
    if (!result.validation.valid) console.log(`提示：发现 ${result.validation.errors.length} 项校验问题；运行 workflow-os validate 查看。`);
    return;
  }

  if (command === 'status') {
    const db = await openForQuery(root, { noSync: options.has('no-sync') });
    try {
      const status = queryStatus(db);
      if (options.has('json')) console.log(JSON.stringify(status, null, 2));
      else printStatus(status);
    } finally {
      db.close();
    }
    return;
  }

  if (command === 'context') {
    const workItemId = positionals[0];
    if (!workItemId) throw new Error('context 需要 <work-id>。');
    const db = await openForQuery(root, { noSync: options.has('no-sync') });
    try {
      const context = queryContext(db, workItemId);
      if (options.has('json')) console.log(JSON.stringify(context, null, 2));
      else printContext(context);
      if (context.error) process.exitCode = 1;
    } finally {
      db.close();
    }
    return;
  }

  if (command === 'validate') {
    const db = await openForQuery(root, { noSync: options.has('no-sync') });
    try {
      const validation = queryValidation(db);
      if (options.has('json')) console.log(JSON.stringify(validation, null, 2));
      else printValidation(validation);
      if (!validation.valid) process.exitCode = 1;
    } finally {
      db.close();
    }
    return;
  }

  if (command === 'upgrade') {
    await requireInstalled(root);
    const plan = await buildUpgradePlan(root, templates);
    if (options.has('apply')) {
      const applied = await applyUpgradePlan(root, templates, await packageVersion(), plan);
      if (options.has('json')) console.log(JSON.stringify({ applied, plan: plan.actions }, null, 2));
      else console.log(applied.length > 0 ? `已应用 ${applied.length} 项安全升级。` : '没有可安全应用的升级。');
    } else if (options.has('json')) {
      console.log(JSON.stringify(plan, null, 2));
    } else {
      const notable = plan.actions.filter((action) => action.kind !== 'current');
      if (notable.length === 0) console.log('工作流模板已是当前版本。');
      for (const action of notable) console.log(`${action.kind.padEnd(20)} ${action.target}`);
      if (notable.some((action) => action.kind === 'local_override')) console.log('本地覆盖不会被自动修改。');
      if (!options.has('plan')) console.log('运行 workflow-os upgrade --apply 应用安全更新。');
    }
    return;
  }

  if (command === 'adapter') {
    await requireInstalled(root);
    const [subcommand, adapterId] = positionals;
    if (subcommand === 'status') {
      const result = await adapterStatus(root, adapterId ?? null);
      if (options.has('json')) console.log(JSON.stringify(result, null, 2));
      else for (const adapter of result.adapters) {
        const state = adapter.state?.available_version ? `；发现版本：${adapter.state.available_version}（等待确认）` : '';
        console.log(`${adapter.id}：${adapter.update_policy}${state}`);
      }
      return;
    }
    if (subcommand === 'doctor') {
      const result = await recordAdapterDetection(root);
      if (options.has('json')) console.log(JSON.stringify(result, null, 2));
      else for (const [id, status] of Object.entries(result)) console.log(`${id}：${status.availability}${status.reason ? `；${status.reason}` : ''}`);
      return;
    }
    if (subcommand === 'check') {
      if (!adapterId) throw new Error('adapter check 需要 <adapter-id>。');
      const result = await recordAdapterCheck(root, adapterId, {
        version: optionValue(options, 'version'),
        releaseUrl: optionValue(options, 'release-url'),
      });
      if (options.has('json')) console.log(JSON.stringify(result, null, 2));
      else console.log(`已记录 ${result.id} 的候选版本 ${result.state.available_version}；等待你的确认。`);
      return;
    }
    if (subcommand === 'install') {
      if (!adapterId) throw new Error('adapter install 需要 <adapter-id>。');
      const result = await installAdapter(root, adapterId, {
        authorized: options.has('authorized'),
        log: options.has('json') ? () => {} : console.log,
      });
      if (options.has('json')) console.log(JSON.stringify(result, null, 2));
      else if (result.manual) console.log(`${adapterId} 需手动安装：${result.instruction}`);
      else console.log(result.installed ? `${adapterId} 已安装并通过检测。` : `${adapterId} 安装命令已完成，但尚未通过检测。`);
      return;
    }
    throw new Error(`adapter 不支持 ${subcommand ?? ''}。`);
  }

  if (command === 'ingest') {
    await requireInstalled(root);
    const sourcePath = positionals[0];
    if (!sourcePath) throw new Error('ingest 需要 <local-file>。');
    const result = await ingestWithMarkItDown(root, sourcePath, {
      title: optionValue(options, 'title'),
      researchId: optionValue(options, 'research'),
      workItemId: optionValue(options, 'work-item'),
      id: optionValue(options, 'id'),
      slug: optionValue(options, 'slug'),
    });
    await syncProject(root);
    console.log(`已导入 ${result.path} [${result.id}]。`);
    return;
  }

  if (command === 'guard') {
    await requireInstalled(root);
    const workItemId = positionals[0];
    const outcome = optionValue(options, 'outcome');
    if (!workItemId || !outcome) throw new Error('guard 需要 <work-id> 与 --outcome progress|no-progress。');
    const result = await recordGuard(root, workItemId, outcome, optionValue(options, 'error'));
    if (options.has('json')) console.log(JSON.stringify(result, null, 2));
    else console.log(`guard: ${result.state.decision}${result.state.reasons.length ? `（${result.state.reasons.join('；')}）` : ''}`);
    if (result.state.decision === 'stop') process.exitCode = 2;
    return;
  }

  throw new Error(`未知命令：${command}`);
}

run().catch((error) => {
  console.error(`workflow-os: ${error.message}`);
  process.exitCode = 1;
});
