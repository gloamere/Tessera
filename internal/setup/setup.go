// Package setup 实现 `tessera setup`:新机/新装的六阶段流程。
// 默认 dry-run(只打印计划);--register 才真正执行市集注册。跨平台。
package setup

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"

	"tessera/internal/gate"
	"tessera/internal/selftest"
)

// Options 是 setup 参数。
type Options struct {
	Root     string // 安装/仓库根(含 pieces/);空则用 cwd
	Register bool   // 实际执行市集注册;默认只打印
	Codex    bool   // 一并注册 Codex
}

// Plan 是探测得到的执行计划(纯数据,不含外部副作用)。
type Plan struct {
	OS, Arch      string
	Root          string
	BinaryPath    string
	BinaryPresent bool
	Selftest      []selftest.Result
	SelftestOK    bool
	Marketplace   []string // 将执行/打印的注册命令
	HookCommands  []string // 信任复核:将由 hook 运行的命令
}

func binaryName() string {
	if runtime.GOOS == "windows" {
		return "tessera.exe"
	}
	return "tessera"
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

	p.BinaryPath = filepath.Join(root, "pieces", "wfos-core", "bin", binaryName())
	_, err = os.Stat(p.BinaryPath)
	p.BinaryPresent = err == nil

	if rules, err := gate.LoadRules(filepath.Join(root, "pieces", "wfos-core", "gate-rules.json")); err == nil {
		p.Selftest = selftest.Run(rules)
		p.SelftestOK = selftest.AllPass(p.Selftest)
	}

	p.Marketplace = []string{"claude plugin marketplace add " + root}
	if opts.Codex {
		p.Marketplace = append(p.Marketplace, "codex plugin marketplace add "+root)
	}

	p.HookCommands = readHookCommands(root)
	return p, nil
}

type hookFile struct {
	Hooks map[string][]struct {
		Hooks []struct {
			Command        string `json:"command"`
			CommandWindows string `json:"commandWindows"`
		} `json:"hooks"`
	} `json:"hooks"`
}

func readHookCommands(root string) []string {
	var cmds []string
	for _, rel := range []string{
		filepath.Join("pieces", "wfos-core", "hooks", "hooks.json"),
		filepath.Join("pieces", "wfos-core", "hooks", "codex.hooks.json"),
	} {
		data, err := os.ReadFile(filepath.Join(root, rel))
		if err != nil {
			continue
		}
		var hf hookFile
		if json.Unmarshal(data, &hf) != nil {
			continue
		}
		for _, entries := range hf.Hooks {
			for _, e := range entries {
				for _, h := range e.Hooks {
					if h.Command != "" {
						cmds = append(cmds, h.Command)
					}
					if h.CommandWindows != "" {
						cmds = append(cmds, h.CommandWindows)
					}
				}
			}
		}
	}
	return cmds
}

// Run 组装并渲染计划;register 为真时执行市集注册。返回退出码。
func Run(opts Options, w io.Writer) int {
	plan, err := BuildPlan(opts)
	if err != nil {
		fmt.Fprintln(w, "tessera setup: "+err.Error())
		return 1
	}

	fmt.Fprintf(w, "① 平台        %s/%s\n", plan.OS, plan.Arch)
	fmt.Fprintf(w, "② 安装根      %s\n", plan.Root)

	mark := "✗ 缺失(需 make build / build-gate.ps1 / M3 分发)"
	if plan.BinaryPresent {
		mark = "✓ " + plan.BinaryPath
	}
	fmt.Fprintf(w, "③ 门二进制    %s\n", mark)

	pass := 0
	for _, r := range plan.Selftest {
		if r.Pass {
			pass++
		}
	}
	stMark := "✓"
	if !plan.SelftestOK {
		stMark = "✗"
	}
	fmt.Fprintf(w, "④ 门自检      %s %d/%d 断言\n", stMark, pass, len(plan.Selftest))

	fmt.Fprintln(w, "⑤ 市集注册")
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

	fmt.Fprintln(w, "⑥ 信任复核(以下命令将由 hook 在每次工具调用时运行,审阅后再决定是否信任)")
	if len(plan.HookCommands) == 0 {
		fmt.Fprintln(w, "   (未找到 hook 配置)")
	}
	for _, c := range plan.HookCommands {
		fmt.Fprintf(w, "   • %s\n", c)
	}

	if !opts.Register {
		fmt.Fprintln(w, "\n默认 dry-run。确认无误后加 --register 执行市集注册(可加 --codex 一并注册 Codex)。")
	}
	if !plan.BinaryPresent {
		fmt.Fprintln(w, "注意:门二进制缺失时 hook 会 fail-open(门失效)。先构建二进制再注册。")
		return 1
	}
	if !plan.SelftestOK {
		return 1
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
