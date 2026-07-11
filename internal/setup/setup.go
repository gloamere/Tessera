// Package setup 实现 `tessera setup`:注册能力市集。
// 默认 dry-run(只打印计划);--register 才真正执行注册。跨平台。
package setup

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

// Options 是 setup 参数。
type Options struct {
	Root     string // 安装/仓库根(含 pieces/);空则用 cwd
	Register bool   // 实际执行市集注册;默认只打印
	Codex    bool   // 一并注册 Codex
}

// Plan 是探测得到的执行计划(纯数据,不含外部副作用)。
type Plan struct {
	OS, Arch    string
	Root        string
	Marketplace []string // 将执行/打印的注册命令
}

// BuildPlan 探测环境并组装计划,不执行任何外部命令。
func BuildPlan(opts Options) (Plan, error) {
	root := opts.Root
	if root == "" {
		wd, err := os.Getwd()
		if err != nil {
			return Plan{}, err
		}
		root = wd
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		return Plan{}, err
	}
	root = abs

	if _, err := os.Stat(filepath.Join(root, "pieces")); err != nil {
		return Plan{}, fmt.Errorf("未在 %s 找到 pieces/(用 --root 指定仓库根)", root)
	}

	p := Plan{OS: runtime.GOOS, Arch: runtime.GOARCH, Root: root}
	p.Marketplace = []string{"claude plugin marketplace add " + root}
	if opts.Codex {
		p.Marketplace = append(p.Marketplace, "codex plugin marketplace add "+root)
	}
	return p, nil
}

// Run 组装并渲染计划;register 为真时执行市集注册。返回退出码。
func Run(opts Options, w io.Writer) int {
	plan, err := BuildPlan(opts)
	if err != nil {
		fmt.Fprintln(w, "tessera setup: "+err.Error())
		return 1
	}

	fmt.Fprintf(w, "① 平台      %s/%s\n", plan.OS, plan.Arch)
	fmt.Fprintf(w, "② 安装根    %s\n", plan.Root)
	fmt.Fprintln(w, "③ 市集注册")
	for _, c := range plan.Marketplace {
		if opts.Register {
			fmt.Fprintf(w, "   执行:%s\n", c)
			if code := execShell(w, c); code != 0 {
				fmt.Fprintf(w, "   ⚠ 命令退出码 %d\n", code)
			}
		} else {
			fmt.Fprintf(w, "   (dry-run)%s\n", c)
		}
	}

	if !opts.Register {
		fmt.Fprintln(w, "\n默认 dry-run。确认无误后加 --register 执行市集注册(可加 --codex 一并注册 Codex)。")
	}
	return 0
}

// execShell 通过平台默认 shell 执行一条命令,输出透传。
func execShell(w io.Writer, command string) int {
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("cmd", "/c", command)
	} else {
		cmd = exec.Command("sh", "-c", command)
	}
	cmd.Stdout = w
	cmd.Stderr = w
	if err := cmd.Run(); err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return ee.ExitCode()
		}
		return 1
	}
	return 0
}
