package piece

import (
	"path/filepath"
	"testing"
)

func repoRoot() string { return filepath.Join("..", "..") }

func TestListRealPieces(t *testing.T) {
	pieces, err := List(repoRoot())
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	byID := map[string]Piece{}
	for _, p := range pieces {
		byID[p.ID] = p
	}
	if _, ok := byID["tessera-core"]; !ok {
		t.Errorf("缺 tessera-core,得到 %v", keys(byID))
	}
	bd, ok := byID["bd-tasks"]
	if !ok {
		t.Fatalf("缺 bd-tasks")
	}
	if bd.Kind != "cli-wrapper" {
		t.Errorf("bd-tasks kind = %q, want cli-wrapper", bd.Kind)
	}
	if len(bd.ExternalDeps) != 1 || bd.ExternalDeps[0].Name != "bd" {
		t.Errorf("bd-tasks external_deps = %+v, want 一条 name=bd", bd.ExternalDeps)
	}
	if bd.ExternalDeps[0].VersionCheck != "bd version" {
		t.Errorf("bd version_check = %q", bd.ExternalDeps[0].VersionCheck)
	}
}

func TestParseInlineEmptyDeps(t *testing.T) {
	src := []byte("id: demo\nkind: skill\nsummary: 演示\nexternal_deps: []\nupgrade_policy: notify-only\n")
	p := Parse(src)
	if p.ID != "demo" || p.Kind != "skill" || p.Summary != "演示" || p.UpgradePolicy != "notify-only" {
		t.Errorf("标量解析错误:%+v", p)
	}
	if len(p.ExternalDeps) != 0 {
		t.Errorf("external_deps [] 应为空,得 %+v", p.ExternalDeps)
	}
}

func keys(m map[string]Piece) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}
