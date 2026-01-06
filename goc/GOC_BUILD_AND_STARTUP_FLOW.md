# GOC Build 和启动流程详解

本文档详细说明使用 `goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o api .` 编译服务后再启动命令时，整个过程中执行的所有操作。

## 一、编译阶段 (goc build)

### 1.1 命令解析阶段

**位置**: `goc/cmd/build.go` 和 `goc/cmd/commonflags.go`

**操作**:
- 解析命令行参数，包括：
  - `--rabbitmq-url`: RabbitMQ 连接 URL（存储到 `rabbitmqURL` 变量）
  - `--output` / `-o`: 输出文件路径（存储到 `buildOutput` 变量）
  - `--mode`: 覆盖率模式（count/set/atomic，默认 count）
  - `--center`: goc 中心地址（默认 http://127.0.0.1:7777）
  - `--agentport`: 固定端口号
  - `--singleton`: 单例模式标志
  - `--buildflags`: 额外的构建标志

### 1.2 创建 Build 对象

**位置**: `goc/pkg/build/build.go::NewBuild()`

**操作**:
1. 验证参数（检查工作目录、参数数量等）
2. 创建 `Build` 结构体，包含：
   - `BuildFlags`: 构建标志
   - `Packages`: 要构建的包（通常是 "."）
   - `WorkingDir`: 当前工作目录

### 1.3 移动项目到临时目录

**位置**: `goc/pkg/build/build.go::MvProjectsToTmp()`

**操作**:
1. **列出所有包** (`cover.ListPackages()`):
   - 执行 `go list -json ./...` 命令
   - 解析 JSON 输出，获取所有包的依赖信息

2. **创建临时目录** (`mvProjectsToTmp()`):
   - 临时目录路径: `$TMPDIR/goc-build-{hash}`
   - hash 基于工作目录路径的 SHA256 前6位
   - 删除之前的临时目录（如果存在）
   - 创建全局覆盖率变量存储路径: `src/gocbuild{hash}/`

3. **判断项目类型**:
   - 遍历包列表，判断是 Go Modules 项目还是 Legacy GOPATH 项目
   - 设置 `IsMod` 和 `Root` 标志

4. **复制项目文件**:
   - **Go Modules 项目**: 复制整个模块目录到临时目录 (`cpGoModulesProject()`)
   - **Legacy GOPATH 项目**: 复制包及其依赖到临时目录 (`cpLegacyProject()`)
   - **非标准项目**: 仅复制主包目录 (`cpNonStandardLegacy()`)
   - 跳过 `.git` 目录和不规则文件

5. **更新 go.mod** (仅 Go Modules 项目):
   - 如果 `go.mod` 中有相对路径的 `replace` 指令，转换为绝对路径
   - 确保临时目录中的依赖路径正确

6. **设置新的 GOPATH**:
   - Go Modules: `NewGOPATH = ""` (使用模块模式)
   - Legacy GOPATH: `NewGOPATH = "$TmpDir:$OriGOPATH"`

### 1.4 注入覆盖率代码

**位置**: `goc/pkg/cover/cover.go::Execute()`

**操作**:
1. **再次列出包** (在临时目录中):
   - 执行 `go list -json ./...` 在临时目录中

2. **处理主包**:
   - 找到 `Name == "main"` 的包
   - 为每个 `.go` 文件注入覆盖率计数器 (`AddCounters()`)

3. **处理依赖包**:
   - 遍历主包的所有依赖 (`pkg.Deps`)
   - 只为非标准库、非第三方库的依赖注入计数器
   - 避免重复处理已处理的包

4. **注入计数器到源文件** (`pkg/cover/internal/tool/cover.go::Annotate()`):
   - 解析 Go 源文件 AST
   - 在每个基本块（basic block）开始处插入计数器语句
   - 根据模式选择计数器语句：
     - `count`: `GoCover_X.Count[i]++`
     - `set`: `GoCover_X.Count[i] = 1`
     - `atomic`: `atomic.AddUint32(&GoCover_X.Count[i], 1)`
   - 添加全局覆盖率变量导入语句
   - 生成覆盖率变量声明（但不写入文件，返回字符串）

