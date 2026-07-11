package doctor

import (
	"path/filepath"
	"testing"
)

func TestRunAllOK(t *testing.T) {
	checks := Run(filepath.Join("..", ".."))
	if len(checks) == 0 {
		t.Fatal("无检查项")
	}
	if !AllOK(checks) {
		for _, c := range checks {
			if !c.OK {
				t.Errorf("检查失败:%s — %s", c.Name, c.Detail)
			}
		}
	}
}
