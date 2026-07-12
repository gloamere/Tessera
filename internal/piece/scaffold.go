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