5. **生成 HTTP API 文件** (`InjectCountersHandlers()`):
   - 在临时目录的主包目录下生成 `_cover_http_apis_auto_generated.go` 文件
   - 该文件包含：
     - 全局变量 `gocReportURL`（从 `RabbitMQURL` 参数设置）
     - HTTP 服务器和路由处理
     - 覆盖率数据收集和上报逻辑
     - Git 信息获取逻辑
     - CI 信息获取逻辑
     - RabbitMQ 上报逻辑

6. **生成全局覆盖率变量文件** (`injectGlobalCoverVarFile()`):
   - 在临时目录的 `src/gocbuild{hash}/` 目录下创建 `cover.go`
   - 包含所有包的覆盖率变量声明
   - 每个文件对应一个覆盖率变量结构体

### 1.5 执行 Go Build

**位置**: `goc/pkg/build/build.go::Build()`

**操作**:
1. 在临时目录中执行 `go build` 命令
2. 设置环境变量 `GOPATH=$NewGOPATH`（如果是 Legacy 项目）
3. 构建标志包含 `-o $Target`（输出到指定路径）
4. 编译后的二进制文件包含：
   - 原始业务代码
   - 注入的覆盖率计数器
   - 生成的 HTTP API 代码
   - 全局覆盖率变量

### 1.6 清理临时目录

**位置**: `goc/pkg/build/build.go::Clean()`

**操作**:
- 如果不在 debug 模式，删除临时目录
- 如果启用 debug 模式，保留临时目录用于调试

---

## 二、启动阶段 (运行编译后的二进制)

### 2.1 程序初始化

**位置**: 生成的 `_cover_http_apis_auto_generated.go` 中的 `init()` 函数

**操作**:
- 启动 goroutine 执行 `registerHandlersGoc()`

### 2.2 注册 HTTP 处理器

**位置**: `registerHandlersGoc()` 函数

**操作**:

1. **初始化 Git 信息** (`getGitInfoGoc()`):
   - 查找 `.git` 目录（向上遍历目录树）
   - 获取远程仓库 URL (`getGitRemoteOriginGoc()`):
     - 读取 `.git/config` 文件
     - 解析 `[remote "origin"]` 部分的 `url` 字段
   - 获取当前分支 (`getGitBranchGoc()`):
     - 读取 `.git/HEAD` 文件
     - 解析 `ref: refs/heads/{branch}` 或直接使用 commit hash
   - 获取当前 commit (`getGitCommitGoc()`):
     - 读取 `.git/HEAD` 指向的 ref 文件
     - 或直接使用 HEAD 内容（如果是 detached HEAD）
   - 获取 GitHub 仓库 ID (`getGitHubRepoIDGoc()`):
     - 解析 GitHub URL（支持 https://、git@、git:// 格式）
     - 调用 GitHub API: `GET https://api.github.com/repos/{owner}/{repo}`
     - 提取 `id` 字段作为 `repo_id`

2. **初始化 CI 信息** (`getCIInfoGoc()`):
   - 检查环境变量，识别 CI 平台：
     - **GitLab CI**: `CI_PIPELINE_ID`, `CI_JOB_ID`
     - **Jenkins**: `BUILD_NUMBER`, `JOB_NAME`
     - **GitHub Actions**: `GITHUB_RUN_ID`, `GITHUB_JOB`
     - **CircleCI**: `CIRCLE_BUILD_NUM`, `CIRCLE_JOB`

3. **检查 RabbitMQ URL**:
   - 如果 `gocReportURL` 为空:
     - 输出警告日志: `[goc][WARN] gocReportURL is EMPTY - coverage reporting is DISABLED`
   - 如果 `gocReportURL` 已设置:
     - 输出信息日志: `[goc][INFO] gocReportURL is set: {url}`
     - 输出 Git 信息日志
     - **启动定期上报 goroutine**:
       - 立即执行一次覆盖率上报
       - 然后每 1 分钟执行一次上报
       - 使用 `time.Ticker` 实现定时

