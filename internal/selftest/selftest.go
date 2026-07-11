// Package selftest 在运行时校验门规则的关键行为,
// 供 `tessera selftest` 与 doctor 使用。
package selftest

import "tessera/internal/gate"

// Case 是一条内置断言:cmd 期望匹配到 want(空串表示应放行)。
type Case struct {
	Command string
	Want    string
}

// Cases 覆盖每条规则 id 至少一个正例,加若干负例。
var Cases = []Case{
	{"rm -rf $HOME/data", "recursive-delete-outside"},
	{"rm -rf node_modules", "recursive-delete-inside"},
	{"git push --force origin main", "force-push-protected"},
	{"git push --force origin feature/x", "force-push-other"},
	{"git reset --hard HEAD~1", "discard-changes"},
	{"npm install -g typescript", "untrusted-global-install"},
	{"npm install -g @beads/bd", ""},
	{"echo hi > trust.yaml", "self-protect"},
	{"git status", ""},
	{"ls -la", ""},
}

// Result 是单条断言的执行结果。
type Result struct {
	Command string
	Want    string
	Got     string
	Pass    bool
}

// Run 对每条内置用例跑一次匹配并比对。
func Run(rules *gate.Rules) []Result {
	out := make([]Result, 0, len(Cases))
	for _, c := range Cases {
		got := ""
		if m := gate.MatchCommand(c.Command, rules); m != nil {
			got = m.ID
		}
		out = append(out, Result{
			Command: c.Command,
			Want:    c.Want,
			Got:     got,
			Pass:    got == c.Want,
		})
	}
	return out
}

// AllPass 报告是否全部断言通过。
func AllPass(results []Result) bool {
	for _, r := range results {
		if !r.Pass {
			return false
		}
	}
	return true
}
