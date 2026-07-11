# Tessera 门二进制构建(mac/linux/CI 用;Windows 用 scripts/build-gate.ps1)。
# 零 CGO,纯 Go 交叉编译。

BINARY   := tessera
PKG      := ./cmd/tessera
PIECEBIN := pieces/tessera-core/bin
DIST     := dist
VERSION  ?= 2.0.0-beta.1
LDFLAGS  := -ldflags "-X main.version=$(VERSION)"
export GOTOOLCHAIN := local

PLATFORMS := windows/amd64 windows/arm64 darwin/amd64 darwin/arm64 linux/amd64 linux/arm64

.PHONY: build test vet dist checksums clean

## build: 构建本机二进制到 pieces/tessera-core/bin/
build:
	@mkdir -p $(PIECEBIN)
	go build $(LDFLAGS) -o $(PIECEBIN)/$(BINARY) $(PKG)
	@echo "built -> $(PIECEBIN)/$(BINARY)"

## test: 跑全部 Go 测试
test:
	go test ./...

## vet: 静态检查
vet:
	go vet ./...

## dist: 交叉编译全平台到 dist/
dist:
	@mkdir -p $(DIST)
	@for p in $(PLATFORMS); do \
	  os=$${p%/*}; arch=$${p#*/}; ext=; [ "$$os" = windows ] && ext=.exe; \
	  GOOS=$$os GOARCH=$$arch go build $(LDFLAGS) -o $(DIST)/$(BINARY)-$$os-$$arch$$ext $(PKG) \
	    && echo "built $$os/$$arch" || exit 1; \
	done

## checksums: 生成 dist/checksums.txt
checksums: dist
	cd $(DIST) && sha256sum $(BINARY)-* > checksums.txt && echo "checksums -> $(DIST)/checksums.txt"

## clean: 清理构建产物
clean:
	rm -rf $(DIST) $(PIECEBIN)