4. **启动 HTTP 监听** (`listenGoc()`):
   - 如果指定了 `--agentport`，使用指定端口
   - 否则尝试使用上次的端口（从 `{binary}_profile_listen_addr` 文件读取）
   - 如果失败，使用随机端口（`:0`）
   - 获取真实 IP 地址（优先非回环地址）
   - 保存监听地址到 `{binary}_profile_listen_addr` 文件

5. **注册到 goc 中心** (非 singleton 模式):
   - 向 `{center}/v1/cover/register` 发送 POST 请求
   - 参数: `name={service_name}&address=http://{host}:{port}`
   - 服务名从环境变量 `GOC_SERVICE_NAME` 获取，或使用二进制文件名

6. **注册信号处理** (非 singleton 模式):
   - 监听 `SIGHUP`, `SIGQUIT`, `SIGTERM`, `SIGINT` 信号
   - 收到退出信号时，向 goc 中心注销服务

7. **注册 HTTP 路由**:
   - `/v1/cover/coverage`: 返回覆盖率百分比（0-1 之间的浮点数）
   - `/v1/cover/profile`: 返回覆盖率 profile 数据（goc 格式）
     - 如果设置了 `gocReportURL`，同时触发一次手动上报
   - `/v1/cover/clear`: 清空所有覆盖率计数器

### 2.3 定期覆盖率上报

**位置**: `collectAndReportCoverageGoc()` 函数

**操作** (每 1 分钟执行一次):

1. **收集覆盖率数据**:
   - 遍历所有覆盖率计数器 (`loadValuesGoc()`)
   - 生成 goc 格式的覆盖率 profile:
     ```
     mode: {mode}
     {file}:{line0}.{col0},{line1}.{col1} {stmts} {count}
     ...
     ```

2. **构建上报消息**:
   - 创建 `gocCoverageReportMessageStruct`:
     ```json
     {
       "repo": "git@github.com:owner/repo.git",
       "repo_id": "12345678",
       "branch": "main",
       "commit": "abc123...",
       "ci": {
         "provider": "github",
         "pipeline_id": "123",
         "job_id": "test"
       },
       "coverage": {
         "format": "goc",
         "raw": "mode: count\n..."
       },
       "timestamp": 1234567890
     }
     ```

3. **发布到 RabbitMQ** (`publishCoverageReportGoc()`):
   - 如果 URL 以 `amqp://` 开头:
     - 转换为 RabbitMQ HTTP Management API URL:
       - `amqp://user:pass@host:port/vhost` 
       - → `http://user:pass@host:15672/api/exchanges/%2F/coverage_exchange/publish`
     - 构建 RabbitMQ API 格式的 payload:
       ```json
       {
         "properties": {
           "content_type": "application/json"
         },
         "routing_key": "coverage.report",
         "payload": "{coverage_message_json}",
         "payload_encoding": "string"
       }
       ```
   - 如果 URL 是 HTTP URL:
     - 直接发送 JSON payload
   - 发送 HTTP POST 请求
   - 记录成功或失败日志

### 2.4 运行时覆盖率收集

**操作**:
- 当业务代码执行时，注入的计数器会自动递增
- 计数器存储在内存中的全局变量中
- 可以通过 HTTP API 实时查询覆盖率

---

## 三、关键文件生成

### 3.1 编译时生成的文件

1. **临时目录中的文件**:
   - `_cover_http_apis_auto_generated.go`: HTTP API 和上报逻辑
   - `src/gocbuild{hash}/cover.go`: 全局覆盖率变量声明
   - 所有 `.go` 文件: 已注入覆盖率计数器

2. **最终二进制文件**:
   - 包含所有注入的代码和生成的代码
   - `gocReportURL` 变量已硬编码到二进制中

