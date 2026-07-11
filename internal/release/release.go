// Package release 从 GitHub Releases(或任意兼容 base)下载指定版本、
// 当前平台的门二进制并做 sha256 校验。零第三方依赖。
package release

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// DefaultBase 是 GitHub Releases 资产下载基址(本机实测 objects.githubusercontent.com 可达)。
const DefaultBase = "https://github.com/gloamere/workflow-os/releases/download"

// DefaultAPIBase / Repo 用于解析 latest 版本(本机实测 api.github.com 可达)。
const (
	DefaultAPIBase = "https://api.github.com"
	Repo           = "gloamere/workflow-os"
)

// LatestVersion 查询最新 release 的 tag_name。
func LatestVersion(apiBase, repo string) (string, error) {
	data, err := httpGet(strings.TrimRight(apiBase, "/") + "/repos/" + repo + "/releases/latest")
	if err != nil {
		return "", err
	}
	var r struct {
		TagName string `json:"tag_name"`
	}
	if err := json.Unmarshal(data, &r); err != nil {
		return "", err
	}
	if r.TagName == "" {
		return "", fmt.Errorf("release 无 tag_name")
	}
	return r.TagName, nil
}

// AssetName 返回某平台的二进制资产名。
func AssetName(goos, goarch string) string {
	name := "tessera-" + goos + "-" + goarch
	if goos == "windows" {
		name += ".exe"
	}
	return name
}

// ParseChecksum 从 sha256sum 输出("<hex>  <file>")里取指定文件的期望哈希。
func ParseChecksum(text, asset string) string {
	for _, line := range strings.Split(text, "\n") {
		fields := strings.Fields(line)
		if len(fields) == 2 && fields[1] == asset {
			return strings.ToLower(fields[0])
		}
	}
	return ""
}

func httpGet(url string) ([]byte, error) {
	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("下载 %s 失败:HTTP %d", url, resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

// Fetch 下载 <base>/<version>/tessera-<os>-<arch>,按同目录 checksums.txt 校验,
// 原子写入 dest 并置可执行位。校验失败即中止,不落地。
func Fetch(base, version, goos, goarch, dest string) error {
	asset := AssetName(goos, goarch)
	prefix := strings.TrimRight(base, "/") + "/" + version + "/"

	sums, err := httpGet(prefix + "checksums.txt")
	if err != nil {
		return err
	}
	want := ParseChecksum(string(sums), asset)
	if want == "" {
		return fmt.Errorf("checksums.txt 中无 %s 条目", asset)
	}

	data, err := httpGet(prefix + asset)
	if err != nil {
		return err
	}
	sum := sha256.Sum256(data)
	if got := hex.EncodeToString(sum[:]); got != want {
		return fmt.Errorf("%s 校验不匹配:期望 %s,实得 %s", asset, want, got)
	}

	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return err
	}
	tmp := dest + ".new"
	if err := os.WriteFile(tmp, data, 0o755); err != nil {
		return err
	}
	// Windows 下无法覆盖运行中的 exe:先把旧的挪开(允许),再落新文件。
	if _, err := os.Stat(dest); err == nil {
		_ = os.Remove(dest + ".old")
		if err := os.Rename(dest, dest+".old"); err != nil {
			return err
		}
	}
	if err := os.Rename(tmp, dest); err != nil {
		return err
	}
	_ = os.Chmod(dest, 0o755)
	return nil
}
