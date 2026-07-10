import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';
import { homedir } from 'node:os';
import { parse, stringify } from 'yaml';
import { pathExists } from './project.mjs';

const CODEX_START = '<!-- workflow-os:start -->';
const CODEX_END = '<!-- workflow-os:end -->';
const DEFAULT_BUDGET = {
  max_parallel_agents: 3,
  max_agent_rounds: 3,
  repeated_error_limit: 2,
  no_progress_limit: 2,
  default_reasoning: 'medium',
};
const DEFAULT_ADAPTERS = {
  'taste-skill': {
    source: 'Leonxlnx/taste-skill',
    update_policy: 'check-and-confirm',
  },
  superpowers: {
    source: 'obra/superpowers',
    install_name: 'Superpowers',
    update_policy: 'check-release-and-confirm',
    enabled_by_default: false,
  },
  markitdown: {
    source: 'microsoft/markitdown',
    install_name: 'markitdown',
    update_policy: 'check-release-and-confirm',
    enabled_by_default: false,
  },
};

function hash(content) {
  return createHash('sha256').update(content).digest('hex');
}

async function text(path) {
  return readFile(path, 'utf8');
}

async function files(directory, root = directory, result = []) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const absolute = join(directory, entry.name);
    if (entry.isDirectory()) await files(absolute, root, result);
    else if (entry.isFile()) result.push({ absolute, relative: relative(root, absolute).replaceAll('\\', '/') });
  }
  return result;
}

export async function managedTemplateEntries(templatesRoot) {
  const entries = [];
  for (const [sourceFolder, targetFolder] of [['workflow', '.workflow'], ['docs', 'docs']]) {
    const sourceRoot = join(templatesRoot, sourceFolder);
    for (const file of await files(sourceRoot)) {
      entries.push({
        sourceId: `${sourceFolder}/${file.relative}`,
        sourcePath: file.absolute,
        target: `${targetFolder}/${file.relative}`,
      });
    }
  }
  entries.push({
    sourceId: 'workflow-gitignore.template',
    sourcePath: join(templatesRoot, 'workflow-gitignore.template'),
    target: '.workflow/.gitignore',
  });
  return entries;
}

function codexBlock(content) {
  return `${CODEX_START}\n${content.trim()}\n${CODEX_END}\n`;
}

export async function installCodexGuidance(root, templatePath, dryRun, changes) {
  const target = join(root, 'AGENTS.md');
  const block = codexBlock(await text(templatePath));
  if (!(await pathExists(target))) {
    changes.push(`create  ${target} (workflow-os managed block)`);
    if (!dryRun) await writeFile(target, block, 'utf8');
    return { enabled: true, sourceHash: hash(block) };
  }

  const current = await text(target);
  const start = current.indexOf(CODEX_START);
  const end = current.indexOf(CODEX_END);
  if ((start >= 0) !== (end >= 0) || (start >= 0 && end < start)) {
    changes.push(`conflict ${target} (workflow-os markers are malformed)`);
    return { enabled: false, sourceHash: hash(block), conflict: true };
  }
  if (start >= 0) {
    const next = `${current.slice(0, start)}${block}${current.slice(end + CODEX_END.length)}`;
    if (next !== current) changes.push(`update  ${target} (workflow-os managed block)`);
    if (!dryRun && next !== current) await writeFile(target, next, 'utf8');
    return { enabled: true, sourceHash: hash(block) };
  }

  changes.push(`append  ${target} (workflow-os managed block)`);
  if (!dryRun) await writeFile(target, `${current}${current.endsWith('\n') ? '\n' : '\n\n'}${block}`, 'utf8');
  return { enabled: true, sourceHash: hash(block) };
}

export async function readManifest(root) {
  const path = join(root, '.workflow', 'manifest.yaml');
  if (!(await pathExists(path))) return null;
  const value = parse(await text(path));
  if (!value || typeof value !== 'object') throw new Error('`.workflow/manifest.yaml` 无法解析为对象。');
  return value;
}

async function writeManifest(root, manifest) {
  const path = join(root, '.workflow', 'manifest.yaml');
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, stringify(manifest), 'utf8');
}

