// Package piece 的脚手架:创建/删除/升版本拼图并同步登记。
package piece

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
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
