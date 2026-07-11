package gate

import (
	"encoding/json"
	"strings"
	"testing"
)

func assertContains(t *testing.T, s, sub string) {
	t.Helper()
	if !strings.Contains(s, sub) {
		t.Errorf("output %q does not contain %q", s, sub)
	}
}

// assertJSONField 解析 out 后按点分路径取字符串字段并比对。
func assertJSONField(t *testing.T, out, path, want string) {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal([]byte(out), &m); err != nil {
		t.Fatalf("invalid JSON %q: %v", out, err)
	}
	var cur any = m
	for _, k := range strings.Split(path, ".") {
		obj, ok := cur.(map[string]any)
		if !ok {
			t.Fatalf("path %q: %q is not an object", path, k)
		}
		cur = obj[k]
	}
	got, ok := cur.(string)
	if !ok {
		t.Fatalf("path %q: not a string (%T)", path, cur)
	}
	if got != want {
		t.Errorf("path %q = %q, want %q", path, got, want)
	}
}
