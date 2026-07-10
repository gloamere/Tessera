import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename, join, relative, resolve } from 'node:path';
import { makeStableId, pathExists, toProjectPath } from './project.mjs';

function command(command, args) {
  return spawnSync(command, args, { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, windowsHide: true });
}

function markItDownCommand() {
  const locator = command(process.platform === 'win32' ? 'where.exe' : 'which', ['markitdown']);
  if (locator.status === 0) return { executable: 'markitdown', prefix: [] };
  const module = command('python', ['-c', 'import markitdown']);
  if (module.status === 0) return { executable: 'python', prefix: ['-m', 'markitdown'] };
  return null;
}

function safeName(value) {
  return value.toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48);
}

function yamlString(value) { return JSON.stringify(value); }

export async function ingestWithMarkItDown(root, sourcePath, options = {}) {
  const source = resolve(process.cwd(), sourcePath);
  if (!(await pathExists(source))) throw new Error(`未找到本地资料：${sourcePath}`);
  const markitdown = markItDownCommand();
  if (!markitdown) throw new Error('未检测到 markitdown。请先由负责人授权安装，再使用资料导入。');
  const converted = command(markitdown.executable, [...markitdown.prefix, source]);
  if (converted.status !== 0) throw new Error(`MarkItDown 转换失败：${converted.stderr?.trim() || converted.error?.message || '未知错误'}`);
  const id = options.id ?? makeStableId('source');
  const filename = `${safeName(options.slug ?? id) || id}.md`;
  const output = join(root, 'docs', 'sources', filename);
  if (await pathExists(output)) throw new Error(`目标资料已存在：${toProjectPath(root, output)}`);
  const original = await readFile(source);
  const originalHash = createHash('sha256').update(original).digest('hex');
  const version = command(markitdown.executable, [...markitdown.prefix, '--version']);
  const sourceRelative = relative(root, source).replaceAll('\\', '/');
  const frontmatter = [
    '---',
    'schema: workflow-os/source@1',
    `id: ${yamlString(id)}`,
    `title: ${yamlString(options.title ?? basename(source))}`,
    'converter: markitdown',
    `converter_version: ${yamlString(version.status === 0 ? version.stdout.trim() : 'unknown')}`,
    `original_path: ${yamlString(sourceRelative || source)}`,
    `original_sha256: ${yamlString(originalHash)}`,
    `imported_at: ${yamlString(new Date().toISOString())}`,
    `research: ${options.researchId ? yamlString(options.researchId) : 'null'}`,
    `work_item: ${options.workItemId ? yamlString(options.workItemId) : 'null'}`,
    '---',
    '',
    `# ${options.title ?? basename(source)}`,
    '',
  ].join('\n');
  await mkdir(join(root, 'docs', 'sources'), { recursive: true });
  await writeFile(output, `${frontmatter}${converted.stdout.trim()}\n`, 'utf8');
  return { id, path: toProjectPath(root, output), originalSha256: originalHash };
}
