package selftest

import (
	"path/filepath"
	"testing"

	"tessera/internal/gate"
)

func TestRunAllPass(t *testing.T) {
	rules, err := gate.LoadRules(filepath.Join("..", "..", "pieces", "wfos-core", "gate-rules.json"))
	if err != nil {
		t.Fatalf("LoadRules: %v", err)
	}
	results := Run(rules)
	if len(results) != len(Cases) {
		t.Fatalf("结果数 %d != 用例数 %d", len(results), len(Cases))
	}
	if !AllPass(results) {
		for _, r := range results {
			if !r.Pass {
				t.Errorf("断言失败:%q 期望 %q 实得 %q", r.Command, r.Want, r.Got)
			}
		}
	}
}