### 3.2 运行时生成的文件

1. **`{binary}_profile_listen_addr`**:
   - 存储 HTTP 服务器的监听地址
   - 用于下次启动时复用端口

---

## 四、数据流图

```
编译阶段:
用户命令
  ↓
解析参数 (rabbitmqURL, output, etc.)
  ↓
创建临时目录
  ↓
复制项目到临时目录
  ↓
注入覆盖率计数器到源文件
  ↓
生成 _cover_http_apis_auto_generated.go (包含 gocReportURL)
  ↓
生成全局覆盖率变量文件
  ↓
执行 go build
  ↓
输出二进制文件
  ↓
清理临时目录

启动阶段:
运行二进制文件
  ↓
init() → registerHandlersGoc()
  ↓
获取 Git 信息 (repo, branch, commit, repo_id)
  ↓
获取 CI 信息 (provider, pipeline_id, job_id)
  ↓
检查 gocReportURL
  ↓
如果设置了 URL:
  ├─ 启动定期上报 goroutine (每 1 分钟)
  └─ 立即执行一次上报
  ↓
启动 HTTP 服务器
  ↓
注册到 goc 中心 (非 singleton 模式)
  ↓
监听 HTTP 请求和信号

运行时:
业务代码执行
  ↓
覆盖率计数器递增
  ↓
定期上报 (每 1 分钟)
  ├─ 收集覆盖率数据
  ├─ 构建消息
  └─ 发送到 RabbitMQ
```

---

## 五、关键配置说明

### 5.1 RabbitMQ URL 格式

- **AMQP 格式**: `amqp://user:pass@host:port/vhost`
  - 会被转换为 HTTP Management API URL
  - 默认使用端口 15672（RabbitMQ 管理端口）
  - 发布到 exchange: `coverage_exchange`
  - routing key: `coverage.report`

- **HTTP 格式**: `http://host:port/path`
  - 直接作为 webhook URL 使用
  - 发送 JSON payload

### 5.2 覆盖率模式

- **count**: 计数器模式，每次执行递增
- **set**: 设置模式，执行过就设为 1
- **atomic**: 原子模式，使用 `sync/atomic` 保证并发安全

### 5.3 环境变量

- `GOC_SERVICE_NAME`: 自定义服务名称（用于注册到 goc 中心）
- `CI_PIPELINE_ID`, `GITHUB_RUN_ID`, `BUILD_NUMBER`, `CIRCLE_BUILD_NUM`: CI 平台标识
- `GOPATH`: Legacy 项目需要

---

## 六、注意事项

1. **临时目录**: 编译完成后会删除（除非 debug 模式），但二进制文件已包含所有必要代码

2. **Git 信息**: 启动时从运行目录的 `.git` 获取，确保在 Git 仓库目录下运行

3. **RabbitMQ 连接**: 使用 HTTP API，不需要 AMQP 客户端库，但需要 RabbitMQ 管理插件启用

4. **端口复用**: 如果上次启动成功，会尝试使用相同的端口

5. **覆盖率数据**: 存储在内存中，程序重启后清零

6. **上报频率**: 固定为 1 分钟，无法配置

---

## 七、调试建议

1. **检查 gocReportURL 是否设置**:
   - 查看启动日志中的 `[goc][INFO]` 或 `[goc][WARN]` 消息
   - 或检查生成的 `_cover_http_apis_auto_generated.go` 文件（如果保留临时目录）

2. **检查上报是否成功**:
   - 查看日志中的 `[goc][INFO] Successfully published coverage report` 或错误消息
   - 检查 RabbitMQ 队列中是否有消息

3. **检查 Git 信息**:
   - 查看日志中的 `[goc][INFO] Git info: repo=...` 消息
   - 确保在 Git 仓库目录下运行

4. **保留临时目录**:
   - 使用 `goc build --debug` 或设置环境变量保留临时目录用于调试

