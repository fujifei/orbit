# Orbit - 代码覆盖率平台

Orbit 是一个统一的代码覆盖率收集、存储和可视化平台，支持 Go、Java、Python 三种语言的覆盖率数据收集和展示。

## 项目结构

```
qa/
├── goc/              # Go 语言覆盖率工具（已移至上级目录）
├── jaca/             # Java 覆盖率适配器（已移至上级目录）
├── pyca/             # Python 覆盖率代理（已移至上级目录）
└── orbit/            # Orbit 覆盖率平台
    ├── coverage-platform/ # 后端服务（API + Consumer）
    │   ├── coverage-api/      # RESTful API 服务
    │   ├── coverage-consumer/ # 消息队列消费者
    │   └── manager/           # 业务逻辑管理层
    └── coverage-fe/      # 前端可视化界面
```

## 核心组件

### 1. 覆盖率收集工具

#### GOC (Go Coverage)
- **位置**: `../goc/` (位于 orbit 目录的上级目录)
- **功能**: Go 语言系统测试覆盖率收集工具
- **特点**: 
  - 支持运行时覆盖率收集
  - 通过 goc server 统一管理
  - 支持多服务聚合

#### JACA (Java Coverage Adapter)
- **位置**: `../jaca/` (位于 orbit 目录的上级目录)
- **功能**: Java 覆盖率适配器，从 JaCoCo agent 获取数据
- **特点**:
  - 对业务代码无侵入（Java Agent 模式）
  - 定时采集覆盖率数据（默认 60 秒）
  - 行级转区间级，兼容 goc 格式
  - Fingerprint 算法，仅在变化时上报

#### PYCA (Python Coverage Agent)
- **位置**: `../pyca/` (位于 orbit 目录的上级目录)
- **功能**: Python 覆盖率代理，无侵入收集覆盖率
- **特点**:
  - 使用 `.pth` + `sitecustomize` 双钩子方案
  - 定时采集（默认 60 秒）
  - 增量上报（Fingerprint 算法）
  - 支持上报到 RabbitMQ

### 2. 后端服务

#### Coverage API
- **位置**: `coverage-platform/coverage-api/`
- **功能**: 提供 RESTful API 接口
- **主要接口**:
  - `GET /api/v1/coverage/reports` - 获取覆盖率报告列表
  - `GET /api/v1/coverage/reports/<id>` - 获取报告详情（全量覆盖率）
  - `GET /api/v1/coverage/reports/<id>/diff` - 获取增量覆盖率
  - `GET /api/v1/coverage/files` - 获取文件列表
  - `GET /api/v1/coverage/files/<id>` - 获取文件详情
  - `GET /api/v1/coverage/configs` - 配置管理

#### Coverage Consumer
- **位置**: `coverage-platform/coverage-consumer/`
- **功能**: 从 RabbitMQ 消费覆盖率消息并存储到数据库
- **处理流程**:
  1. 从 RabbitMQ 接收消息
  2. 解析消息（支持 goc/jaca/pyca 格式）
  3. 存储到数据库（CoverageReport、CoverageFile、CoverageRange）
  4. 支持重试机制（最多 10 次）

### 3. 前端服务

#### Coverage FE
- **位置**: `coverage-fe/`
- **技术栈**: React + Vite + Ant Design
- **功能**: 
  - 覆盖率报告列表展示
  - 全量覆盖率可视化
  - 增量覆盖率可视化
  - 代码高亮显示覆盖情况

## 数据流程

### 上报流程

1. **GOC 上报**:
   ```
   被测服务 (goc build) 
   → goc server 
   → 上报到 RabbitMQ (coverage.report)
   ```

2. **JACA 上报**:
   ```
   Java 应用 (JaCoCo Agent)
   → JACA 定时采集 (JaCoCo CLI)
   → 解析 XML → 转区间级
   → 计算 Fingerprint
   → 上报到 RabbitMQ (coverage.report)
   ```

3. **PYCA 上报**:
   ```
   Python 应用 (自动加载)
   → PYCA 定时采集 (coverage.py)
   → 提取 executed_lines
   → 行转区间 → 计算 Fingerprint
   → 上报到 RabbitMQ (coverage.report)
   ```

### 处理流程

```
RabbitMQ (coverage_queue)
  ↓
Coverage Consumer
  ↓
解析消息 (goc/jaca/pyca 格式)
  ↓
存储到数据库
  ├── CoverageReport (报告元信息)
  ├── CoverageFile (文件信息)
  └── CoverageRange (覆盖率区间)
```

### 查询流程

