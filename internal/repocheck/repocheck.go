// Package repocheck 提供仓库卫生/配置一致性校验。
// 从 tests/repo-hygiene.test.mjs 与 tests/codex-hooks.test.mjs 移植;
// 函数可被测试与 `tessera doctor` 复用。
package repocheck

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var skipDirs = map[string]bool{
	"node_modules": true, ".git": true, ".beads": true, ".superpowers": true,
}

var textExt = regexp.MustCompile(`(?i)\.(json|md|ya?ml)$`)

// BOMFiles 返回带 UTF-8 BOM 的 json/md/yaml 文件(应为空)。
func BOMFiles(root string) ([]string, error) {
	var hits []string
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if skipDirs[d.Name()] {
				return fs.SkipDir
			}
			return nil
		}
		if !textExt.MatchString(d.Name()) {
			return nil
		}
		b, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if len(b) >= 3 && b[0] == 0xef && b[1] == 0xbb && b[2] == 0xbf {
			hits = append(hits, path)
		}
		return nil
	})
	return hits, err
}

// CheckBootstrap 校验 Windows 引导脚本固定版本、拒覆盖、不用远程 pipe 执行。
func CheckBootstrap(root string) error {
	b, err := os.ReadFile(filepath.Join(root, "scripts", "bootstrap-machine.ps1"))
	if err != nil {
		return err
	}
	s := string(b)
	for _, must := range []string{"v2.0.0-beta.1", "Refusing to overwrite", "InstallCodexPlugin"} {
		if !strings.Contains(s, must) {
			return fmt.Errorf("bootstrap 缺少 %q", must)
		}
	}
	if regexp.MustCompile(`(?i)Invoke-Expression|\biex\b`).MatchString(s) {
		return fmt.Errorf("bootstrap 不应包含 Invoke-Expression/iex")
	}
	return nil
}

type hookFile struct {
	Hooks map[string][]struct {
		Matcher string `json:"matcher"`
		Hooks   []struct {
			Command        string `json:"command"`
			CommandWindows string `json:"commandWindows"`
		} `json:"hooks"`
	} `json:"hooks"`
}

// CheckCodexHooks 校验 Codex hook:Bash 匹配、含 PLUGIN_ROOT 与对应 --event。
func CheckCodexHooks(root string) error {
	b, err := os.ReadFile(filepath.Join(root, "pieces", "wfos-core", "hooks", "codex.hooks.json"))
	if err != nil {
		return err
	}
	var hf hookFile
	if err := json.Unmarshal(b, &hf); err != nil {
		return err
	}
	for _, event := range []string{"PreToolUse", "PermissionRequest"} {
		entries, ok := hf.Hooks[event]
		if !ok || len(entries) == 0 {
			return fmt.Errorf("codex hooks 缺 %s", event)
		}
		if entries[0].Matcher != "^Bash$" {
			return fmt.Errorf("%s matcher = %q, 期望 ^Bash$", event, entries[0].Matcher)
		}
		if len(entries[0].Hooks) == 0 {
			return fmt.Errorf("%s 无 handler", event)
		}
		h := entries[0].Hooks[0]
		if !strings.Contains(h.Command, "${PLUGIN_ROOT}") || !strings.Contains(h.Command, "--event="+event) {
			return fmt.Errorf("%s command 不含 ${PLUGIN_ROOT} 或 --event=%s:%q", event, event, h.Command)
		}
		if !strings.Contains(h.CommandWindows, "$env:PLUGIN_ROOT") || !strings.Contains(h.CommandWindows, "--event="+event) {
			return fmt.Errorf("%s commandWindows 不含 $env:PLUGIN_ROOT 或 --event=%s:%q", event, event, h.CommandWindows)
		}
	}
	return nil
}

type claudeMkt struct {
	Plugins []struct {
		Name    string `json:"name"`
		Source  string `json:"source"`
		Version string `json:"version"`
	} `json:"plugins"`
}

type codexMkt struct {
	Plugins []struct {
		Name   string `json:"name"`
		Source struct {
			Path string `json:"path"`
		} `json:"source"`
		Policy struct {
			Installation   string `json:"installation"`
			Authentication string `json:"authentication"`
		} `json:"policy"`
		Category string `json:"category"`
	} `json:"plugins"`
}

type manifest struct {
	Version string `json:"version"`
}

func readJSON(path string, v any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, v)
}

// CheckMarketplaces 校验两份市集清单与各 plugin.json 的一致性。
func CheckMarketplaces(root string) error {
	var claude claudeMkt
	if err := readJSON(filepath.Join(root, ".claude-plugin", "marketplace.json"), &claude); err != nil {
		return err
	}
	var codex codexMkt
	if err := readJSON(filepath.Join(root, ".agents", "plugins", "marketplace.json"), &codex); err != nil {
		return err
	}

	claudeNames := make([]string, len(claude.Plugins))
	for i, p := range claude.Plugins {
		claudeNames[i] = p.Name
	}
	codexNames := make([]string, len(codex.Plugins))
	for i, p := range codex.Plugins {
		codexNames[i] = p.Name
	}
	sort.Strings(claudeNames)
	sort.Strings(codexNames)
	if strings.Join(claudeNames, ",") != strings.Join(codexNames, ",") {
		return fmt.Errorf("两市集拼图名不一致:%v vs %v", claudeNames, codexNames)
	}

	for _, entry := range claude.Plugins {
		var cm manifest
		if err := readJSON(filepath.Join(root, entry.Source, ".claude-plugin", "plugin.json"), &cm); err != nil {
			return err
		}
		if cm.Version != entry.Version {
			return fmt.Errorf("%s claude plugin.json 版本漂移:%s != %s", entry.Name, cm.Version, entry.Version)
		}
		var xm manifest
		if err := readJSON(filepath.Join(root, entry.Source, ".codex-plugin", "plugin.json"), &xm); err != nil {
			return err
		}
		if xm.Version != entry.Version {
			return fmt.Errorf("%s codex plugin.json 版本漂移:%s != %s", entry.Name, xm.Version, entry.Version)
		}

		found := false
		for _, ce := range codex.Plugins {
			if ce.Name != entry.Name {
				continue
			}
			found = true
			if ce.Policy.Installation != "AVAILABLE" {
				return fmt.Errorf("%s codex installation != AVAILABLE", entry.Name)
			}
			if ce.Policy.Authentication != "ON_INSTALL" {
				return fmt.Errorf("%s codex authentication != ON_INSTALL", entry.Name)
			}
			if ce.Category == "" {
				return fmt.Errorf("%s codex category 为空", entry.Name)
			}
			if ce.Source.Path != entry.Source {
				return fmt.Errorf("%s 两市集 source 路径漂移:%s != %s", entry.Name, ce.Source.Path, entry.Source)
			}
		}
		if !found {
			return fmt.Errorf("codex 市集缺 %s", entry.Name)
		}
	}
	return nil
}
