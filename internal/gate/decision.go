package gate

import (
	"bytes"
	"encoding/json"
)

// Reason 复刻 gate.mjs 的裁决文案(逐字节等价:半角括号、全角句号)。
func Reason(r *Rule) string {
	return "[Tessera 门] " + r.Description + "(规则 " + r.ID + ")。请确认后再执行。"
}

// Decide 依据平台与事件类型渲染 hook 输出。
// emit 为 false 时不产生任何 stdout(交平台原生审批)。
func Decide(match *Rule, platform, event string) (output string, emit bool) {
	if match == nil {
		return "", false
	}
	reason := Reason(match)
	action := match.Action(platform)

	switch {
	case platform == "claude" && (action == "ask" || action == "deny"):
		return marshal(map[string]any{
			"hookSpecificOutput": ordered(
				"hookEventName", "PreToolUse",
				"permissionDecision", action,
				"permissionDecisionReason", reason,
			),
		}), true
	case platform == "codex" && action == "deny":
		if event == "PermissionRequest" {
			return marshal(map[string]any{
				"hookSpecificOutput": ordered(
					"hookEventName", "PermissionRequest",
					"decision", ordered("behavior", "deny", "message", reason),
				),
			}), true
		}
		return marshal(map[string]any{
			"hookSpecificOutput": ordered(
				"hookEventName", "PreToolUse",
				"permissionDecision", "deny",
				"permissionDecisionReason", reason,
			),
		}), true
	default:
		// codex 'native' 或其它:不裁决 → 原生审批。
		return "", false
	}
}

// orderedMap 是保持插入顺序的键值对,用于产出与 gate.mjs 相同字段序的 JSON。
type orderedMap struct {
	keys []string
	vals map[string]any
}

func ordered(kv ...any) *orderedMap {
	m := &orderedMap{vals: map[string]any{}}
	for i := 0; i+1 < len(kv); i += 2 {
		k := kv[i].(string)
		m.keys = append(m.keys, k)
		m.vals[k] = kv[i+1]
	}
	return m
}

func (m *orderedMap) MarshalJSON() ([]byte, error) {
	var buf bytes.Buffer
	buf.WriteByte('{')
	for i, k := range m.keys {
		if i > 0 {
			buf.WriteByte(',')
		}
		kb, _ := json.Marshal(k)
		buf.Write(kb)
		buf.WriteByte(':')
		vb, err := marshalRaw(m.vals[k])
		if err != nil {
			return nil, err
		}
		buf.Write(vb)
	}
	buf.WriteByte('}')
	return buf.Bytes(), nil
}

func marshalRaw(v any) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

func marshal(v any) string {
	b, err := marshalRaw(v)
	if err != nil {
		return ""
	}
	return string(b)
}