export async function ensureManifest(root, templatesRoot, version, codex, dryRun, changes) {
  const existing = await readManifest(root);
  if (existing) {
    const missingAdapters = Object.entries(DEFAULT_ADAPTERS)
      .filter(([id]) => !existing.adapters?.[id]);
    if (missingAdapters.length > 0) {
      existing.adapters = { ...(existing.adapters ?? {}), ...Object.fromEntries(missingAdapters) };
      existing.updated_at = new Date().toISOString();
      changes.push(`update  ${join(root, '.workflow', 'manifest.yaml')} (register adapters: ${missingAdapters.map(([id]) => id).join(', ')})`);
      if (!dryRun) await writeManifest(root, existing);
    }
    if (codex.enabled && !existing.codex?.enabled) {
      existing.codex = { enabled: true, source_hash: codex.sourceHash };
      existing.updated_at = new Date().toISOString();
      changes.push(`update  ${join(root, '.workflow', 'manifest.yaml')} (enable Codex guidance)`);
      if (!dryRun) await writeManifest(root, existing);
    }
    return existing;
  }
  const managedFiles = {};
  for (const entry of await managedTemplateEntries(templatesRoot)) {
    const sourceHash = hash(await text(entry.sourcePath));
    const targetPath = join(root, entry.target);
    managedFiles[entry.sourceId] = {
      target: entry.target,
      source_hash: sourceHash,
      installed_hash: (await pathExists(targetPath)) ? hash(await text(targetPath)) : null,
    };
  }
  const manifest = {
    schema: 1,
    workflow_os_version: version,
    installed_at: new Date().toISOString(),
    managed_files: managedFiles,
    codex: {
      enabled: codex.enabled,
      source_hash: codex.sourceHash,
    },
    adapters: DEFAULT_ADAPTERS,
  };
  changes.push(`create  ${join(root, '.workflow', 'manifest.yaml')}`);
  if (!dryRun) await writeManifest(root, manifest);
  return manifest;
}

function adapterStatePath(root) {
  return join(root, '.workflow', 'runtime', 'adapters.json');
}

export async function adapterStatus(root, adapterId = null) {
  const manifest = await readManifest(root);
  if (!manifest) throw new Error('未发现 manifest.yaml；请先运行 workflow-os init。');
  const statePath = adapterStatePath(root);
  const state = (await pathExists(statePath)) ? JSON.parse(await text(statePath)) : {};
  const adapters = Object.entries(manifest.adapters ?? {})
    .filter(([id]) => adapterId === null || id === adapterId)
    .map(([id, adapter]) => ({ id, ...adapter, state: state[id] ?? null }));
  if (adapterId !== null && adapters.length === 0) throw new Error(`未知适配器：${adapterId}`);
  return { adapters };
}

export async function adapterDefinitions(root) {
  const registryPath = join(root, '.workflow', 'adapters.yaml');
  if (!(await pathExists(registryPath))) return [];
  const registry = parse(await text(registryPath));
  if (!registry || !Array.isArray(registry.adapters)) throw new Error('`.workflow/adapters.yaml` 必须包含 adapters 数组。');
  return registry.adapters.filter((adapter) => adapter && typeof adapter.id === 'string');
}

function commandExists(command) {
  const locator = process.platform === 'win32' ? 'where.exe' : 'which';
  const result = spawnSync(locator, [command], { stdio: 'ignore', windowsHide: true });
  return result.status === 0;
}

function pythonModuleExists(module) {
  const result = spawnSync('python', ['-c', `import importlib.util, sys; sys.exit(0 if importlib.util.find_spec(${JSON.stringify(module)}) else 1)`], { stdio: 'ignore', windowsHide: true });
  return result.status === 0;
}

async function anyPathExists(paths) {
  for (const path of paths) if (await pathExists(path)) return path;
  return null;
}

export async function detectAdapters(root) {
  const codexHome = process.env.CODEX_HOME ?? join(homedir(), '.codex');
  const definitions = await adapterDefinitions(root);
  const results = {};
  for (const adapter of definitions) {
    const detectedAt = new Date().toISOString();
    if (typeof adapter.detect?.command === 'string') {
      const commandAvailable = commandExists(adapter.detect.command);
      const moduleAvailable = typeof adapter.detect?.python_module === 'string' && pythonModuleExists(adapter.detect.python_module);
      results[adapter.id] = commandAvailable || moduleAvailable
        ? { availability: 'available', detected_at: detectedAt, command: commandAvailable ? adapter.detect.command : `python -m ${adapter.detect.python_module}` }
        : { availability: 'missing', detected_at: detectedAt, reason: `未在 PATH 中找到 ${adapter.detect.command} 命令或 Python 模块 ${adapter.detect.python_module ?? '(未配置)'}。` };
      continue;
    }
    const paths = (adapter.detect?.paths ?? []).map((path) => path
      .replaceAll('${PROJECT_ROOT}', root)
      .replaceAll('${CODEX_HOME}', codexHome)
      .replaceAll('${HOME}', homedir()));
    const location = await anyPathExists(paths);
    results[adapter.id] = location
      ? { availability: 'available', detected_at: detectedAt, location }
      : { availability: 'missing', detected_at: detectedAt, reason: `未检测到 ${adapter.id} 的可识别安装位置。` };
  }
  return results;
}

