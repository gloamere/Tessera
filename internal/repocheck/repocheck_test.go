package repocheck

import (
	"path/filepath"
	"testing"
)

func root() string { return filepath.Join("..", "..") }

// 对应 tests/repo-hygiene.test.mjs 的 BOM 检查。
func TestNoBOM(t *testing.T) {
	hits, err := BOMFiles(root())
	if err != nil {
		t.Fatalf("BOMFiles: %v", err)
	}
	if len(hits) > 0 {
		t.Errorf("发现带 BOM 的文件:%v", hits)
	}
}

// 对应 repo-hygiene 的 bootstrap 固定版本/拒覆盖检查。
func TestBootstrap(t *testing.T) {
	if err := CheckBootstrap(root()); err != nil {
		t.Error(err)
	}
}

// 对应 repo-hygiene 的两市集一致性检查。
func TestMarketplaces(t *testing.T) {
	if err := CheckMarketplaces(root()); err != nil {
		t.Error(err)
	}
}

// 对应 tests/codex-hooks.test.mjs。
func TestCodexHooks(t *testing.T) {
	if err := CheckCodexHooks(root()); err != nil {
		t.Error(err)
	}
}
