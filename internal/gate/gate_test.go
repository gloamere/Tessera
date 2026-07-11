package gate

import (
	"path/filepath"
	"testing"
)

func testRules(t *testing.T) *Rules {
	t.Helper()
	r, err := LoadRules(filepath.Join("..", "..", "pieces", "wfos-core", "gate-rules.json"))
	if err != nil {
		t.Fatalf("LoadRules: %v", err)
	}
	return r
}

// 与 tests/gate-match.test.mjs 的 CASES 一一对应。
var matchCases = []struct {
	cmd  string
	want string // "" 表示 nil
}{
	{`rm -rf C:\Users\Administrator\proj`, "recursive-delete-outside"},
	{`rm -fr /`, "recursive-delete-outside"},
	{`rm -r -f ~/stuff`, "recursive-delete-outside"},
	{`rm -rf node_modules`, "recursive-delete-inside"},
	{`rm -rf ./build dist`, "recursive-delete-inside"},
	{`Remove-Item -Recurse -Force C:\env\old`, "recursive-delete-outside"},
	{`Remove-Item -Recurse -Force .\build`, "recursive-delete-inside"},
	{`Remove-Item -Recurse -Force $env:USERPROFILE\tmp`, "recursive-delete-outside"},
	{`rimraf dist`, "recursive-delete-inside"},
	{`rm -r src`, ""},
	{`git push --force origin main`, "force-push-protected"},
	{`git push -f origin master`, "force-push-protected"},
	{`git push --force-with-lease origin main`, "force-push-protected"},
	{`git push --force origin feature/x`, "force-push-other"},
	{`git push -f`, "force-push-other"},
	{`git push origin main`, ""},
	{`git reset --hard HEAD~1`, "discard-changes"},
	{`git checkout -- .`, "discard-changes"},
	{`git clean -fd`, "discard-changes"},
	{`git clean -xfd`, "discard-changes"},
	{`git checkout main`, ""},
	{`npm install -g typescript`, "untrusted-global-install"},
	{`npm i -g @foo/bar`, "untrusted-global-install"},
	{`npm install -g @beads/bd`, ""},
	{`pip install requests`, "untrusted-global-install"},
	{`npm install typescript`, ""},
	{`echo hi > trust.yaml`, "self-protect"},
	{`Set-Content gate-rules.json x`, "self-protect"},
	{`sed -i s/a/b/ pieces/wfos-core/gate-rules.json`, "self-protect"},
	{`cat trust.yaml`, ""},
	{`ls -la`, ""},
}

func TestMatchCommand(t *testing.T) {
	rules := testRules(t)
	for _, tc := range matchCases {
		t.Run(tc.cmd, func(t *testing.T) {
			m := MatchCommand(tc.cmd, rules)
			got := ""
			if m != nil {
				got = m.ID
			}
			if got != tc.want {
				t.Errorf("MatchCommand(%q) = %q, want %q", tc.cmd, got, tc.want)
			}
		})
	}
}

func TestExtractCommand(t *testing.T) {
	cases := []struct {
		name    string
		payload map[string]any
		want    string
	}{
		{"claude PreToolUse", map[string]any{"tool_name": "Bash", "tool_input": map[string]any{"command": "git status"}}, "git status"},
		{"top-level command", map[string]any{"command": "ls"}, "ls"},
		{"params.command", map[string]any{"params": map[string]any{"command": "ls"}}, "ls"},
		{"arguments.command", map[string]any{"arguments": map[string]any{"command": "ls"}}, "ls"},
		{"empty", map[string]any{}, ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := ExtractCommand(tc.payload); got != tc.want {
				t.Errorf("ExtractCommand(%v) = %q, want %q", tc.payload, got, tc.want)
			}
		})
	}
}

// TestDecide 覆盖 gate-io.test.mjs 的裁决渲染契约(纯函数,无子进程)。
func TestDecide(t *testing.T) {
	rules := testRules(t)
	find := func(cmd string) *Rule { return MatchCommand(cmd, rules) }

	t.Run("claude ask", func(t *testing.T) {
		out, emit := Decide(find("git reset --hard HEAD~1"), "claude", "PreToolUse")
		if !emit {
			t.Fatal("want emit")
		}
		assertJSONField(t, out, "hookSpecificOutput.hookEventName", "PreToolUse")
		assertJSONField(t, out, "hookSpecificOutput.permissionDecision", "ask")
		assertContains(t, out, "discard-changes")
	})

	t.Run("claude deny", func(t *testing.T) {
		out, emit := Decide(find("git push --force origin main"), "claude", "PreToolUse")
		if !emit {
			t.Fatal("want emit")
		}
		assertJSONField(t, out, "hookSpecificOutput.permissionDecision", "deny")
		assertContains(t, out, "force-push-protected")
	})

	t.Run("claude no match → no emit", func(t *testing.T) {
		if _, emit := Decide(find("git status"), "claude", "PreToolUse"); emit {
			t.Fatal("want no emit")
		}
	})

	t.Run("codex PreToolUse deny", func(t *testing.T) {
		out, emit := Decide(find("git push --force origin main"), "codex", "PreToolUse")
		if !emit {
			t.Fatal("want emit")
		}
		assertJSONField(t, out, "hookSpecificOutput.hookEventName", "PreToolUse")
		assertJSONField(t, out, "hookSpecificOutput.permissionDecision", "deny")
	})

	t.Run("codex native → no emit", func(t *testing.T) {
		if _, emit := Decide(find("git reset --hard HEAD~1"), "codex", "PreToolUse"); emit {
			t.Fatal("want no emit")
		}
	})

	t.Run("codex PermissionRequest deny", func(t *testing.T) {
		out, emit := Decide(find("git push --force origin main"), "codex", "PermissionRequest")
		if !emit {
			t.Fatal("want emit")
		}
		assertJSONField(t, out, "hookSpecificOutput.hookEventName", "PermissionRequest")
		assertJSONField(t, out, "hookSpecificOutput.decision.behavior", "deny")
		assertContains(t, out, "force-push-protected")
	})
}
