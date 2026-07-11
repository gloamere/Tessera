#!/usr/bin/env node
/**
 * 不可逆操作门(spec §7.2)。零 npm 依赖:运行于插件缓存快照内。
 * 匹配是启发式 guardrail,不是安全边界(spec 已如实定性)。
 */
import { readFileSync, appendFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';

const here = dirname(fileURLToPath(import.meta.url));

export function loadRules(path = join(here, '..', 'gate-rules.json')) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

const ABS_TARGET = /^([A-Za-z]:[\\/]|[\\/]$|[\\/][^\\/]|~|\$HOME\b|\$env:USERPROFILE\b|%USERPROFILE%)/i;

const words = (cmd) => cmd.trim().split(/\s+/).map((w) => w.replace(/^['"]|['"]$/g, ''));

function matchRecursiveDelete(cmd) {
  const w = words(cmd);
  const lower = w.map((x) => x.toLowerCase());
  let targets = null;
  const rmIdx = lower.indexOf('rm');
  if (rmIdx >= 0) {
    const flags = w.slice(rmIdx + 1).filter((x) => /^-[a-z]+$/i.test(x)).join('');
    if (/r/i.test(flags) && /f/i.test(flags)) targets = w.slice(rmIdx + 1).filter((x) => !x.startsWith('-'));
  }
  const riIdx = lower.findIndex((x) => x === 'remove-item' || x === 'ri');
  if (riIdx >= 0 && lower.some((x) => x.startsWith('-recurse')) && lower.some((x) => x.startsWith('-force'))) {
    targets = w.slice(riIdx + 1).filter((x) => !x.startsWith('-'));
  }
  const rrIdx = lower.indexOf('rimraf');
  if (rrIdx >= 0) targets = w.slice(rrIdx + 1).filter((x) => !x.startsWith('-'));
  if (!targets) return null;
  return targets.some((t) => ABS_TARGET.test(t)) ? 'recursive-delete-outside' : 'recursive-delete-inside';
}

function matchForcePush(cmd) {
  if (!/\bgit\s+push\b/.test(cmd)) return null;
  if (!/(\s--force(-with-lease)?\b|\s-f\b)/.test(cmd)) return null;
  return /\b(main|master)\b/.test(cmd) ? 'force-push-protected' : 'force-push-other';
}

function matchDiscardChanges(cmd) {
  if (/\bgit\s+reset\s+--hard\b/.test(cmd)) return 'discard-changes';
  if (/\bgit\s+checkout\s+--\s/.test(cmd)) return 'discard-changes';
  if (/\bgit\s+clean\s+-[a-z]*f/i.test(cmd)) return 'discard-changes';
  return null;
}

function matchGlobalInstall(cmd, allowlist) {
  const npmGlobal = /\bnpm\s+(install|i|add)\b[^&|;]*(\s-g\b|\s--global\b)/.test(cmd);
  const pipInstall = /\bpip3?\s+install\s/.test(cmd);
  if (!npmGlobal && !pipInstall) return null;
  const normalized = cmd.trim().replace(/\s+/g, ' ');
  if (allowlist.includes(normalized)) return null;
  return 'untrusted-global-install';
}

function matchSelfProtect(cmd) {
  if (!/(trust\.yaml|gate-rules\.json)/i.test(cmd)) return null;
  if (/(>>?|\bset-content\b|\bout-file\b|\bsed\s+-i\b|\btee\b|\brm\b|\bremove-item\b|\bdel\b|\bmv\b|\bmove\b)/i.test(cmd)) return 'self-protect';
  return null;
}

export function matchCommand(command, rules) {
  if (!command || typeof command !== 'string') return null;
  const allow = rules.global_install_allowlist ?? [];
  const id = matchRecursiveDelete(command) ?? matchForcePush(command)
    ?? matchDiscardChanges(command) ?? matchGlobalInstall(command, allow) ?? matchSelfProtect(command);
  return id ? (rules.rules.find((r) => r.id === id) ?? null) : null;
}

export function extractCommand(payload) {
  const candidates = [
    payload?.tool_input?.command,
    payload?.tool_input?.script,
    payload?.command,
    payload?.params?.command,
    payload?.arguments?.command,
  ];
  for (const c of candidates) if (typeof c === 'string' && c.trim()) return c;
  return null;
}

// ---- CLI 入口(hook 调用) ----
const isMain = import.meta.main;
if (isMain) {
  let raw = '';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) raw += chunk;

  if (process.env.WFOS_GATE_DEBUG === '1') {
    try {
      const dir = join(homedir(), '.workflow-os');
      mkdirSync(dir, { recursive: true });
      appendFileSync(join(dir, 'gate-debug.log'), `${new Date().toISOString()} ${raw}\n`, 'utf8');
    } catch { /* 调试日志失败不影响裁决 */ }
  }

  const platform = process.argv.includes('--platform=codex') ? 'codex' : 'claude';
  const event = process.argv.find((arg) => arg.startsWith('--event='))?.slice('--event='.length)
    ?? (platform === 'codex' ? 'PreToolUse' : 'PreToolUse');
  let match = null;
  try {
    const payload = JSON.parse(raw);
    const command = extractCommand(payload);
    if (command) match = matchCommand(command, loadRules());
  } catch { /* fail-open:门是 guardrail,解析失败不阻塞工具 */ }

  if (match) {
    const reason = `[wfos 门] ${match.description}(规则 ${match.id})。请确认后再执行。`;
    const action = match[platform];
    if (platform === 'claude' && (action === 'ask' || action === 'deny')) {
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: action, permissionDecisionReason: reason },
      }));
    } else if (platform === 'codex' && action === 'deny') {
      if (event === 'PermissionRequest') {
        process.stdout.write(JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'PermissionRequest',
            decision: { behavior: 'deny', message: reason },
          },
        }));
      } else {
        process.stdout.write(JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            permissionDecision: 'deny',
            permissionDecisionReason: reason,
          },
        }));
      }
    }
    // codex 'native':不裁决 → 原生审批
  }
}