export async function recordAdapterDetection(root) {
  const detected = await detectAdapters(root);
  const statePath = adapterStatePath(root);
  const current = (await pathExists(statePath)) ? JSON.parse(await text(statePath)) : {};
  for (const [id, status] of Object.entries(detected)) current[id] = { ...(current[id] ?? {}), ...status };
  await mkdir(dirname(statePath), { recursive: true });
  await writeFile(statePath, `${JSON.stringify(current, null, 2)}\n`, 'utf8');
  return detected;
}

export async function recordAdapterCheck(root, adapterId, { version, releaseUrl }) {
  const status = await adapterStatus(root, adapterId);
  const adapter = status.adapters[0];
  if (!version) throw new Error('adapter check 需要 --version <version>。');
  if (releaseUrl && !/^https:\/\//i.test(releaseUrl)) throw new Error('--release-url 必须是 https URL。');
  const statePath = adapterStatePath(root);
  const current = (await pathExists(statePath)) ? JSON.parse(await text(statePath)) : {};
  current[adapterId] = {
    checked_at: new Date().toISOString(),
    available_version: version,
    release_url: releaseUrl ?? null,
    action: 'awaiting_user_confirmation',
    policy: adapter.update_policy,
  };
  await mkdir(dirname(statePath), { recursive: true });
  await writeFile(statePath, `${JSON.stringify(current, null, 2)}\n`, 'utf8');
  return { id: adapterId, ...adapter, state: current[adapterId] };
}

export async function installAdapter(root, adapterId, { authorized = false } = {}) {
  if (!authorized) throw new Error('安装外部适配器需要明确传入 --authorized。');
  const adapter = (await adapterDefinitions(root)).find((item) => item.id === adapterId);
  if (!adapter) throw new Error(`未知适配器：${adapterId}`);
  if (adapter.install?.method !== 'pip') {
    return {
      id: adapterId,
      installed: false,
      manual: true,
      instruction: adapter.install?.instruction ?? '此适配器需要在对应宿主中手动安装。',
    };
  }
  const result = spawnSync('python', ['-m', 'pip', 'install', adapter.install.package], {
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
    windowsHide: true,
  });
  if (result.status !== 0) {
    const statePath = adapterStatePath(root);
    const current = (await pathExists(statePath)) ? JSON.parse(await text(statePath)) : {};
    current[adapterId] = {
      ...(current[adapterId] ?? {}),
      last_install_attempt_at: new Date().toISOString(),
      last_install_result: 'failed',
      last_install_error: result.stderr?.trim() || result.stdout?.trim() || '未知错误',
    };
    await mkdir(dirname(statePath), { recursive: true });
    await writeFile(statePath, `${JSON.stringify(current, null, 2)}\n`, 'utf8');
    throw new Error(`安装 ${adapterId} 失败：${current[adapterId].last_install_error}`);
  }
  const detected = await recordAdapterDetection(root);
  return { id: adapterId, installed: detected[adapterId]?.availability === 'available', output: result.stdout.trim(), detected: detected[adapterId] };
}

export async function buildUpgradePlan(root, templatesRoot) {
  const manifest = await readManifest(root);
  if (!manifest) throw new Error('未发现 manifest.yaml；请先运行 workflow-os init。');
  const actions = [];
  const tracked = manifest.managed_files ?? {};
  for (const entry of await managedTemplateEntries(templatesRoot)) {
    const prior = tracked[entry.sourceId];
    const sourceHash = hash(await text(entry.sourcePath));
    const targetPath = join(root, entry.target);
    if (!prior) {
      actions.push({ kind: 'untracked', source: entry.sourceId, target: entry.target });
    } else if (!(await pathExists(targetPath))) {
      actions.push({ kind: 'create', source: entry.sourceId, target: entry.target, sourceHash });
    } else {
      const targetHash = hash(await text(targetPath));
      if (targetHash !== prior.installed_hash) {
        actions.push({ kind: 'local_override', source: entry.sourceId, target: entry.target });
      } else if (sourceHash !== prior.source_hash) {
        actions.push({ kind: 'update', source: entry.sourceId, target: entry.target, sourceHash });
      } else {
        actions.push({ kind: 'current', source: entry.sourceId, target: entry.target });
      }
    }
  }

  const codexSource = hash(codexBlock(await text(join(templatesRoot, 'codex'))));
  if (manifest.codex?.enabled && codexSource !== manifest.codex.source_hash) {
    actions.push({ kind: 'update_managed_block', source: 'codex', target: 'AGENTS.md', sourceHash: codexSource });
  }
  for (const [adapterId, adapter] of Object.entries(manifest.adapters ?? {})) {
    actions.push({
      kind: 'external_check_required',
      source: adapter.source,
      target: adapterId,
      policy: adapter.update_policy ?? 'manual',
    });
  }
  return { manifest, actions };
}

export async function applyUpgradePlan(root, templatesRoot, version, plan) {
  const entries = new Map((await managedTemplateEntries(templatesRoot)).map((entry) => [entry.sourceId, entry]));
  const applied = [];
  for (const action of plan.actions) {
    if (!['create', 'update'].includes(action.kind)) continue;
    const entry = entries.get(action.source);
    const target = join(root, entry.target);
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, await text(entry.sourcePath), 'utf8');
    plan.manifest.managed_files[action.source] = {
      target: entry.target,
      source_hash: hash(await text(entry.sourcePath)),
      installed_hash: hash(await text(target)),
    };
    applied.push(action);
  }
  if (plan.actions.some((action) => action.kind === 'update_managed_block')) {
    const changes = [];
    const codex = await installCodexGuidance(root, join(templatesRoot, 'codex'), false, changes);
    plan.manifest.codex = { enabled: codex.enabled, source_hash: codex.sourceHash };
    applied.push(...plan.actions.filter((action) => action.kind === 'update_managed_block'));
  }
  plan.manifest.workflow_os_version = version;
  plan.manifest.updated_at = new Date().toISOString();
  await writeManifest(root, plan.manifest);
  return applied;
}

