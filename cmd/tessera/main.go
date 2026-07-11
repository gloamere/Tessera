// Command tessera 是 Tessera 的单二进制 CLI。
// 子命令:init、setup、doctor、piece、update、version。
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"tessera/internal/doctor"
	"tessera/internal/initproject"
	"tessera/internal/piece"
	"tessera/internal/release"
	"tessera/internal/setup"
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
	case "doctor":
		os.Exit(runDoctor())
	case "piece":
		os.Exit(runPiece(rest))
	case "init":
		os.Exit(initproject.Run(rest, os.Stdout))
	case "setup":
		os.Exit(runSetup(rest))
	case "update":
		os.Exit(runUpdate(rest))
	case "version", "--version", "-v":
		fmt.Println("tessera " + version)
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
  tessera init --target <path> [--name <n>] [--dry-run]  为项目补齐骨架(只补缺)
  tessera setup [--root <path>] [--register] [--codex]   安装:注册能力市集(默认 dry-run)
  tessera doctor                                         仓库/安装环境体检
  tessera piece list                                     列出拼图与外部依赖
  tessera update [--version <tag>] [--root <path>]       下载校验并替换二进制(默认 latest)
  tessera version                                        打印版本
`)
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

// ---- setup ----

func runSetup(args []string) int {
	opts := setup.Options{}
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--register":
			opts.Register = true
		case "--codex":
			opts.Codex = true
		case "--root":
			if i+1 < len(args) {
				opts.Root = args[i+1]
				i++
			}
		default:
			if r, ok := cutFlag(args[i], "--root="); ok {
				opts.Root = r
			}
		}
	}
	return setup.Run(opts, os.Stdout)
}

func cutFlag(arg, prefix string) (string, bool) {
	if strings.HasPrefix(arg, prefix) {
		return strings.TrimPrefix(arg, prefix), true
	}
	return "", false
}

// ---- update ----

func runUpdate(args []string) int {
	version, root, base := "", "", release.DefaultBase
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--version":
			if i+1 < len(args) {
				version = args[i+1]
				i++
			}
		case "--root":
			if i+1 < len(args) {
				root = args[i+1]
				i++
			}
		case "--base":
			if i+1 < len(args) {
				base = args[i+1]
				i++
			}
		default:
			if v, ok := cutFlag(args[i], "--version="); ok {
				version = v
			}
			if r, ok := cutFlag(args[i], "--root="); ok {
				root = r
			}
			if b, ok := cutFlag(args[i], "--base="); ok {
				base = b
			}
		}
	}
	if root == "" {
		root = repoRoot()
	}
	if version == "" {
		v, err := release.LatestVersion(release.DefaultAPIBase, release.Repo)
		if err != nil {
			fmt.Fprintln(os.Stderr, "tessera update:无法解析 latest(用 --version 指定):"+err.Error())
			return 1
		}
		version = v
	}
	dest := filepath.Join(root, "pieces", "tessera-core", "bin", binaryName())
	fmt.Printf("下载 %s(%s/%s)→ %s\n", version, runtime.GOOS, runtime.GOARCH, dest)
	if err := release.Fetch(base, version, runtime.GOOS, runtime.GOARCH, dest); err != nil {
		fmt.Fprintln(os.Stderr, "tessera update:"+err.Error())
		return 1
	}
	fmt.Println("✓ 已下载、校验并替换二进制")
	return 0
}

func binaryName() string {
	if runtime.GOOS == "windows" {
		return "tessera.exe"
	}
	return "tessera"
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
	if p := os.Getenv("TESSERA_ROOT"); p != "" {
		return p
	}
	wd, err := os.Getwd()
	if err != nil {
		return "."
	}
	return wd
}
