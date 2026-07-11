// Package gate 是不可逆操作门的匹配核心(spec §7.2)。
// 从 gate.mjs 1:1 移植:匹配是启发式 guardrail,不是安全边界。
package gate

import (
	"encoding/json"
	"os"
	"regexp"
	"strings"
)

// Rule 对应 gate-rules.json 中的单条规则。
type Rule struct {
	ID          string `json:"id"`
	Description string `json:"description"`
	Claude      string `json:"claude"`
	Codex       string `json:"codex"`
}

// Rules 是 gate-rules.json 的整体结构。
type Rules struct {
	Version            int      `json:"version"`
	GlobalInstallAllow []string `json:"global_install_allowlist"`
	// ExemptCommands 是精确规范化命令白名单:命中即旁路所有规则(逃生舱)。
	ExemptCommands []string `json:"exempt_commands"`
	Rules          []Rule   `json:"rules"`
}

// LoadRules 读取并解析规则数据文件。
func LoadRules(path string) (*Rules, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var r Rules
	if err := json.Unmarshal(b, &r); err != nil {
		return nil, err
	}
	return &r, nil
}

// Action 返回该规则在指定平台的动作(claude / codex)。
func (r *Rule) Action(platform string) string {
	if platform == "codex" {
		return r.Codex
	}
	return r.Claude
}

var (
	absTarget      = regexp.MustCompile(`(?i)^([A-Za-z]:[\\/]|[\\/]$|[\\/][^\\/]|~|\$HOME\b|\$env:USERPROFILE\b|%USERPROFILE%)`)
	reFlagToken    = regexp.MustCompile(`(?i)^-[a-z]+$`)
	reGitPush      = regexp.MustCompile(`\bgit\s+push\b`)
	reForceFlag    = regexp.MustCompile(`(\s--force(-with-lease)?\b|\s-f\b)`)
	reProtected    = regexp.MustCompile(`\b(main|master)\b`)
	reResetHard    = regexp.MustCompile(`\bgit\s+reset\s+--hard\b`)
	reCheckoutDD   = regexp.MustCompile(`\bgit\s+checkout\s+--\s`)
	reCleanForce   = regexp.MustCompile(`(?i)\bgit\s+clean\s+-[a-z]*f`)
	reNpmGlobal    = regexp.MustCompile(`\bnpm\s+(install|i|add)\b[^&|;]*(\s-g\b|\s--global\b)`)
	rePipInstall   = regexp.MustCompile(`\bpip3?\s+install\s`)
	reWhitespace   = regexp.MustCompile(`\s+`)
	reSelfTarget   = regexp.MustCompile(`(?i)(trust\.yaml|gate-rules\.json)`)
	reSelfWrite    = regexp.MustCompile(`(?i)(>>?|\bset-content\b|\bout-file\b|\bsed\s+-i\b|\btee\b|\brm\b|\bremove-item\b|\bdel\b|\bmv\b|\bmove\b)`)
	// reFdNoise 匹配 fd 重定向/丢弃(2>&1、1>&2、2>/dev/null 等),不是写具名文件。
	reFdNoise = regexp.MustCompile(`(?i)\d*>&\d*|\d+>\s*(/dev/null|nul|\$null)\b`)
	// reSegment 按命令分隔符切段(; && || | 换行);单个 & 不切,避免拆散 2>&1。
	reSegment = regexp.MustCompile(`&&|\|\||[;\n|]`)
)

// words 复刻 gate.mjs 的分词:去首尾空白、按空白切分、剥去首尾一层引号。
func words(cmd string) []string {
	fields := strings.Fields(strings.TrimSpace(cmd))
	out := make([]string, len(fields))
	for i, w := range fields {
		if len(w) > 0 && (w[0] == '\'' || w[0] == '"') {
			w = w[1:]
		}
		if len(w) > 0 && (w[len(w)-1] == '\'' || w[len(w)-1] == '"') {
			w = w[:len(w)-1]
		}
		out[i] = w
	}
	return out
}

func nonFlags(tokens []string) []string {
	var out []string
	for _, t := range tokens {
		if !strings.HasPrefix(t, "-") {
			out = append(out, t)
		}
	}
	return out
}

func indexOf(tokens []string, want string) int {
	for i, t := range tokens {
		if t == want {
			return i
		}
	}
	return -1
}

func anyHasPrefix(tokens []string, prefix string) bool {
	for _, t := range tokens {
		if strings.HasPrefix(t, prefix) {
			return true
		}
	}
	return false
}

