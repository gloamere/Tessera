// Package doctor 对仓库/安装环境做体检,供 `tessera doctor` 使用。
package doctor

import (
	"strconv"

	"tessera/internal/piece"
	"tessera/internal/repocheck"
)

// Check 是单项体检结果。
type Check struct {
	Name   string
	OK     bool
	Detail string
}

// Run 以 root 为仓库/安装根跑各项检查。
func Run(root string) []Check {
	var checks []Check

	pieces, err := piece.List(root)
	if err != nil || len(pieces) == 0 {
		checks = append(checks, Check{"拼图清单", false, "未找到任何 pieces/*/piece.yaml"})
	} else {
		checks = append(checks, Check{"拼图清单", true, strconv.Itoa(len(pieces)) + " 块拼图"})
	}

	if err := repocheck.CheckMarketplaces(root); err != nil {
		checks = append(checks, Check{"市集一致性", false, err.Error()})
	} else {
		checks = append(checks, Check{"市集一致性", true, "两市集与 plugin.json 版本一致"})
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
