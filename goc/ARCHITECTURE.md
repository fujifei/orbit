# Goc 架构分析文档

## 项目概述

**Goc** 是一个基于 Go 语言的综合代码覆盖率测试工具，特别适用于系统测试场景的代码覆盖率收集和精确测试。它支持运行时覆盖率收集，适用于长期运行的 Go 应用程序。

## 核心功能

1. **运行时覆盖率收集** - 对运行中的 Go 服务进行实时覆盖率统计
2. **服务注册中心** - 集中管理多个被测试服务的注册信息
3. **覆盖率数据聚合** - 支持多服务覆盖率数据合并
4. **覆盖率差异分析** - 基于 Pull Request 的覆盖率差异分析
5. **开发模式支持** - 支持精确测试的开发模式

## 项目结构

```
goc/
├── cmd/                    # CLI 命令入口
│   ├── root.go            # 根命令定义
│   ├── server.go          # 启动服务注册中心
│   ├── build.go           # 构建带覆盖率插桩的二进制
│   ├── install.go         # 安装命令
│   ├── run.go             # 运行命令
│   ├── profile.go         # 获取覆盖率数据
│   ├── list.go            # 列出注册的服务
│   ├── register.go        # 注册服务
│   ├── remove.go          # 移除服务
│   ├── clear.go           # 清空覆盖率计数器
│   ├── init.go            # 初始化系统
│   ├── merge.go           # 合并覆盖率文件
│   ├── diff.go            # 覆盖率差异分析
│   └── version.go         # 版本信息
│
├── pkg/                    # 核心功能包
│   ├── cover/             # 覆盖率核心模块
│   │   ├── server.go      # 服务注册中心实现
│   │   ├── client.go      # 客户端实现
│   │   ├── instrument.go  # 代码插桩逻辑
│   │   ├── cover.go       # 覆盖率处理
│   │   ├── store.go       # 服务存储（文件/内存）
│   │   ├── delta.go       # 覆盖率差异计算
│   │   └── internal/      # 内部工具
│   │
│   ├── build/             # 构建模块
│   │   ├── build.go       # 构建逻辑
│   │   ├── install.go     # 安装逻辑
│   │   ├── gomodules.go   # Go Modules 支持
│   │   ├── legacy.go      # GOPATH 支持
│   │   └── tmpfolder.go   # 临时目录管理
│   │
│   ├── github/            # GitHub 集成
│   ├── prow/              # Prow CI 集成
│   └── qiniu/             # 七牛云相关功能
│
├── tools/                 # 工具
│   └── vscode-ext/        # VSCode 扩展
│
├── tests/                 # 测试用例
│   └── samples/           # 测试样例项目
│
└── docs/                  # 文档
```

## 架构设计

### 1. 核心组件

#### 1.1 服务注册中心 (Coverage Server)
- **位置**: `pkg/cover/server.go`
- **功能**: 
  - 管理被测试服务的注册信息
  - 提供 HTTP API 接口
  - 聚合多个服务的覆盖率数据
  - 支持文件持久化和内存存储

#### 1.2 代码插桩模块 (Instrumentation)
- **位置**: `pkg/cover/instrument.go`
- **功能**:
  - 在目标代码中注入覆盖率计数器
  - 生成 HTTP API 处理器用于运行时查询覆盖率
  - 支持 Go Modules 和 GOPATH 项目

#### 1.3 构建模块 (Build)
- **位置**: `pkg/build/build.go`
- **功能**:
  - 将项目复制到临时目录
  - 执行代码插桩
  - 构建带覆盖率支持的二进制文件
  - 支持自定义构建参数

#### 1.4 客户端模块 (Client)
- **位置**: `pkg/cover/client.go`
- **功能**:
  - 与服务注册中心通信
  - 获取覆盖率数据
  - 清空覆盖率计数器
  - 注册/移除服务

### 2. 工作流程

#### 2.1 基本使用流程

```
1. 启动服务注册中心
   goc server
   ↓
2. 构建带覆盖率插桩的二进制
   goc build .
   ↓
3. 运行生成的二进制
   ./your-binary
   (自动注册到服务注册中心)
   ↓
4. 获取覆盖率数据
   goc profile
```

#### 2.2 代码插桩流程

```
1. 复制项目到临时目录
2. 解析 Go 包依赖
3. 对目标包进行覆盖率插桩
4. 生成 _cover_http_apis.go 文件（包含 HTTP 处理器）
5. 生成全局覆盖率变量文件
6. 执行 go build 构建二进制
7. 将二进制输出到原始目录
```

#### 2.3 运行时覆盖率收集流程

```
1. 被测试服务启动时自动注册到服务注册中心
2. 服务运行过程中，覆盖率计数器实时更新
3. 通过 HTTP API 查询覆盖率数据
4. 服务注册中心聚合多个服务的覆盖率数据
5. 输出标准格式的覆盖率文件
```

### 3. 数据流

```
被测试服务 (Binary)
    │
    │ HTTP API (/v1/cover/profile)
    ↓
服务注册中心 (Goc Server)
    │
    │ 聚合多个服务
    ↓
覆盖率数据 (Coverage Profile)
    │
    │ 标准格式输出
    ↓
覆盖率文件 (.cov)
```

### 4. 存储机制

- **文件存储** (`FileStore`): 持久化服务注册信息到本地文件
- **内存存储** (`MemoryStore`): 临时存储，不持久化

### 5. API 接口

服务注册中心提供以下 HTTP API:

- `POST /v1/cover/register` - 注册服务
- `GET /v1/cover/list` - 列出所有注册的服务
- `POST /v1/cover/profile` - 获取覆盖率数据
- `POST /v1/cover/clear` - 清空覆盖率计数器
- `POST /v1/cover/init` - 初始化系统
- `POST /v1/cover/remove` - 移除服务

## 技术特点

1. **支持 Go Modules 和 GOPATH**: 兼容两种 Go 项目结构
2. **运行时插桩**: 无需重新编译即可收集覆盖率
3. **多服务支持**: 支持同时管理多个被测试服务
4. **数据聚合**: 自动合并多个服务的覆盖率数据
5. **标准格式输出**: 输出标准 Go 覆盖率格式，兼容现有工具
6. **VSCode 集成**: 提供 VSCode 扩展实时显示覆盖率

## 依赖关系

- **Gin**: HTTP Web 框架（服务注册中心）
- **Cobra**: CLI 框架
- **golang.org/x/tools/cover**: Go 官方覆盖率工具
- **k8s.io/test-infra**: Kubernetes 测试基础设施（覆盖率合并）

## 扩展性

- 支持自定义服务注册中心地址
- 支持自定义覆盖率收集端口
- 支持文件过滤（包含/排除特定文件）
- 支持覆盖率数据合并和差异分析