#### 全量覆盖率
```
API 请求: GET /api/v1/coverage/reports/<id>
  ↓
查询数据库
  ├── CoverageReport (报告信息)
  ├── CoverageFile (文件列表)
  └── CoverageRange (覆盖率区间)
  ↓
计算统计信息
  ├── total_statements (总语句数)
  ├── covered_statements (已覆盖语句数)
  └── coverage_rate (覆盖率)
  ↓
返回 JSON 响应
```

#### 增量覆盖率
```
API 请求: GET /api/v1/coverage/reports/<id>/diff
  ↓
获取基准分支和目标分支
  ↓
Git Diff (计算代码差异)
  ↓
查询目标分支覆盖率数据
  ↓
合并差异和覆盖率
  ↓
计算增量覆盖率统计
  ├── diff_lines (差异行数)
  ├── covered_lines (已覆盖差异行)
  └── diff_coverage_rate (增量覆盖率)
  ↓
返回 JSON 响应
```

## 数据库模型

### CoverageReport
- 报告元信息（repo_id, branch, commit, status 等）

### CoverageFile
- 文件信息（repo_id, branch, file_path 等）

### CoverageRange
- 覆盖率区间（file_id, start_line, end_line, hit 等）

### CoverageConfig
- 仓库配置（repo_url, base_branch, exclude_dirs, exclude_files 等）

## 消息格式

所有工具上报的消息格式统一：

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
    "format": "goc|jaca|pca",
    "raw": "mode: count\nfile.go:10.32,14.34 2 1\n..."
  },
  "timestamp": 1234567890
}
```

## 覆盖率数据格式

所有工具统一使用区间级格式（兼容 goc 格式）：

```
mode: count
file.go:10.32,14.34 2 1
file.go:20.10,20.15 1 1
```

格式说明：
- `file.go:startLine.startCol,endLine.endCol statements count`
- `statements`: 该代码块包含的语句数
- `count`: 执行次数（1 表示已覆盖）

## 快速开始

### 1. 启动 RabbitMQ

```bash
cd coverage-platform/docker/rabbitmq
docker-compose up -d
```

### 2. 初始化数据库

```bash
cd coverage-platform
python3 -c "from models import init_db; init_db()"
```

### 3. 启动后端服务

```bash
cd coverage-platform
./run.sh start
```

### 4. 启动前端服务

```bash
cd coverage-fe
npm install
npm run dev
```

### 5. 使用覆盖率工具

#### GOC
```bash
# 启动 goc server
goc server

# 构建并运行被测服务
goc build .
./your-service

# 上报覆盖率（通过 goc server 配置）
```

#### JACA
```bash
# Java Agent 模式
java -javaagent:jaca.jar=flushInterval=60 your-app.jar

# 独立服务模式
java -jar jaca.jar
```

#### PYCA
```bash
# 安装
pip install /path/to/pyca

# 配置环境变量
export PCA_RABBITMQ_URL="amqp://coverage:coverage123@localhost:5672/"
export PCA_FLUSH_INTERVAL=60

# 运行应用
python your-app.py
```

## 配置说明

### 环境变量

#### Coverage Consumer
- `RABBITMQ_URL`: RabbitMQ 连接 URL（默认: `amqp://coverage:coverage123@localhost:5672/`）

#### Coverage API
- 默认端口: `8826`

#### PYCA
- `PCA_ENABLED`: 是否启用（默认: 1）
- `PCA_RABBITMQ_URL`: RabbitMQ 连接 URL
- `PCA_FLUSH_INTERVAL`: 采集间隔（秒，默认: 60）
- `GITHUB_TOKEN`: GitHub Token（可选，用于获取 repo_id）

#### JACA
- `JACOCO_CLI_JAR`: JaCoCo CLI JAR 路径
- `RABBITMQ_URL`: RabbitMQ 连接 URL
- `FLUSH_INTERVAL`: 采集间隔（秒，默认: 60）

## 架构图

详细的系统架构图请参考 [ARCHITECTURE.md](./ARCHITECTURE.md)，包含：

- 完整的系统架构概览图
- GOC/JACA/PYCA 上报流程详解
- Coverage Consumer 处理核心逻辑
- API 获取全量覆盖率和增量覆盖率的业务逻辑
- 数据格式说明和关键技术点

## 相关文档

- [GOC README](../goc/README.md)
- [JACA README](../jaca/README.md)
- [PYCA README](../pyca/README.md)
- [Coverage Platform README](./coverage-fe/README.md)
- [Diff Coverage Feature](./coverage-fe/DIFF_COVERAGE_FEATURE.md)

## 许可证

各组件可能有不同的许可证，请查看各子目录的 LICENSE 文件。

