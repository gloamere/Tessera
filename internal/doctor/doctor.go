// Package doctor 对仓库/安装环境做体检,供 `tessera doctor` 使用。
package doctor

import (
	"os"
	"path/filepath"
	"strconv"

	"tessera/internal/gate"
	"tessera/internal/piece"
	"tessera/internal/selftest"
)

func itoa(n int) string { return strconv.Itoa(n) }

// Check 是单项体检结果。
type Check struct {
	Name   string
	OK     bool
	Detail string
}

// Run 以 root 为仓库/安装根跑各项检查。
func Run(root string) []Check {
	var checks []Check

	rulesPath := filepath.Join(root, "pieces", "tessera-core", "gate-rules.json")
	rules, err := gate.LoadRules(rulesPath)
	if err != nil {
		checks = append(checks, Check{"规则数据文件", false, "无法读取/解析 " + rulesPath + ": " + err.Error()})
	} else {
		checks = append(checks, Check{"规则数据文件", true, "已加载 " + itoa(len(rules.Rules)) + " 条规则"})
	}

	pieces, err := piece.List(root)
	if err != nil || len(pieces) == 0 {
		checks = append(checks, Check{"拼图清单", false, "未找到任何 pieces/*/piece.yaml"})
	} else {
		checks = append(checks, Check{"拼图清单", true, itoa(len(pieces)) + " 块拼图"})
	}

	for _, hf := range []struct{ name, rel string }{
		{"Claude hooks 配置", filepath.Join("pieces", "tessera-core", "hooks", "hooks.json")},
		{"Codex hooks 配置", filepath.Join("pieces", "tessera-core", "hooks", "codex.hooks.json")},
	} {
		p := filepath.Join(root, hf.rel)
		if _, err := os.Stat(p); err != nil {
			checks = append(checks, Check{hf.name, false, "缺失 " + hf.rel})
		} else {
			checks = append(checks, Check{hf.name, true, hf.rel})
		}
	}

	if rules != nil {
		results := selftest.Run(rules)
		pass := 0
		for _, r := range results {
			if r.Pass {
				pass++
			}
		}
		ok := selftest.AllPass(results)
		checks = append(checks, Check{"门自检", ok, itoa(pass) + "/" + itoa(len(results)) + " 断言通过"})
	}

	return checks
}

// AllOK 报告是否全部检查通过。
func AllOK(checks []Check) bool {
	for _, c := range checks {
		if !c.OK {
			return false
		}
	}
	return true
}

