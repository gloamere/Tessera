// Command tessera 是 workflow-os(改名中:Tessera)的单二进制 CLI。
// 子命令:gate(hook 入口)、selftest、doctor、piece、version。
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"tessera/internal/doctor"
	"tessera/internal/gate"
	"tessera/internal/initproject"
	"tessera/internal/piece"
	"tessera/internal/selftest"
)

// version 可在构建时用 -ldflags "-X main.version=vX" 覆盖。
var version = "2.0.0-beta.1"

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		printHelp()
		os.Exit(0)
	}
	sub, rest := args[0], args[1:]
	switch sub {
	case "gate":
		os.Exit(runGate(rest))
	case "selftest":
		os.Exit(runSelftest())
	case "doctor":
		os.Exit(runDoctor())
	case "piece":
		os.Exit(runPiece(rest))
	case "init":
		os.Exit(initproject.Run(rest, os.Stdout))
	case "version", "--version", "-v":
		fmt.Println("tessera " + version)
	case "setup", "update":
		fmt.Fprintln(os.Stderr, "tessera "+sub+":新机安装/升级流程属 M4,尚未实现。")
		os.Exit(2)
	case "help", "--help", "-h":
		printHelp()
	default:
		fmt.Fprintln(os.Stderr, "未知子命令:"+sub)
		printHelp()
		os.Exit(2)
	}
}

func printHelp() {
	fmt.Print(`tessera ` + version + ` — 能力操作系统单二进制 CLI

用法:
  tessera gate --platform=claude|codex [--event=NAME]   hook 入口(读 stdin payload,输出裁决)
  tessera selftest                                       跑内置门断言
  tessera doctor                                         仓库/安装环境体检
  tessera piece list                                     列出拼图与外部依赖
  tessera init --target <path> [--name <n>] [--dry-run]  为项目补齐骨架(只补缺)
  tessera version                                        打印版本
  tessera setup | update                                 (M4 待实现)
`)
}

// ---- gate:hook 入口,契约与旧 gate.mjs 逐字节等价 ----

func runGate(args []string) int {
	raw, _ := io.ReadAll(os.Stdin)

	if os.Getenv("WFOS_GATE_DEBUG") == "1" {
		if home, err := os.UserHomeDir(); err == nil {
			dir := filepath.Join(home, ".workflow-os")
			if os.MkdirAll(dir, 0o755) == nil {
				line := time.Now().UTC().Format(time.RFC3339) + " " + string(raw) + "\n"
				if f, err := os.OpenFile(filepath.Join(dir, "gate-debug.log"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644); err == nil {
					_, _ = f.WriteString(line)
					_ = f.Close()
				}
			}
		}
	}

	platform := "claude"
	event := "PreToolUse"
	for _, a := range args {
		if a == "--platform=codex" {
			platform = "codex"
		}
		if strings.HasPrefix(a, "--event=") {
			event = strings.TrimPrefix(a, "--event=")
		}
	}

	rules, err := gate.LoadRules(rulesPath())
	if err != nil {
		return 0 // fail-open
	}
	var payload map[string]any
	if err := json.Unmarshal(raw, &payload); err != nil {
		return 0 // fail-open
	}
	command := gate.ExtractCommand(payload)
	if command == "" {
		return 0
	}
	if out, emit := gate.Decide(gate.MatchCommand(command, rules), platform, event); emit {
		fmt.Print(out)
	}
	return 0
}

// rulesPath:env 覆盖 > 二进制同目录 > 二进制上级目录。
func rulesPath() string {
	if p := os.Getenv("WFOS_GATE_RULES"); p != "" {
		return p
	}
	exe, err := os.Executable()
	if err != nil {
		return "gate-rules.json"
	}
	dir := filepath.Dir(exe)
	for _, p := range []string{
		filepath.Join(dir, "gate-rules.json"),
		filepath.Join(dir, "..", "gate-rules.json"),
	} {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return filepath.Join(dir, "gate-rules.json")
}

// ---- selftest ----

func runSelftest() int {
	rules, err := gate.LoadRules(repoRulesPath())
	if err != nil {
		fmt.Fprintln(os.Stderr, "selftest:无法加载规则:"+err.Error())
		return 1
	}
	results := selftest.Run(rules)
	for _, r := range results {
		mark := "✓"
		if !r.Pass {
			mark = "✗"
		}
		want := r.Want
		if want == "" {
			want = "(放行)"
		}
		got := r.Got
		if got == "" {
			got = "(放行)"
		}
		if r.Pass {
			fmt.Printf("%s %-40s → %s\n", mark, r.Command, got)
		} else {
			fmt.Printf("%s %-40s → 期望 %s,实得 %s\n", mark, r.Command, want, got)
		}
	}
	if selftest.AllPass(results) {
		fmt.Printf("\n%d/%d 断言通过\n", len(results), len(results))
		return 0
	}
	pass := 0
	for _, r := range results {
		if r.Pass {
			pass++
		}
	}
	fmt.Printf("\n%d/%d 断言通过 — 有失败\n", pass, len(results))
	return 1
}

// ---- doctor ----

func runDoctor() int {
	root := repoRoot()
	checks := doctor.Run(root)
	for _, c := range checks {
		mark := "✓"
		if !c.OK {
			mark = "✗"
		}
		fmt.Printf("%s %-16s %s\n", mark, c.Name, c.Detail)
	}
	if doctor.AllOK(checks) {
		fmt.Println("\n体检通过")
		return 0
	}
	fmt.Println("\n体检发现问题")
	return 1
}

// ---- piece ----

func runPiece(args []string) int {
	if len(args) == 0 || args[0] != "list" {
		fmt.Fprintln(os.Stderr, "用法:tessera piece list")
		return 2
	}
	pieces, err := piece.List(repoRoot())
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

// ---- 根目录解析 ----

func repoRoot() string {
	if p := os.Getenv("WFOS_ROOT"); p != "" {
		return p
	}
	wd, err := os.Getwd()
	if err != nil {
		return "."
	}
	return wd
}

func repoRulesPath() string {
	if p := os.Getenv("WFOS_GATE_RULES"); p != "" {
		return p
	}
	return filepath.Join(repoRoot(), "pieces", "wfos-core", "gate-rules.json")
}
