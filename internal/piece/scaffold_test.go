package piece

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// 搭一个最小 repo:两份 marketplace(含额外顶层字段)+ piece-router 桩。
func tmpRepo(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	mustWrite(t, filepath.Join(root, ".claude-plugin", "marketplace.json"), `{
  "name": "tessera",
  "owner": { "name": "van" },
  "metadata": { "description": "d", "version": "2.0.0" },
  "plugins": [
    { "name": "tessera-core", "source": "./pieces/tessera-core", "description": "内核", "version": "0.1.3", "strict": true }
  ]
}
`)
	mustWrite(t, filepath.Join(root, ".agents", "plugins", "marketplace.json"), `{
  "name": "tessera",
  "interface": { "displayName": "Tessera" },
  "plugins": [
    {
      "name": "tessera-core",
      "source": { "source": "local", "path": "./pieces/tessera-core" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
`)
	router := "# 拼图派发表\n\n| 意图 | 拼图 | 调用方式 |\n|---|---|---|\n| 记笔记 | knowledge-base | Skill 工具调用 knowledge-base |\n| 拼图状态/安装/升级 | tessera-core 自身 | tessera-status、tessera-setup skill |\n\n## 硬规则\n"
	mustWrite(t, filepath.Join(root, "pieces", "tessera-core", "skills", "piece-router", "SKILL.md"), router)
	return root
}

func mustWrite(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestMarketRoundTripPreservesTopLevel(t *testing.T) {
	root := tmpRepo(t)
	cm, err := readClaudeMarket(root)
	if err != nil {
		t.Fatal(err)
	}
	if err := writeClaudeMarket(root, cm); err != nil {
		t.Fatal(err)
	}
	b, _ := os.ReadFile(filepath.Join(root, ".claude-plugin", "marketplace.json"))
	if b[0] == 0xef {
		t.Fatal("写出带 BOM")
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(b, &raw); err != nil {
		t.Fatal(err)
	}
	for _, k := range []string{"name", "owner", "metadata", "plugins"} {
		if _, ok := raw[k]; !ok {
			t.Fatalf("顶层字段 %q 丢失", k)
		}
	}
	xm, err := readCodexMarket(root)
	if err != nil {
		t.Fatal(err)
	}
	if err := writeCodexMarket(root, xm); err != nil {
		t.Fatal(err)
	}
	xb, _ := os.ReadFile(filepath.Join(root, ".agents", "plugins", "marketplace.json"))
	var xraw map[string]json.RawMessage
	if err := json.Unmarshal(xb, &xraw); err != nil {
		t.Fatal(err)
	}
	if _, ok := xraw["interface"]; !ok {
		t.Fatal("codex interface 字段丢失")
	}
}
