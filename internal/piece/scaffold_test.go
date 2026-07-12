package piece

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
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

func seedPiece(t *testing.T, root, id string) {
	t.Helper()
	mustWrite(t, filepath.Join(root, "pieces", id, ".claude-plugin", "plugin.json"),
		`{"name":"`+id+`","description":"d","version":"0.1.0","author":{"name":"van"}}`+"\n")
	mustWrite(t, filepath.Join(root, "pieces", id, ".codex-plugin", "plugin.json"),
		`{"name":"`+id+`","description":"d","version":"0.1.0","skills":"./skills/"}`+"\n")
}

func pluginVersion(t *testing.T, root, id, sub string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(root, "pieces", id, sub, "plugin.json"))
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatal(err)
	}
	return m["version"].(string)
}

func TestBumpSyncsThreeVersions(t *testing.T) {
	root := tmpRepo(t)
	seedPiece(t, root, "demo")
	cm, _ := readClaudeMarket(root)
	cm.Plugins = append(cm.Plugins, ClaudePlugin{Name: "demo", Source: "./pieces/demo", Description: "d", Version: "0.1.0", Strict: true})
	writeClaudeMarket(root, cm)

	if err := Bump(root, "demo", "0.2.0"); err != nil {
		t.Fatal(err)
	}
	if v := pluginVersion(t, root, "demo", ".claude-plugin"); v != "0.2.0" {
		t.Fatalf("claude plugin.json = %s", v)
	}
	if v := pluginVersion(t, root, "demo", ".codex-plugin"); v != "0.2.0" {
		t.Fatalf("codex plugin.json = %s", v)
	}
	cm2, _ := readClaudeMarket(root)
	for _, p := range cm2.Plugins {
		if p.Name == "demo" && p.Version != "0.2.0" {
			t.Fatalf("marketplace = %s", p.Version)
		}
	}
	if err := Bump(root, "demo", "bad"); err == nil {
		t.Fatal("非法版本应报错")
	}
	if err := Bump(root, "nope", "0.2.0"); err == nil {
		t.Fatal("不存在的 id 应报错")
	}
}

func TestNewScaffoldsAndRegisters(t *testing.T) {
	root := tmpRepo(t)
	added, err := New(root, NewOpts{ID: "demo", Intent: "演示意图", Desc: "演示拼图"})
	if err != nil {
		t.Fatal(err)
	}
	if !added {
		t.Fatal("给了 intent 应插路由行")
	}
	for _, rel := range []string{
		"pieces/demo/piece.yaml",
		"pieces/demo/.claude-plugin/plugin.json",
		"pieces/demo/.codex-plugin/plugin.json",
		"pieces/demo/skills/demo/SKILL.md",
	} {
		if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(rel))); err != nil {
			t.Fatalf("缺文件 %s", rel)
		}
	}
	cm, _ := readClaudeMarket(root)
	xm, _ := readCodexMarket(root)
	if !hasClaude(cm, "demo") || !hasCodex(xm, "demo") {
		t.Fatal("两市集应各多一条 demo")
	}
	router, _ := os.ReadFile(filepath.Join(root, "pieces", "tessera-core", "skills", "piece-router", "SKILL.md"))
	if !strings.Contains(string(router), "| 演示意图 | demo |") {
		t.Fatal("路由行未插入")
	}
	// 无 intent:不插行,routerAdded=false
	added2, err := New(root, NewOpts{ID: "quiet"})
	if err != nil {
		t.Fatal(err)
	}
	if added2 {
		t.Fatal("无 intent 不应插路由行")
	}
	// 重复拒绝
	if _, err := New(root, NewOpts{ID: "demo"}); err == nil {
		t.Fatal("重复 id 应报错")
	}
}

func hasClaude(m *ClaudeMarket, id string) bool {
	for _, p := range m.Plugins {
		if p.Name == id {
			return true
		}
	}
	return false
}
func hasCodex(m *CodexMarket, id string) bool {
	for _, p := range m.Plugins {
		if p.Name == id {
			return true
		}
	}
	return false
}

func TestRemove(t *testing.T) {
	root := tmpRepo(t)
	New(root, NewOpts{ID: "demo", Intent: "演示意图", Desc: "演示拼图"})

	// dry-run 不动文件
	actions, err := Remove(root, "demo", false)
	if err != nil {
		t.Fatal(err)
	}
	if len(actions) == 0 {
		t.Fatal("dry-run 应返回动作清单")
	}
	if _, err := os.Stat(filepath.Join(root, "pieces", "demo")); err != nil {
		t.Fatal("dry-run 不应删除目录")
	}

	// 确认删除,三处清干净
	if _, err := Remove(root, "demo", true); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(root, "pieces", "demo")); !os.IsNotExist(err) {
		t.Fatal("目录应被删")
	}
	cm, _ := readClaudeMarket(root)
	xm, _ := readCodexMarket(root)
	if hasClaude(cm, "demo") || hasCodex(xm, "demo") {
		t.Fatal("市集条目应被删")
	}
	router, _ := os.ReadFile(routerPath(root))
	if strings.Contains(string(router), "| demo |") {
		t.Fatal("路由行应被删")
	}

	// 保护内核 + 不存在报错
	if _, err := Remove(root, "tessera-core", true); err == nil {
		t.Fatal("应拒删 tessera-core")
	}
	if _, err := Remove(root, "nope", true); err == nil {
		t.Fatal("不存在应报错")
	}
}
