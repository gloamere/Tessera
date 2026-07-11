// Package piece 读取拼图清单 piece.yaml。
// 零依赖:只解析本仓库用到的 piece.yaml 子集(顶层标量 + external_deps 列表),
// 不是通用 YAML 解析器。
package piece

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// ExternalDep 是一条外部依赖声明(仅取门/状态需要的字段)。
type ExternalDep struct {
	Name         string
	VersionCheck string
}

// Piece 是单块拼图的语义描述。
type Piece struct {
	ID            string
	Kind          string
	Summary       string
	UpgradePolicy string
	ExternalDeps  []ExternalDep
	Dir           string
}

var reTopKey = regexp.MustCompile(`^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$`)

// List 扫描 <root>/pieces/*/piece.yaml,按 id 排序返回。
func List(root string) ([]Piece, error) {
	entries, err := os.ReadDir(filepath.Join(root, "pieces"))
	if err != nil {
		return nil, err
	}
	var pieces []Piece
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		path := filepath.Join(root, "pieces", e.Name(), "piece.yaml")
		data, err := os.ReadFile(path)
		if err != nil {
			continue // 无 piece.yaml(如占位 .gitkeep 目录)跳过
		}
		p := Parse(data)
		p.Dir = e.Name()
		pieces = append(pieces, p)
	}
	sort.Slice(pieces, func(i, j int) bool { return pieces[i].ID < pieces[j].ID })
	return pieces, nil
}

// Parse 解析 piece.yaml 的子集。
func Parse(data []byte) Piece {
	var p Piece
	lines := strings.Split(strings.ReplaceAll(string(data), "\r\n", "\n"), "\n")
	for i := 0; i < len(lines); i++ {
		m := reTopKey.FindStringSubmatch(lines[i])
		if m == nil {
			continue // 缩进行由其所属顶层键处理
		}
		key, val := m[1], stripComment(m[2])
		switch key {
		case "id":
			p.ID = unquote(val)
		case "kind":
			p.Kind = unquote(val)
		case "summary":
			p.Summary = unquote(val)
		case "upgrade_policy":
			p.UpgradePolicy = unquote(val)
		case "external_deps":
			if strings.HasPrefix(strings.TrimSpace(val), "[") {
				continue // 内联 []:无依赖
			}
			p.ExternalDeps = parseDeps(lines[i+1:])
		}
	}
	return p
}

// parseDeps 从 external_deps: 之后的缩进块收集依赖,遇到下一个顶层键即停。
func parseDeps(lines []string) []ExternalDep {
	var deps []ExternalDep
	for _, raw := range lines {
		if strings.TrimSpace(raw) == "" {
			continue
		}
		if !isIndented(raw) {
			break // 回到顶层,块结束
		}
		t := strings.TrimSpace(raw)
		switch {
		case strings.HasPrefix(t, "- name:"):
			deps = append(deps, ExternalDep{Name: unquote(stripComment(strings.TrimSpace(t[len("- name:"):])))})
		case strings.HasPrefix(t, "name:") && len(deps) == 0:
			deps = append(deps, ExternalDep{Name: unquote(stripComment(strings.TrimSpace(t[len("name:"):])))})
		case strings.HasPrefix(t, "version_check:") && len(deps) > 0:
			deps[len(deps)-1].VersionCheck = unquote(stripComment(strings.TrimSpace(t[len("version_check:"):])))
		}
	}
	return deps
}

func isIndented(line string) bool {
	return len(line) > 0 && (line[0] == ' ' || line[0] == '\t')
}

// stripComment 去掉行内 " #" 之后的注释(不处理引号内 #,本仓库无此情形)。
func stripComment(s string) string {
	if idx := strings.Index(s, " #"); idx >= 0 {
		return strings.TrimSpace(s[:idx])
	}
	return strings.TrimSpace(s)
}

func unquote(s string) string {
	s = strings.TrimSpace(s)
	if len(s) >= 2 {
		if (s[0] == '"' && s[len(s)-1] == '"') || (s[0] == '\'' && s[len(s)-1] == '\'') {
			return s[1 : len(s)-1]
		}
	}
	return s
}
