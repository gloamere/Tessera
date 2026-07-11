package setup

import (
	"bytes"
	"path/filepath"
	"strings"
	"testing"
)

func repoRoot() string { return filepath.Join("..", "..") }

func TestBuildPlan(t *testing.T) {
	p, err := BuildPlan(Options{Root: repoRoot(), Codex: true})
	if err != nil {
		t.Fatalf("BuildPlan: %v", err)
	}
	if p.OS == "" || p.Arch == "" {
		t.Errorf("平台探测为空:%q/%q", p.OS, p.Arch)
	}
	if len(p.Marketplace) != 2 {
		t.Errorf("含 --codex 应有 2 条注册命令,得 %d", len(p.Marketplace))
	}
}

func TestBuildPlanMissingPieces(t *testing.T) {
	if _, err := BuildPlan(Options{Root: t.TempDir()}); err == nil {
		t.Error("无 pieces/ 应报错")
	}
}

func TestRunDryRunDoesNotRegister(t *testing.T) {
	var out bytes.Buffer
	Run(Options{Root: repoRoot()}, &out)
	s := out.String()
	if !strings.Contains(s, "dry-run") {
		t.Errorf("默认应 dry-run,输出:%s", s)
	}
	if strings.Contains(s, "执行:") {
		t.Errorf("dry-run 不应执行注册:%s", s)
	}
}
