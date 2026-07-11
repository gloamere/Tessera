package initproject

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// 对应 tests/init-project.test.mjs。
func TestInitCreatesOnlyMissing(t *testing.T) {
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "docs"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "docs", "PROJECT.md"), []byte("# Existing project\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "AGENTS.md"), []byte("# Human rules\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	var out bytes.Buffer
	if code := Run([]string{"--target", root, "--name", "Test Project"}, &out); code != 0 {
		t.Fatalf("exit %d: %s", code, out.String())
	}

	// 已存在的 PROJECT.md 不被覆盖
	got, _ := os.ReadFile(filepath.Join(root, "docs", "PROJECT.md"))
	if string(got) != "# Existing project\n" {
		t.Errorf("PROJECT.md 被改动:%q", string(got))
	}
	// 缺失文件被补齐
	if !exists(filepath.Join(root, ".tessera", "project.yaml")) {
		t.Error("project.yaml 未创建")
	}
	if !exists(filepath.Join(root, "docs", "research", "README.md")) {
		t.Error("research/README.md 未创建")
	}
	// AGENTS.md 保留人类规则并注入托管块
	guidance, _ := os.ReadFile(filepath.Join(root, "AGENTS.md"))
	if !strings.Contains(string(guidance), "# Human rules") {
		t.Error("人类规则被抹掉")
	}
	if !strings.Contains(string(guidance), "tessera:v2:start") {
		t.Error("托管块标记缺失")
	}

	// 重跑应 skip
	var out2 bytes.Buffer
	Run([]string{"--target", root, "--name", "Test Project"}, &out2)
	if !strings.Contains(out2.String(), "skip") {
		t.Errorf("重跑应含 skip,得:%s", out2.String())
	}
}

func TestInitDryRun(t *testing.T) {
	root := t.TempDir()
	sub := filepath.Join(root, "proj")
	var out bytes.Buffer
	Run([]string{"--target", sub, "--dry-run"}, &out)
	if !strings.Contains(out.String(), "Preview") {
		t.Errorf("dry-run 应含 Preview,得:%s", out.String())
	}
	if exists(filepath.Join(sub, "docs")) || exists(filepath.Join(sub, "AGENTS.md")) {
		t.Error("dry-run 不应写文件")
	}
}

// 托管块存在时更新、损坏时拒绝。
func TestInitManagedBlockGuard(t *testing.T) {
	root := t.TempDir()
	// 只有 start 无 end → 损坏 → 报错(退出码 1)
	if err := os.WriteFile(filepath.Join(root, "AGENTS.md"), []byte("x\n<!-- tessera:v2:start -->\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	if code := Run([]string{"--target", root}, &out); code == 0 {
		t.Errorf("标记损坏应非零退出,输出:%s", out.String())
	}
}