func matchRecursiveDelete(cmd string) string {
	w := words(cmd)
	lower := make([]string, len(w))
	for i, x := range w {
		lower[i] = strings.ToLower(x)
	}
	var targets []string
	found := false

	if rmIdx := indexOf(lower, "rm"); rmIdx >= 0 {
		var flags strings.Builder
		for _, x := range w[rmIdx+1:] {
			if reFlagToken.MatchString(x) {
				flags.WriteString(x)
			}
		}
		f := strings.ToLower(flags.String())
		if strings.Contains(f, "r") && strings.Contains(f, "f") {
			targets = nonFlags(w[rmIdx+1:])
			found = true
		}
	}

	riIdx := -1
	for i, x := range lower {
		if x == "remove-item" || x == "ri" {
			riIdx = i
			break
		}
	}
	if riIdx >= 0 && anyHasPrefix(lower, "-recurse") && anyHasPrefix(lower, "-force") {
		targets = nonFlags(w[riIdx+1:])
		found = true
	}

	if rrIdx := indexOf(lower, "rimraf"); rrIdx >= 0 {
		targets = nonFlags(w[rrIdx+1:])
		found = true
	}

	if !found {
		return ""
	}
	for _, t := range targets {
		if absTarget.MatchString(t) {
			return "recursive-delete-outside"
		}
	}
	return "recursive-delete-inside"
}

func matchForcePush(cmd string) string {
	if !reGitPush.MatchString(cmd) {
		return ""
	}
	if !reForceFlag.MatchString(cmd) {
		return ""
	}
	if reProtected.MatchString(cmd) {
		return "force-push-protected"
	}
	return "force-push-other"
}

func matchDiscardChanges(cmd string) string {
	if reResetHard.MatchString(cmd) || reCheckoutDD.MatchString(cmd) || reCleanForce.MatchString(cmd) {
		return "discard-changes"
	}
	return ""
}

func matchGlobalInstall(cmd string, allowlist []string) string {
	if !reNpmGlobal.MatchString(cmd) && !rePipInstall.MatchString(cmd) {
		return ""
	}
	normalized := reWhitespace.ReplaceAllString(strings.TrimSpace(cmd), " ")
	for _, a := range allowlist {
		if a == normalized {
			return ""
		}
	}
	return "untrusted-global-install"
}

func matchSelfProtect(cmd string) string {
	if !reSelfTarget.MatchString(cmd) {
		return ""
	}
	// 先剥掉 fd 重定向噪声,避免把 `2>&1` 之类误当成写受保护文件。
	cleaned := reFdNoise.ReplaceAllString(cmd, " ")
	if reSelfWrite.MatchString(cleaned) {
		return "self-protect"
	}
	return ""
}

// MatchCommand 逐"命令段"匹配:先按分隔符切段,再对每段跑匹配器。
// 真正危险的命令都落在单段内,切段能消除跨段误伤(如另一段 echo "main" 触发强推保护),
// 而不削弱防护。命中即返回对应规则;未命中返回 nil。
func MatchCommand(command string, rules *Rules) *Rule {
	if command == "" || rules == nil {
		return nil
	}
	// 逃生舱:精确规范化命令白名单命中则完全放行。
	normalized := reWhitespace.ReplaceAllString(strings.TrimSpace(command), " ")
	for _, e := range rules.ExemptCommands {
		if e == normalized {
			return nil
		}
	}
	allow := rules.GlobalInstallAllow
	for _, seg := range reSegment.Split(command, -1) {
		seg = strings.TrimSpace(seg)
		if seg == "" {
			continue
		}
		id := firstNonEmpty(
			matchRecursiveDelete(seg),
			matchForcePush(seg),
			matchDiscardChanges(seg),
			matchGlobalInstall(seg, allow),
			matchSelfProtect(seg),
		)
		if id == "" {
			continue
		}
		for i := range rules.Rules {
			if rules.Rules[i].ID == id {
				return &rules.Rules[i]
			}
		}
	}
	return nil
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}

// ExtractCommand 从任意 hook payload 中按常见路径取出命令字符串。
func ExtractCommand(payload map[string]any) string {
	get := func(path ...string) string {
		var cur any = payload
		for _, k := range path {
			m, ok := cur.(map[string]any)
			if !ok {
				return ""
			}
			cur = m[k]
		}
		if s, ok := cur.(string); ok {
			return s
		}
		return ""
	}
	for _, c := range []string{
		get("tool_input", "command"),
		get("tool_input", "script"),
		get("command"),
		get("params", "command"),
		get("arguments", "command"),
	} {
		if strings.TrimSpace(c) != "" {
			return c
		}
	}
	return ""
}
