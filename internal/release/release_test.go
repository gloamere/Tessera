package release

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestAssetName(t *testing.T) {
	if got := AssetName("windows", "amd64"); got != "tessera-windows-amd64.exe" {
		t.Errorf("windows = %q", got)
	}
	if got := AssetName("linux", "arm64"); got != "tessera-linux-arm64" {
		t.Errorf("linux = %q", got)
	}
}

func TestParseChecksum(t *testing.T) {
	text := "aaaa  tessera-linux-amd64\nbbbb  tessera-windows-amd64.exe\n"
	if got := ParseChecksum(text, "tessera-windows-amd64.exe"); got != "bbbb" {
		t.Errorf("got %q", got)
	}
	if got := ParseChecksum(text, "nope"); got != "" {
		t.Errorf("缺失应返回空,得 %q", got)
	}
}

// 用 httptest 起一个假 release 源,验证下载+校验+落地全链路。
func TestFetchVerifiesAndWrites(t *testing.T) {
	asset := AssetName(runtime.GOOS, runtime.GOARCH)
	payload := []byte("fake-tessera-binary-bytes")
	sum := sha256.Sum256(payload)
	checksums := fmt.Sprintf("%s  %s\n", hex.EncodeToString(sum[:]), asset)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/v1/checksums.txt":
			_, _ = w.Write([]byte(checksums))
		case r.URL.Path == "/v1/"+asset:
			_, _ = w.Write(payload)
		default:
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "bin", "tessera")
	if err := Fetch(srv.URL, "v1", runtime.GOOS, runtime.GOARCH, dest); err != nil {
		t.Fatalf("Fetch: %v", err)
	}
	got, _ := os.ReadFile(dest)
	if string(got) != string(payload) {
		t.Errorf("落地内容不符:%q", got)
	}
}

func TestLatestVersion(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/repos/gloamere/workflow-os/releases/latest" {
			_, _ = w.Write([]byte(`{"tag_name":"v2.0.0-beta.9","name":"x"}`))
			return
		}
		w.WriteHeader(404)
	}))
	defer srv.Close()
	v, err := LatestVersion(srv.URL, "gloamere/workflow-os")
	if err != nil {
		t.Fatalf("LatestVersion: %v", err)
	}
	if v != "v2.0.0-beta.9" {
		t.Errorf("got %q", v)
	}
}

func TestFetchRejectsBadChecksum(t *testing.T) {
	asset := AssetName(runtime.GOOS, runtime.GOARCH)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/v1/checksums.txt":
			_, _ = w.Write([]byte("deadbeef  " + asset + "\n")) // 故意错的哈希
		default:
			_, _ = w.Write([]byte("whatever"))
		}
	}))
	defer srv.Close()

	dest := filepath.Join(t.TempDir(), "tessera")
	if err := Fetch(srv.URL, "v1", runtime.GOOS, runtime.GOARCH, dest); err == nil {
		t.Error("校验不匹配应报错")
	}
	if _, err := os.Stat(dest); err == nil {
		t.Error("校验失败不应落地文件")
	}
}
