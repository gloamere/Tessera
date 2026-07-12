# 拼图脚手架命令 (piece new/rm/bump) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `tessera piece` 加 `new`/`rm`/`bump` 三个子命令,自动化拼图的样板生成与多处登记同步。

**Architecture:** 纯逻辑放 `internal/piece/scaffold.go`(`New`/`Remove`/`Bump` + 两份 marketplace 的读写辅助 + 路由表行增删);CLI 分发与打印放 `cmd/tessera/main.go` 的 `runPiece`。marketplace.json 用"解析→改→标准缩进重写"(`json.MarshalIndent`),用完整结构体 + `json.RawMessage` 保住 `owner`/`metadata`/`interface` 等未建模的顶层字段。每次 mutation 收尾调 `repocheck.CheckMarketplaces` 报告。

**Tech Stack:** Go 1.23,零第三方依赖,标准库 `encoding/json` / `os` / `regexp` / `strings`。

## Global Constraints

- 零第三方依赖:只用 Go 标准库(仓库硬约束)。
- 构建离线:`export PATH="/c/Go/bin:$PATH" GOTOOLCHAIN=local`(Go 装在 `C:\Go`,不在 PATH)。
- 写文件一律 UTF-8 **无 BOM**(`repocheck.BOMFiles` 会抓)。
- 命令非交互:靠 flag,不弹提示。
- 新拼图初始 version = `0.1.0`;version 格式 `X.Y.Z`。
- Codex marketplace 条目无 `version` 字段;`bump` 不动它。
- `tessera-core` 是内核,`rm` 必须硬拒。
- 保留 marketplace.json 两文件的全部顶层字段(claude:`name`/`owner`/`metadata`/`plugins`;codex:`name`/`interface`/`plugins`)。

---

### Task 1: marketplace 读写辅助 + 无 BOM JSON 写入

**Files:**
- Create: `internal/piece/scaffold.go`
- Test: `internal/piece/scaffold_test.go`

**Interfaces:**
- Produces:
  - `type ClaudeMarket struct { Name string; Owner json.RawMessage; Metadata json.RawMessage; Plugins []ClaudePlugin }`
  - `type ClaudePlugin struct { Name, Source, Description, Version string; Strict bool }`
  - `type CodexMarket struct { Name string; Interface json.RawMessage; Plugins []CodexPlugin }`
  - `type CodexPlugin struct { Name string; Source CodexSource; Policy CodexPolicy; Category string }`
  - `type CodexSource struct { Source, Path string }` ; `type CodexPolicy struct { Installation, Authentication string }`
  - `func readClaudeMarket(root string) (*ClaudeMarket, error)`
  - `func writeClaudeMarket(root string, m *ClaudeMarket) error`
  - `func readCodexMarket(root string) (*CodexMarket, error)`
  - `func writeCodexMarket(root string, m *CodexMarket) error`
  - `func writeJSON(path string, v any) error` — `MarshalIndent(v,"","  ")` + 结尾 `\n`,无 BOM

- [ ] **Step 1: Write the failing test**

`internal/piece/scaffold_test.go`:
```go
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `export PATH="/c/Go/bin:$PATH" GOTOOLCHAIN=local; go test ./internal/piece/ -run TestMarketRoundTrip -v`
Expected: FAIL(编译错误:`readClaudeMarket` 等未定义)

- [ ] **Step 3: Write minimal implementation**

`internal/piece/scaffold.go`:
```go
// Package piece 的脚手架:创建/删除/升版本拼图并同步登记。
package piece

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type ClaudePlugin struct {
	Name        string `json:"name"`
	Source      string `json:"source"`
	Description string `json:"description"`
	Version     string `json:"version"`
	Strict      bool   `json:"strict"`
}
type ClaudeMarket struct {
	Name     string          `json:"name"`
	Owner    json.RawMessage `json:"owner,omitempty"`
	Metadata json.RawMessage `json:"metadata,omitempty"`
	Plugins  []ClaudePlugin  `json:"plugins"`
}
type CodexSource struct {
	Source string `json:"source"`
	Path   string `json:"path"`
}
type CodexPolicy struct {
	Installation   string `json:"installation"`
	Authentication string `json:"authentication"`
}
type CodexPlugin struct {
	Name     string      `json:"name"`
	Source   CodexSource `json:"source"`
	Policy   CodexPolicy `json:"policy"`
	Category string      `json:"category"`
}
type CodexMarket struct {
	Name      string          `json:"name"`
	Interface json.RawMessage `json:"interface,omitempty"`
	Plugins   []CodexPlugin   `json:"plugins"`
}