async function budget(root) {
  const path = join(root, '.workflow', 'agent-budget.yaml');
  const loaded = (await pathExists(path)) ? parse(await text(path)) : {};
  return { ...DEFAULT_BUDGET, ...(loaded && typeof loaded === 'object' ? loaded : {}) };
}

function runtimeName(workId) {
  return workId.replace(/[^a-zA-Z0-9_-]+/g, '_');
}

export async function recordGuard(root, workId, outcome, errorSignature) {
  if (!['progress', 'no-progress'].includes(outcome)) throw new Error('--outcome 必须是 progress 或 no-progress。');
  const settings = await budget(root);
  const runtimePath = join(root, '.workflow', 'runtime', `${runtimeName(workId)}.json`);
  const previous = (await pathExists(runtimePath)) ? JSON.parse(await text(runtimePath)) : {
    work_id: workId,
    rounds: 0,
    consecutive_no_progress: 0,
    last_error: null,
    same_error_count: 0,
  };
  const next = { ...previous, rounds: previous.rounds + 1, updated_at: new Date().toISOString() };
  next.consecutive_no_progress = outcome === 'no-progress' ? previous.consecutive_no_progress + 1 : 0;
  if (errorSignature) {
    next.same_error_count = previous.last_error === errorSignature ? previous.same_error_count + 1 : 1;
    next.last_error = errorSignature;
  } else if (outcome === 'progress') {
    next.last_error = null;
    next.same_error_count = 0;
  }
  const reasons = [];
  if (next.rounds >= Number(settings.max_agent_rounds)) reasons.push('达到 max_agent_rounds');
  if (next.consecutive_no_progress >= Number(settings.no_progress_limit)) reasons.push('达到 no_progress_limit');
  if (next.same_error_count >= Number(settings.repeated_error_limit)) reasons.push('达到 repeated_error_limit');
  next.decision = reasons.length > 0 ? 'stop' : 'continue';
  next.reasons = reasons;
  await mkdir(dirname(runtimePath), { recursive: true });
  await writeFile(runtimePath, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
  return { settings, state: next };
}
