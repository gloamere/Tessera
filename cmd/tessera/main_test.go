package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

var (
	binPath   string
	rulesAbs  string
)

// TestMain 编译一次 tessera 二进制,供各 IO 契约用例复用。
func TestMain(m *testing.M) {
	dir, err := os.MkdirTemp("", "tessera-iotest")
	if err != nil {
		panic(err)
	}
	defer os.RemoveAll(dir)

	binPath = filepath.Join(dir, "tessera")
	if runtime.GOOS == "windows" {
		binPath += ".exe"
	}
	build := exec.Command("go", "build", "-o", binPath, ".")
	build.Stderr = os.Stderr
	if err := build.Run(); err != nil {
		panic("go build failed: " + err.Error())
	}

	abs, err := filepath.Abs(filepath.Join("..", "..", "pieces", "wfos-core", "gate-rules.json"))
	if err != nil {
		panic(err)
	}
	rulesAbs = abs

	os.Exit(m.Run())
}

func runGateBin(t *testing.T, stdin string, args ...string) (string, string, int) {
	t.Helper()
	cmd := exec.Command(binPath, args...)
	cmd.Stdin = strings.NewReader(stdin)
	cmd.Env = append(os.Environ(), "WFOS_GATE_RULES="+rulesAbs)
	var out, errb strings.Builder
	cmd.Stdout = &out
	cmd.Stderr = &errb
	err := cmd.Run()
	code := 0
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			code = ee.ExitCode()
		} else {
			t.Fatalf("run: %v", err)
		}
	}
	return out.String(), errb.String(), code
}

func bashPayload(command string) string {
	b, _ := json.Marshal(map[string]any{
		"tool_name":  "Bash",
		"tool_input": map[string]any{"command": command},
	})
	return string(b)
}

func field(t *testing.T, out, path string) string {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal([]byte(out), &m); err != nil {
		t.Fatalf("invalid JSON %q: %v", out, err)
	}
	var cur any = m
	for _, k := range strings.Split(path, ".") {
		obj, ok := cur.(map[string]any)
		if !ok {
			t.Fatalf("path %q: %q not an object", path, k)
		}
		cur = obj[k]
	}
	s, _ := cur.(string)
	return s
}

func TestClaudeAsk(t *testing.T) {
	out, _, code := runGateBin(t, bashPayload("git reset --hard HEAD~1"), "gate", "--platform=claude")
	if code != 0 {
		t.Fatalf("exit %d", code)
	}
	if got := field(t, out, "hookSpecificOutput.hookEventName"); got != "PreToolUse" {
		t.Errorf("hookEventName = %q", got)
	}
	if got := field(t, out, "hookSpecificOutput.permissionDecision"); got != "ask" {
		t.Errorf("permissionDecision = %q", got)
	}
	if !strings.Contains(out, "discard-changes") {
		t.Errorf("reason missing rule id: %q", out)
	}
}

func TestClaudeDeny(t *testing.T) {
	out, _, code := runGateBin(t, bashPayload("git push --force origin main"), "gate", "--platform=claude")
	if code != 0 {
		t.Fatalf("exit %d", code)
	}
	if got := field(t, out, "hookSpecificOutput.permissionDecision"); got != "deny" {
		t.Errorf("permissionDecision = %q", got)
	}
	if !strings.Contains(out, "force-push-protected") {
		t.Errorf("reason missing rule id: %q", out)
	}
}

func TestClaudeNoMatch(t *testing.T) {
	out, _, code := runGateBin(t, bashPayload("git status"), "gate", "--platform=claude")
	if code != 0 {
		t.Fatalf("exit %d", code)
	}
	if strings.TrimSpace(out) != "" {
		t.Errorf("want empty stdout, got %q", out)
	}
}

func TestCodexPreToolUseDeny(t *testing.T) {
	out, errb, code := runGateBin(t, bashPayload("git push --force origin main"), "gate", "--platform=codex")
	if code != 0 {
		t.Fatalf("exit %d", code)
	}
	if got := field(t, out, "hookSpecificOutput.hookEventName"); got != "PreToolUse" {
		t.Errorf("hookEventName = %q", got)
	}
	if got := field(t, out, "hookSpecificOutput.permissionDecision"); got != "deny" {
		t.Errorf("permissionDecision = %q", got)
	}
	if strings.TrimSpace(errb) != "" {
		t.Errorf("want empty stderr, got %q", errb)
	}
}

func TestCodexNative(t *testing.T) {
	out, errb, code := runGateBin(t, bashPayload("git reset --hard HEAD~1"), "gate", "--platform=codex")
	if code != 0 {
		t.Fatalf("exit %d", code)
	}
	if strings.TrimSpace(out) != "" || strings.TrimSpace(errb) != "" {
		t.Errorf("want no output, got stdout=%q stderr=%q", out, errb)
	}
}

func TestCodexPermissionRequestDeny(t *testing.T) {
	out, _, code := runGateBin(t, bashPayload("git push --force origin main"), "gate", "--platform=codex", "--event=PermissionRequest")
	if code != 0 {
		t.Fatalf("exit %d", code)
	}
	if got := field(t, out, "hookSpecificOutput.hookEventName"); got != "PermissionRequest" {
		t.Errorf("hookEventName = %q", got)
	}
	if got := field(t, out, "hookSpecificOutput.decision.behavior"); got != "deny" {
		t.Errorf("behavior = %q", got)
	}
	if !strings.Contains(field(t, out, "hookSpecificOutput.decision.message"), "force-push-protected") {
		t.Errorf("message missing rule id: %q", out)
	}
}

func TestFailOpenBadPayload(t *testing.T) {
	_, _, code := runGateBin(t, "not json", "gate", "--platform=claude")
	if code != 0 {
		t.Fatalf("want exit 0 on bad payload, got %d", code)
	}
}
