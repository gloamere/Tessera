// Package initproject 实现 `tessera init`:为项目补齐 Tessera 骨架文件,
// 只补缺、不覆盖已有内容。从 scripts/init-project.mjs 移植。
package initproject

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const (
	start = "<!-- tessera:v2:start -->"
	end   = "<!-- tessera:v2:end -->"
)

// Options 是 init 的解析后参数。
type Options struct {
	Target string
	Name   string
	DryRun bool
	Help   bool
	hasTgt bool
	hasNm  bool
}

// Parse 复刻 mjs 的参数解析:--k=v、--k v、--k(布尔)。
func Parse(args []string) Options {
	var o Options
	for i := 0; i < len(args); i++ {
		tok := args[i]
		if !strings.HasPrefix(tok, "--") {
			continue
		}
		key, inline, hasInline := strings.Cut(tok[2:], "=")
		val := ""
		isBool := true
		switch {
		case hasInline:
			val, isBool = inline, false
		case i+1 < len(args) && !strings.HasPrefix(args[i+1], "--"):
			val, isBool = args[i+1], false
			i++
		}
		switch key {
		case "target":
			o.Target, o.hasTgt = val, true
			_ = isBool
		case "name":
			o.Name, o.hasNm = val, true
		case "dry-run":
			o.DryRun = true
		case "help":
			o.Help = true
		}
	}
	return o
}

func managedGuidance() string {
	return start + `
# Tessera v2

- 方向性 UI、数值、活动与技术选型先写入 ` + "`docs/decisions/`" + `,负责人确认后才能实施。
- 调研、策划和实现可并行;同一文件或存在依赖的任务不可并行修改。
- 使用已安装的 ` + "`tessera-core`" + ` skill 路由能力;不可逆命令仍受 Codex/Claude 原生权限约束。
- 运行 ` + "`tessera init`" + ` 只补缺,不覆盖此项目的人类规则。
` + end + "\n"
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func copyMissing(path, content string, dryRun bool, changes *[]string) error {
	if exists(path) {
		*changes = append(*changes, "skip    "+path)
		return nil
	}
	*changes = append(*changes, "create  "+path)
	if dryRun {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(content), 0o644)
}

func installGuidance(path string, dryRun bool, changes *[]string) error {
	block := managedGuidance()
	if !exists(path) {
		*changes = append(*changes, "create  "+path)
		if !dryRun {
			return os.WriteFile(path, []byte(block), 0o644)
		}
		return nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	current := string(raw)
	s := strings.Index(current, start)
	e := strings.Index(current, end)
	if (s >= 0) != (e >= 0) || (s >= 0 && e < s) {
		return fmt.Errorf("托管区标记损坏,拒绝修改:%s", path)
	}
	if s >= 0 {
		next := current[:s] + block + current[e+len(end):]
		if next != current {
			*changes = append(*changes, "update  "+path+" (managed block)")
			if !dryRun {
				return os.WriteFile(path, []byte(next), 0o644)
			}
		}
		return nil
	}
	*changes = append(*changes, "append  "+path+" (managed block)")
	if !dryRun {
		sep := "\n\n"
		if strings.HasSuffix(current, "\n") {
			sep = "\n"
		}
		return os.WriteFile(path, []byte(current+sep+block), 0o644)
	}
	return nil
}

// Run 执行初始化,返回退出码。
func Run(args []string, out io.Writer) int {
	o := Parse(args)
	if o.Help || !o.hasTgt || o.Target == "" {
		fmt.Fprintln(out, "Usage: tessera init --target <project-path> [--name <name>] [--dry-run]")
		if o.Help {
			return 0
		}
		return 1
	}
	root, err := filepath.Abs(o.Target)
	if err != nil {
		fmt.Fprintln(out, "tessera init: "+err.Error())
		return 1
	}
	name := o.Name
	if !o.hasNm || name == "" {
		name = filepath.Base(root)
	}
	nameJSON, _ := json.Marshal(name)
	stamp := time.Now().UTC().Format("2006-01-02T15:04:05.000") + "Z"

	var changes []string
	files := []struct{ rel, content string }{
		{".tessera/project.yaml", fmt.Sprintf("schema: tessera/project@2\nname: %s\ninitialized_at: %q\n", nameJSON, stamp)},
		{"docs/PROJECT.md", fmt.Sprintf("# %s\n\n## 目标\n\n- \n\n## 约束\n\n- \n", name)},
		{"docs/NOW.md", "# 当前状态\n\n- \n"},
		{"docs/INBOX.md", "# 收集箱\n\n- \n"},
		{"docs/decisions/README.md", "# 决策\n\n方向性决策在确认前保持 pending。\n"},
		{"docs/research/README.md", "# 调研\n\n研究结论应保留来源与不确定性。\n"},
	}
	for _, f := range files {
		if err := copyMissing(filepath.Join(root, f.rel), f.content, o.DryRun, &changes); err != nil {
			fmt.Fprintln(out, "tessera init: "+err.Error())
			return 1
		}
	}
	if err := installGuidance(filepath.Join(root, "AGENTS.md"), o.DryRun, &changes); err != nil {
		fmt.Fprintln(out, "tessera init: "+err.Error())
		return 1
	}

	verb := "Initialized"
	if o.DryRun {
		verb = "Preview"
	}
	fmt.Fprintf(out, "%s Tessera project: %s\n", verb, root)
	for _, c := range changes {
		fmt.Fprintln(out, c)
	}
	return 0
}