func claudeMarketPath(root string) string {
	return filepath.Join(root, ".claude-plugin", "marketplace.json")
}
func codexMarketPath(root string) string {
	return filepath.Join(root, ".agents", "plugins", "marketplace.json")
}

func readClaudeMarket(root string) (*ClaudeMarket, error) {
	b, err := os.ReadFile(claudeMarketPath(root))
	if err != nil {
		return nil, err
	}
	var m ClaudeMarket
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	return &m, nil
}
func writeClaudeMarket(root string, m *ClaudeMarket) error {
	return writeJSON(claudeMarketPath(root), m)
}
func readCodexMarket(root string) (*CodexMarket, error) {
	b, err := os.ReadFile(codexMarketPath(root))
	if err != nil {
		return nil, err
	}
	var m CodexMarket
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	return &m, nil
}
func writeCodexMarket(root string, m *CodexMarket) error {
	return writeJSON(codexMarketPath(root), m)
}

// writeJSON 以 2 空格缩进 + 结尾换行写出,无 BOM。
func writeJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/piece/ -run TestMarketRoundTrip -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add internal/piece/scaffold.go internal/piece/scaffold_test.go
rtk git commit -m "feat(piece): marketplace 读写辅助,保住顶层字段、无 BOM"
```

---

### Task 2: `Bump` — 同步 3 个 version 字段

**Files:**
- Modify: `internal/piece/scaffold.go`
- Test: `internal/piece/scaffold_test.go`

**Interfaces:**
- Consumes: `readClaudeMarket`/`writeClaudeMarket` (Task 1)
- Produces:
  - `func Bump(root, id, version string) error` — 写 `pieces/<id>/.claude-plugin/plugin.json`、`.codex-plugin/plugin.json` 的 `version`,以及 claude marketplace 中 `<id>` 条目的 `version`。id 不存在或版本非法 → error。
  - `var reSemver = regexp.MustCompile(\`^\d+\.\d+\.\d+$\`)`
  - `func setPluginVersion(root, id, sub, version string) error` — 改 `pieces/<id>/<sub>/plugin.json` 的 version,保住其余字段(用 `map[string]json.RawMessage`)

- [ ] **Step 1: Write the failing test**

追加到 `scaffold_test.go`:
```go
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/piece/ -run TestBump -v`
Expected: FAIL(`Bump` 未定义)

- [ ] **Step 3: Write minimal implementation**

追加到 `scaffold.go`(import 增加 `"fmt"`、`"regexp"`):
```go
var reSemver = regexp.MustCompile(`^\d+\.\d+\.\d+$`)

func Bump(root, id, version string) error {
	if !reSemver.MatchString(version) {
		return fmt.Errorf("版本号非法(需 X.Y.Z):%s", version)
	}
	cm, err := readClaudeMarket(root)
	if err != nil {
		return err
	}
	found := false
	for i := range cm.Plugins {
		if cm.Plugins[i].Name == id {
			cm.Plugins[i].Version = version
			found = true
		}
	}
	if !found {
		return fmt.Errorf("拼图 %q 不在 claude marketplace", id)
	}
	if err := setPluginVersion(root, id, ".claude-plugin", version); err != nil {
		return err
	}
	if err := setPluginVersion(root, id, ".codex-plugin", version); err != nil {
		return err
	}
	return writeClaudeMarket(root, cm)
}

// setPluginVersion 改 plugin.json 的 version,保住其余字段。
func setPluginVersion(root, id, sub, version string) error {
	path := filepath.Join(root, "pieces", id, sub, "plugin.json")
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(b, &m); err != nil {
		return err
	}
	vb, _ := json.Marshal(version)
	m["version"] = vb
	return writeJSON(path, m)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/piece/ -run TestBump -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add internal/piece/scaffold.go internal/piece/scaffold_test.go
rtk git commit -m "feat(piece): bump 同步三处 version"
```

---

### Task 3: `New` — 生成骨架 + 登记两市集 + 可选路由行

**Files:**
- Modify: `internal/piece/scaffold.go`
- Test: `internal/piece/scaffold_test.go`

**Interfaces:**
- Consumes: `read/writeClaudeMarket`, `read/writeCodexMarket` (Task 1)
- Produces:
  - `type NewOpts struct { ID, Skill, Intent, Desc string }`
  - `func New(root string, o NewOpts) (routerAdded bool, err error)` — 生成 4 文件、追加两市集条目;`o.Intent!=""` 时插路由行返回 `true`,否则 `false`。`o.Skill==""` 用 `o.ID`;`o.Desc==""` 用 `o.ID+" 拼图"`。目录已存在或 id 已在任一市集 → error(不写入)。
  - `func insertRouterRow(root, id, intent string) error` — 在含 `tessera-core 自身` 的行前插入 `| <intent> | <id> | Skill 工具调用 <id> |`
  - `func pieceRegistered(root, id string) bool` — dir 存在 或 在任一市集

- [ ] **Step 1: Write the failing test**

追加到 `scaffold_test.go`(import 增加 `"strings"`):
```go
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/piece/ -run TestNew -v`
Expected: FAIL(`New`/`NewOpts` 未定义)

- [ ] **Step 3: Write minimal implementation**

追加到 `scaffold.go`(import 增加 `"strings"`):
```go
type NewOpts struct {
	ID     string
	Skill  string
	Intent string
	Desc   string
}

func New(root string, o NewOpts) (bool, error) {
	if o.ID == "" {
		return false, fmt.Errorf("需要拼图 id")
	}
	if o.Skill == "" {
		o.Skill = o.ID
	}
	if o.Desc == "" {
		o.Desc = o.ID + " 拼图"
	}
	if pieceRegistered(root, o.ID) {
		return false, fmt.Errorf("拼图 %q 已存在", o.ID)
	}

	pieceYAML := "id: " + o.ID + "\nkind: skill\nsummary: " + o.Desc + "\nwhen_to_use:\n  - <填写触发意图>\navoid_when: <填写不适用场景>\nplatforms: { claude: native, codex: native, gemini: snippet, domestic: snippet }\nexternal_deps: []\nupgrade_policy: notify-only\n"
	claudePlugin := "{\n  \"name\": \"" + o.ID + "\",\n  \"description\": \"" + o.Desc + "\",\n  \"version\": \"0.1.0\",\n  \"author\": { \"name\": \"van\" }\n}\n"
	codexPlugin := "{\n  \"name\": \"" + o.ID + "\",\n  \"description\": \"" + o.Desc + "\",\n  \"version\": \"0.1.0\",\n  \"skills\": \"./skills/\"\n}\n"
	skillMD := "---\nname: " + o.Skill + "\ndescription: <一句话:何时触发本 skill,决定路由>\n---\n\n# " + o.Skill + "\n\n<方法论正文>\n"

	writes := []struct{ rel, body string }{
		{filepath.Join("pieces", o.ID, "piece.yaml"), pieceYAML},
		{filepath.Join("pieces", o.ID, ".claude-plugin", "plugin.json"), claudePlugin},
		{filepath.Join("pieces", o.ID, ".codex-plugin", "plugin.json"), codexPlugin},
		{filepath.Join("pieces", o.ID, "skills", o.Skill, "SKILL.md"), skillMD},
	}
	for _, w := range writes {
		p := filepath.Join(root, w.rel)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			return false, err
		}
		if err := os.WriteFile(p, []byte(w.body), 0o644); err != nil {
			return false, err
		}
	}

	cm, err := readClaudeMarket(root)
	if err != nil {
		return false, err
	}
	cm.Plugins = append(cm.Plugins, ClaudePlugin{
		Name: o.ID, Source: "./pieces/" + o.ID, Description: o.Desc, Version: "0.1.0", Strict: true,
	})
	if err := writeClaudeMarket(root, cm); err != nil {
		return false, err
	}
	xm, err := readCodexMarket(root)
	if err != nil {
		return false, err
	}
	xm.Plugins = append(xm.Plugins, CodexPlugin{
		Name:     o.ID,
		Source:   CodexSource{Source: "local", Path: "./pieces/" + o.ID},
		Policy:   CodexPolicy{Installation: "AVAILABLE", Authentication: "ON_INSTALL"},
		Category: "Productivity",
	})
	if err := writeCodexMarket(root, xm); err != nil {
		return false, err
	}

	if o.Intent != "" {
		if err := insertRouterRow(root, o.ID, o.Intent); err != nil {
			return false, err
		}
		return true, nil
	}
	return false, nil
}

func pieceRegistered(root, id string) bool {
	if _, err := os.Stat(filepath.Join(root, "pieces", id)); err == nil {
		return true
	}
	if cm, err := readClaudeMarket(root); err == nil {
		for _, p := range cm.Plugins {
			if p.Name == id {
				return true
			}
		}
	}
	if xm, err := readCodexMarket(root); err == nil {
		for _, p := range xm.Plugins {
			if p.Name == id {
				return true
			}
		}
	}
	return false
}

func routerPath(root string) string {
	return filepath.Join(root, "pieces", "tessera-core", "skills", "piece-router", "SKILL.md")
}

func insertRouterRow(root, id, intent string) error {
	path := routerPath(root)
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	row := "| " + intent + " | " + id + " | Skill 工具调用 " + id + " |"
	lines := strings.Split(string(b), "\n")
	out := make([]string, 0, len(lines)+1)
	inserted := false
	for _, ln := range lines {
		if !inserted && strings.Contains(ln, "tessera-core 自身") {
			out = append(out, row)
			inserted = true
		}
		out = append(out, ln)
	}
	if !inserted {
		return fmt.Errorf("piece-router 未找到 tessera-core 自路由行,无法定位插入点")
	}
	return os.WriteFile(path, []byte(strings.Join(out, "\n")), 0o644)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/piece/ -run TestNew -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add internal/piece/scaffold.go internal/piece/scaffold_test.go
rtk git commit -m "feat(piece): new 生成骨架并登记两市集 + 可选路由行"
```

---

### Task 4: `Remove` — dry-run/确认删除 + 内核保护 + 清路由

**Files:**
- Modify: `internal/piece/scaffold.go`
- Test: `internal/piece/scaffold_test.go`

**Interfaces:**
- Consumes: `read/writeClaudeMarket`, `read/writeCodexMarket`, `routerPath` (Task 1/3)
- Produces:
  - `func Remove(root, id string, confirm bool) (actions []string, err error)` — `confirm==false` 只返回将执行的动作描述、不改文件;`confirm==true` 真删目录 + 两市集条目 + 路由行。`id=="tessera-core"` → error;找不到 → error。
  - `func removeRouterRow(root, id string) error` — 删含 `| <id> |` 的行(无则跳过)

- [ ] **Step 1: Write the failing test**

追加到 `scaffold_test.go`:
```go
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/piece/ -run TestRemove -v`
Expected: FAIL(`Remove` 未定义)

- [ ] **Step 3: Write minimal implementation**

追加到 `scaffold.go`:
```go
func Remove(root, id string, confirm bool) ([]string, error) {
	if id == "tessera-core" {
		return nil, fmt.Errorf("拒绝删除内核 tessera-core")
	}
	if !pieceRegistered(root, id) {
		return nil, fmt.Errorf("拼图 %q 不存在", id)
	}
	actions := []string{
		"删除目录 pieces/" + id + "/",
		"从 .claude-plugin/marketplace.json 摘除 " + id,
		"从 .agents/plugins/marketplace.json 摘除 " + id,
		"从 piece-router 删除 " + id + " 路由行(若有)",
	}
	if !confirm {
		return actions, nil
	}
	if err := os.RemoveAll(filepath.Join(root, "pieces", id)); err != nil {
		return nil, err
	}
	cm, err := readClaudeMarket(root)
	if err != nil {
		return nil, err
	}
	kept := cm.Plugins[:0]
	for _, p := range cm.Plugins {
		if p.Name != id {
			kept = append(kept, p)
		}
	}
	cm.Plugins = kept
	if err := writeClaudeMarket(root, cm); err != nil {
		return nil, err
	}
	xm, err := readCodexMarket(root)
	if err != nil {
		return nil, err
	}
	xkept := xm.Plugins[:0]
	for _, p := range xm.Plugins {
		if p.Name != id {
			xkept = append(xkept, p)
		}
	}
	xm.Plugins = xkept
	if err := writeCodexMarket(root, xm); err != nil {
		return nil, err
	}
	return actions, removeRouterRow(root, id)
}

func removeRouterRow(root, id string) error {
	path := routerPath(root)
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	needle := "| " + id + " |"
	lines := strings.Split(string(b), "\n")
	out := make([]string, 0, len(lines))
	for _, ln := range lines {
		if strings.Contains(ln, needle) {
			continue
		}
		out = append(out, ln)
	}
	return os.WriteFile(path, []byte(strings.Join(out, "\n")), 0o644)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/piece/ -run TestRemove -v` 然后 `go test ./internal/piece/ -v`(全包回归)
Expected: PASS(全部)

- [ ] **Step 5: Commit**

```bash
rtk git add internal/piece/scaffold.go internal/piece/scaffold_test.go
rtk git commit -m "feat(piece): rm 支持 dry-run/确认、内核保护、清路由"
```

---

### Task 5: CLI 接线 `piece new|rm|bump` + repocheck 收尾

**Files:**
- Modify: `cmd/tessera/main.go`(`runPiece` 现约 178-203 行,`printHelp` 约 51-62 行)
- 手动验收(main 包,逻辑已在 piece 包单测覆盖)

**Interfaces:**
- Consumes: `piece.New`/`piece.Remove`/`piece.Bump` (Task 3/4/2)、`repocheck.CheckMarketplaces(root string) error`

- [ ] **Step 1: 改 runPiece 分发**

把 `cmd/tessera/main.go` 的 `runPiece` 整个替换为:
```go
func runPiece(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "用法:tessera piece list|new|rm|bump")
		return 2
	}
	root := repoRoot()
	switch args[0] {
	case "list":
		return runPieceList(root)
	case "new":
		return runPieceNew(root, args[1:])
	case "rm":
		return runPieceRm(root, args[1:])
	case "bump":
		return runPieceBump(root, args[1:])
	default:
		fmt.Fprintln(os.Stderr, "用法:tessera piece list|new|rm|bump")
		return 2
	}
}

func runPieceList(root string) int {
	pieces, err := piece.List(root)
	if err != nil {
		fmt.Fprintln(os.Stderr, "piece list:"+err.Error())
		return 1
	}
	for _, p := range pieces {
		deps := "—"
		if len(p.ExternalDeps) > 0 {
			names := make([]string, len(p.ExternalDeps))
			for i, d := range p.ExternalDeps {
				names[i] = d.Name
			}
			deps = strings.Join(names, ",")
		}
		fmt.Printf("%-14s %-12s 依赖:%-10s %s\n", p.ID, p.Kind, deps, p.Summary)
	}
	if len(pieces) == 0 {
		fmt.Println("(无拼图)")
	}
	return 0
}

// reportMarkets 打印 repocheck 结果,供 new/rm/bump 收尾复用。
func reportMarkets(root string) int {
	if err := repocheck.CheckMarketplaces(root); err != nil {
		fmt.Fprintln(os.Stderr, "✗ 市集校验失败:"+err.Error())
		return 1
	}
	fmt.Println("✓ 市集一致")
	return 0
}

func runPieceNew(root string, args []string) int {
	var o piece.NewOpts
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "用法:tessera piece new <id> [--skill <n>] [--intent \"…\"] [--desc \"…\"]")
		return 2
	}
	o.ID = args[0]
	for i := 1; i < len(args); i++ {
		switch args[i] {
		case "--skill":
			if i+1 < len(args) {
				o.Skill = args[i+1]
				i++
			}
		case "--intent":
			if i+1 < len(args) {
				o.Intent = args[i+1]
				i++
			}
		case "--desc":
			if i+1 < len(args) {
				o.Desc = args[i+1]
				i++
			}
		}
	}
	added, err := piece.New(root, o)
	if err != nil {
		fmt.Fprintln(os.Stderr, "piece new:"+err.Error())
		return 1
	}
	fmt.Printf("✓ 已创建拼图 %s(pieces/%s/)\n", o.ID, o.ID)
	if !added {
		fmt.Println("提醒:未加路由行——请手动在 piece-router 补一行,或重跑时带 --intent")
	}
	return reportMarkets(root)
}

func runPieceRm(root string, args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "用法:tessera piece rm <id> [--yes]")
		return 2
	}
	id := args[0]
	confirm := false
	for _, a := range args[1:] {
		if a == "--yes" {
			confirm = true
		}
	}
	actions, err := piece.Remove(root, id, confirm)
	if err != nil {
		fmt.Fprintln(os.Stderr, "piece rm:"+err.Error())
		return 1
	}
	if !confirm {
		fmt.Println("dry-run,将执行(加 --yes 生效):")
		for _, a := range actions {
			fmt.Println("  - " + a)
		}
		return 0
	}
	fmt.Printf("✓ 已删除拼图 %s\n", id)
	return reportMarkets(root)
}

func runPieceBump(root string, args []string) int {
	if len(args) < 2 {
		fmt.Fprintln(os.Stderr, "用法:tessera piece bump <id> <version>")
		return 2
	}
	if err := piece.Bump(root, args[0], args[1]); err != nil {
		fmt.Fprintln(os.Stderr, "piece bump:"+err.Error())
		return 1
	}
	fmt.Printf("✓ %s 版本 → %s\n", args[0], args[1])
	return reportMarkets(root)
}
```

- [ ] **Step 2: 加 import 与 help**

在 `cmd/tessera/main.go` import 块加 `"tessera/internal/repocheck"`。把 `printHelp` 里的 `tessera piece list` 一行替换为:
```
  tessera piece list                                    列出拼图与外部依赖
  tessera piece new <id> [--skill n][--intent …][--desc …]  脚手架新拼图 + 登记两市集
  tessera piece rm <id> [--yes]                         删拼图(默认 dry-run)
  tessera piece bump <id> <version>                     同步升三处 version
```

- [ ] **Step 3: 构建**

Run: `export PATH="/c/Go/bin:$PATH" GOTOOLCHAIN=local; go build -o /tmp/tsr.exe ./cmd/tessera`
Expected: 无错误

- [ ] **Step 4: 端到端手验(用临时 root 隔离,不污染仓库)**

Run:
```bash
export TESSERA_ROOT="$(mktemp -d)"
cp -r .claude-plugin .agents pieces "$TESSERA_ROOT"/
/tmp/tsr.exe piece new demo --skill demo --intent "演示意图" --desc "演示拼图"
/tmp/tsr.exe piece bump demo 0.2.0
/tmp/tsr.exe piece rm demo            # dry-run
/tmp/tsr.exe piece rm demo --yes
/tmp/tsr.exe piece list
unset TESSERA_ROOT
```
Expected:new 打印 `✓ 已创建` + `✓ 市集一致`;bump 打印 `✓ demo 版本 → 0.2.0`;rm 无 --yes 打印 dry-run 清单;rm --yes 打印 `✓ 已删除` + `✓ 市集一致`;list 不再含 demo。

- [ ] **Step 5: 全量测试 + 提交**

Run: `go test ./...`
Expected: 全绿(含既有 repocheck 测试)

```bash
rtk git add cmd/tessera/main.go
rtk git commit -m "feat(piece): 接线 new/rm/bump CLI + repocheck 收尾"
```

---

## Self-Review

**Spec coverage:**
- `new`(4 文件 + 两市集 + 可选路由 + 拒重复 + repocheck 收尾)→ Task 3 + Task 5 ✓
- `rm`(dry-run 默认 / --yes / 拒内核 / 清路由 / repocheck)→ Task 4 + Task 5 ✓
- `bump`(3 version 同步 / 版本校验 / 拒不存在)→ Task 2 + Task 5 ✓
- JSON 解析→改→标准缩进重写、保住顶层字段、无 BOM → Task 1 ✓
- 非交互、零依赖、version 0.1.0、Codex 无 version → 贯穿各 Task ✓
- `--desc`/`--skill` 默认值 → Task 3 `New` ✓

**Placeholder scan:** 计划内代码无 TBD/TODO;生成物模板里的 `<填写触发意图>` 等是**给用户填的骨架占位**(设计本意),非计划占位。

**Type consistency:** `New`→`(bool,error)`、`Remove`→`([]string,error)`、`Bump`→`error`;`ClaudePlugin`/`CodexPlugin` 字段在 Task 1 定义,Task 3/4 一致引用;`repocheck.CheckMarketplaces(root) error` 与源码一致;`routerPath`/`pieceRegistered` 定义于 Task 3,Task 4 复用。一致。
