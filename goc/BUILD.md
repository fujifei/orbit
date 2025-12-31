# Goc 构建指南

## 前置要求

- Go 1.13+ （开发goc需要Go 1.13+）
- 已安装Git

## 构建步骤

### 1. 进入goc项目目录

```bash
cd /Users/jifei.fu/project/qa/orbit/goc
```

### 2. 下载依赖

```bash
go mod download
```

或者使用：

```bash
go mod tidy
```

### 3. 构建可执行文件

#### 方式一：基本构建（推荐）

```bash
go build -o goc .
```

这会在当前目录生成 `goc` 可执行文件。

#### 方式二：指定输出路径

```bash
go build -o /usr/local/bin/goc .
```

或者：

```bash
go build -o ./bin/goc .
```

#### 方式三：使用Makefile（安装到GOPATH/bin）

```bash
make all
```

这会将goc安装到 `$GOPATH/bin` 或 `$HOME/go/bin` 目录。

#### 方式四：生产构建（禁用CGO，添加版本信息）

```bash
CGO_ENABLED=0 go build -ldflags "-X 'github.com/qiniu/goc/cmd.version=v1.0.0'" -o goc .
```

## 构建选项说明

### 基本选项

- `-o goc`: 指定输出文件名
- `.`: 构建当前目录（goc.go是主入口）

### 高级选项

- `CGO_ENABLED=0`: 禁用CGO，生成静态链接的可执行文件（适合跨平台分发）
- `-ldflags "-X 'github.com/qiniu/goc/cmd.version=v1.0.0'"`: 注入版本信息

### 交叉编译

如果需要为其他平台构建：

```bash
# Linux AMD64
GOOS=linux GOARCH=amd64 go build -o goc-linux-amd64 .

# macOS AMD64
GOOS=darwin GOARCH=amd64 go build -o goc-darwin-amd64 .

# macOS ARM64 (Apple Silicon)
GOOS=darwin GOARCH=arm64 go build -o goc-darwin-arm64 .

# Windows AMD64
GOOS=windows GOARCH=amd64 go build -o goc-windows-amd64.exe .
```

## 验证构建

构建完成后，可以验证可执行文件：

```bash
# 查看版本
./goc version

# 查看帮助
./goc --help

# 测试wrapper命令（需要RabbitMQ）
./goc wrapper --help
```

## 常见问题

### 1. 依赖下载失败

如果 `go mod download` 失败，可能是网络问题，可以：

```bash
# 设置Go代理（国内用户）
export GOPROXY=https://goproxy.cn,direct

# 或者使用官方代理
export GOPROXY=https://proxy.golang.org,direct
```

### 2. 构建失败：找不到包

确保已下载所有依赖：

```bash
go mod tidy
go mod download
```

### 3. 权限问题

如果安装到系统目录需要权限：

```bash
sudo go build -o /usr/local/bin/goc .
```

或者先构建到当前目录，再移动：

```bash
go build -o goc .
sudo mv goc /usr/local/bin/
```

## 快速构建脚本

可以创建一个简单的构建脚本 `build.sh`：

```bash
#!/bin/bash

set -e

echo "Building goc..."

# 下载依赖
echo "Downloading dependencies..."
go mod download

# 构建
echo "Building executable..."
go build -o goc .

echo "Build complete! Executable: ./goc"
echo "To install system-wide: sudo mv goc /usr/local/bin/"
```

使用：

```bash
chmod +x build.sh
./build.sh
```

## 完整构建流程示例

```bash
# 1. 进入项目目录
cd /Users/jifei.fu/project/qa/orbit/goc

# 2. 清理旧的构建文件（可选）
rm -f goc

# 3. 下载依赖
go mod download

# 4. 构建
go build -o goc .

# 5. 验证
./goc version

# 6. 安装到系统（可选）
sudo mv goc /usr/local/bin/
```

## 注意事项

1. **新依赖**: 由于我们添加了RabbitMQ依赖（`github.com/streadway/amqp`），首次构建前必须执行 `go mod download` 或 `go mod tidy`

2. **Go版本**: 确保使用Go 1.13+，可以通过 `go version` 检查

3. **模块模式**: 确保在项目根目录执行构建命令，因为 `go.mod` 文件在根目录

