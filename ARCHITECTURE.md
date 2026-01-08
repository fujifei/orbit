# Orbit 后端服务架构图

## 系统架构概览

```mermaid
graph TB
    subgraph "覆盖率收集层"
        subgraph "GOC 上报"
            GOC_APP[Go 应用<br/>goc build]
            GOC_SERVER[GOC Server<br/>服务注册中心]
            GOC_REPORT[上报模块]
        end
        
        subgraph "JACA 上报"
            JAVA_APP[Java 应用<br/>JaCoCo Agent]
            JACA_AGENT[JACA Agent<br/>定时采集]
            JACA_PARSER[XML 解析器<br/>行转区间]
            JACA_REPORT[上报模块]
        end
        
        subgraph "PYCA 上报"
            PYTHON_APP[Python 应用<br/>自动加载]
            PYCA_AGENT[PYCA Agent<br/>定时采集]
            PYCA_PARSER[覆盖率解析器<br/>行转区间]
            PYCA_REPORT[上报模块]
        end
    end
    
    subgraph "消息队列层"
        RABBITMQ[RabbitMQ<br/>coverage_exchange<br/>coverage_queue]
    end
    
    subgraph "后端服务层"
        subgraph "Coverage Consumer"
            CONSUMER[消息消费者]
            MSG_PARSER[消息解析器<br/>goc/jaca/pyca]
            DB_WRITER[数据库写入器]
        end
        
        subgraph "Coverage API"
            API_SERVER[Flask API Server]
            
            subgraph "全量覆盖率处理"
                FULL_QUERY[查询报告详情]
                FULL_STATS[统计计算器]
                FULL_RESPONSE[响应生成]
            end
            
            subgraph "增量覆盖率处理"
                DIFF_QUERY[查询报告和基准]
                GIT_DIFF[Git Diff 计算]
                DIFF_MERGE[差异合并器]
                DIFF_STATS[增量统计计算]
                DIFF_RESPONSE[响应生成]
            end
        end
    end
    
    subgraph "数据存储层"
        DB[(MySQL 数据库)]
        subgraph "数据表"
            REPORT_TABLE[CoverageReport<br/>报告元信息]
            FILE_TABLE[CoverageFile<br/>文件信息]
            RANGE_TABLE[CoverageRange<br/>覆盖率区间]
            CONFIG_TABLE[CoverageConfig<br/>仓库配置]
        end
    end
    
    subgraph "Git 仓库"
        GIT_REPO[Git 仓库<br/>用于增量计算]
    end
    
    %% GOC 上报流程
    GOC_APP -->|运行时收集| GOC_SERVER
    GOC_SERVER -->|上报数据| GOC_REPORT
    GOC_REPORT -->|发布消息| RABBITMQ
    
    %% JACA 上报流程
    JAVA_APP -->|JaCoCo Agent| JACA_AGENT
    JACA_AGENT -->|定时 dump| JACA_PARSER
    JACA_PARSER -->|解析转换| JACA_REPORT
    JACA_REPORT -->|发布消息| RABBITMQ
    
    %% PYCA 上报流程
    PYTHON_APP -->|自动加载| PYCA_AGENT
    PYCA_AGENT -->|定时采集| PYCA_PARSER
    PYCA_PARSER -->|解析转换| PYCA_REPORT
    PYCA_REPORT -->|发布消息| RABBITMQ
    
    %% 消费者处理流程
    RABBITMQ -->|消费消息| CONSUMER
    CONSUMER -->|解析消息| MSG_PARSER
    MSG_PARSER -->|提取数据| DB_WRITER
    DB_WRITER -->|写入| DB
    
    %% 全量覆盖率查询流程
    API_SERVER -->|GET /reports/<id>| FULL_QUERY
    FULL_QUERY -->|查询| DB
    DB -->|返回数据| FULL_STATS
    FULL_STATS -->|计算统计| FULL_RESPONSE
    FULL_RESPONSE -->|JSON 响应| API_SERVER
    
    %% 增量覆盖率查询流程
    API_SERVER -->|GET /reports/<id>/diff| DIFF_QUERY
    DIFF_QUERY -->|查询报告和配置| DB
    DIFF_QUERY -->|获取基准分支| CONFIG_TABLE
    DIFF_QUERY -->|查询覆盖率数据| RANGE_TABLE
    DIFF_QUERY -->|Git Diff| GIT_REPO
    GIT_REPO -->|返回差异| GIT_DIFF
    GIT_DIFF -->|差异数据| DIFF_MERGE
    RANGE_TABLE -->|覆盖率数据| DIFF_MERGE
    DIFF_MERGE -->|合并结果| DIFF_STATS
    DIFF_STATS -->|计算增量统计| DIFF_RESPONSE
    DIFF_RESPONSE -->|JSON 响应| API_SERVER
    
    %% 样式
    style GOC_APP fill:#e1f5ff
    style JAVA_APP fill:#e1f5ff
    style PYTHON_APP fill:#e1f5ff
    style RABBITMQ fill:#fff4e1
    style CONSUMER fill:#e8f5e9
    style API_SERVER fill:#f3e5f5
    style DB fill:#fce4ec
    style GIT_REPO fill:#e0f2f1
```

## 详细流程说明

### 1. 上报逻辑

#### GOC 上报流程
```
1. Go 应用使用 goc build 构建
2. 应用运行时，goc 自动收集覆盖率数据
3. 通过 goc server 统一管理多个服务
4. 上报模块将覆盖率数据格式化为标准格式
5. 发布消息到 RabbitMQ (routing_key: coverage.report)
```

#### JACA 上报流程
```
1. Java 应用启动时加载 JaCoCo Agent
2. JACA Agent 定时（默认60秒）调用 JaCoCo CLI dump
3. 生成 XML 格式的覆盖率报告
4. XML 解析器将行级覆盖率转换为区间级（兼容 goc 格式）
5. 计算 Fingerprint（SHA256），仅在变化时上报
6. 发布消息到 RabbitMQ (routing_key: coverage.report)
```

#### PYCA 上报流程
```
1. Python 应用启动时自动加载 PYCA（通过 .pth + sitecustomize）
2. PYCA Agent 定时（默认60秒）采集覆盖率数据
3. 提取 executed_lines（已执行行）
4. 将行级数据转换为区间级（连续行合并为区间）
5. 计算 Fingerprint（SHA256），仅在变化时上报
6. 发布消息到 RabbitMQ (routing_key: coverage.report)
```

### 2. 消费者处理核心逻辑

```mermaid
sequenceDiagram
    participant MQ as RabbitMQ
    participant Consumer as Coverage Consumer
    participant Parser as 消息解析器
    participant Manager as 业务逻辑层
    participant DB as MySQL 数据库
    
    MQ->>Consumer: 消费消息 (coverage.report)
    Consumer->>Parser: 解析 JSON 消息
    Parser->>Parser: 提取 repo_id, branch, commit
    Parser->>Parser: 识别格式 (goc/jaca/pyca)
    
    alt 格式为 goc
        Parser->>Manager: parse_goc_coverage(raw)
    else 格式为 jaca
        Parser->>Manager: parse_goc_coverage(raw) [复用]
    else 格式为 pca
        Parser->>Manager: parse_pca_coverage(raw) [复用]
    end
    
    Manager->>Manager: 解析覆盖率数据
    Manager->>Manager: 提取文件列表和区间数据
    
    Manager->>DB: 创建/更新 CoverageReport
    Manager->>DB: 创建/更新 CoverageFile
    Manager->>DB: 创建/更新 CoverageRange
    
    DB-->>Manager: 返回结果
    Manager-->>Consumer: 处理成功
    Consumer-->>MQ: ACK 消息
    
    alt 处理失败
        Consumer->>Consumer: 检查重试次数
        alt 未达上限 (< 10次)
            Consumer->>MQ: 重新发布消息（增加重试计数）
        else 已达上限
            Consumer->>MQ: NACK 消息（丢弃）
        end
    end
```

**核心处理步骤**：
1. **消息接收**: 从 RabbitMQ 队列 `coverage_queue` 消费消息
2. **消息解析**: 解析 JSON 格式，提取元信息（repo_id, branch, commit 等）
3. **格式识别**: 根据 `coverage.format` 字段识别格式（goc/jaca/pca）
4. **数据解析**: 调用对应的解析函数，将原始覆盖率数据解析为结构化数据
5. **数据存储**:
   - 创建或更新 `CoverageReport`（报告元信息）
   - 创建或更新 `CoverageFile`（文件信息）
   - 创建或更新 `CoverageRange`（覆盖率区间数据）
6. **错误处理**: 支持重试机制，最多重试 10 次

### 3. API 获取全量覆盖率业务逻辑

```mermaid
sequenceDiagram
    participant Client as 前端客户端
    participant API as Coverage API
    participant DB as MySQL 数据库
    participant Manager as 业务逻辑层
    
    Client->>API: GET /api/v1/coverage/reports/<id>
    API->>DB: 查询 CoverageReport (id)
    DB-->>API: 返回报告信息
    
    API->>DB: 查询 CoverageFile (repo_id, branch)
    DB-->>API: 返回文件列表
    
    API->>DB: 查询 CoverageRange (file_id)
    DB-->>API: 返回覆盖率区间数据
    
    API->>Manager: get_report_statistics(report)
    Manager->>Manager: 计算统计信息
    Note over Manager: total_statements = 所有区间的 statements 之和<br/>covered_statements = hit > 0 的 statements 之和<br/>coverage_rate = covered / total
    
    Manager-->>API: 返回统计结果
    
    API->>API: 组装响应数据
    API-->>Client: 返回 JSON 响应
    Note over Client: {<br/>  report: {...},<br/>  statistics: {<br/>    total_statements: 1000,<br/>    covered_statements: 750,<br/>    coverage_rate: 0.75<br/>  },<br/>  files: [...]<br/>}
```

**核心处理步骤**：
1. **查询报告**: 根据 report_id 查询 `CoverageReport` 表
2. **查询文件**: 根据 repo_id 和 branch 查询 `CoverageFile` 表
3. **查询区间**: 根据 file_id 查询 `CoverageRange` 表
4. **统计计算**:
   - `total_statements`: 所有区间的 statements 字段之和
   - `covered_statements`: hit > 0 的区间的 statements 之和
   - `coverage_rate`: covered_statements / total_statements
5. **过滤排除**: 根据 `CoverageConfig` 中的 exclude_dirs 和 exclude_files 过滤
6. **响应生成**: 组装 JSON 响应返回给客户端

### 4. API 获取增量覆盖率业务逻辑

```mermaid
sequenceDiagram
    participant Client as 前端客户端
    participant API as Coverage API
    participant DB as MySQL 数据库
    participant Manager as Diff Manager
    participant Git as Git 仓库
    
    Client->>API: GET /api/v1/coverage/reports/<id>/diff
    API->>DB: 查询 CoverageReport (id)
    DB-->>API: 返回报告信息
    
    API->>DB: 查询 CoverageConfig (repo_id)
    DB-->>API: 返回配置信息（base_branch）
    
    API->>Manager: calculate_diff_coverage(...)
    
    Manager->>Git: git diff base_branch...target_branch
    Git-->>Manager: 返回代码差异
    
    Manager->>Manager: parse_git_diff(diff_output)
    Note over Manager: 解析差异，提取：<br/>- 新增文件<br/>- 修改文件<br/>- 删除文件<br/>- 修改的行范围
    
    Manager->>DB: 查询 CoverageRange (repo_id, branch)
    DB-->>Manager: 返回覆盖率区间数据
    
    Manager->>Manager: build_coverage_index(ranges)
    Note over Manager: 构建覆盖率索引<br/>file_path -> [CoverageBlock]
    
    Manager->>Manager: merge_diff_and_coverage(diff, coverage)
    Note over Manager: 合并差异和覆盖率：<br/>- 匹配差异行和覆盖率区间<br/>- 标记新增/修改行的覆盖状态<br/>- 生成 DiffCoverageFile 列表
    
    Manager->>Manager: generate_diff_coverage_summary(files)
    Note over Manager: 计算增量统计：<br/>- diff_lines: 差异总行数<br/>- covered_lines: 已覆盖差异行数<br/>- diff_coverage_rate: 增量覆盖率
    
    Manager-->>API: 返回增量覆盖率结果
    
    API->>API: 更新报告的 base_commit
    API->>DB: 更新 CoverageReport
    
    API-->>Client: 返回 JSON 响应
    Note over Client: {<br/>  report_id: 123,<br/>  target_commit: "abc...",<br/>  base_commit: "def...",<br/>  base_branch: "master",<br/>  files: [...],<br/>  summary: {<br/>    diff_lines: 100,<br/>    covered_lines: 75,<br/>    diff_coverage_rate: 0.75<br/>  }<br/>}
```

**核心处理步骤**：
1. **获取报告和配置**: 查询 `CoverageReport` 和 `CoverageConfig`，获取目标分支和基准分支
2. **Git Diff 计算**: 
   - 克隆或更新 Git 仓库（使用 bare repo + worktree）
   - 执行 `git diff base_branch...target_branch`
   - 解析 diff 输出，提取文件变更和行范围
3. **查询覆盖率数据**: 从数据库查询目标分支的覆盖率区间数据
4. **构建覆盖率索引**: 将覆盖率区间数据组织为高效查找的数据结构
5. **合并差异和覆盖率**:
   - 匹配差异行和覆盖率区间
   - 判断每个差异行的覆盖状态（已覆盖/未覆盖）
   - 生成 `DiffCoverageFile` 列表
6. **计算增量统计**:
   - `diff_lines`: 差异总行数（新增+修改）
   - `covered_lines`: 已覆盖的差异行数
   - `diff_coverage_rate`: covered_lines / diff_lines
7. **更新基准信息**: 更新报告的 `base_commit` 和 `base_branch`
8. **响应生成**: 组装 JSON 响应返回给客户端

## 数据格式说明

### 消息格式（统一）
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

### 覆盖率数据格式（统一区间级格式）
```
mode: count
file.go:10.32,14.34 2 1
file.go:20.10,20.15 1 1
```

格式说明：
- `file.go:startLine.startCol,endLine.endCol statements count`
- `statements`: 该代码块包含的语句数
- `count`: 执行次数（1 表示已覆盖）

## 关键技术点

### 1. 格式统一
- 所有工具（goc/jaca/pyca）最终都转换为区间级格式
- 统一使用 goc 格式作为标准格式
- 便于统一处理和存储

### 2. Fingerprint 算法
- JACA 和 PYCA 使用 SHA256 计算覆盖率指纹
- 仅在覆盖率变化时上报，减少网络传输
- 指纹计算基于区间列表的字符串表示

### 3. 增量覆盖率计算
- 使用 Git Diff 获取代码差异
- 通过区间匹配算法将差异行与覆盖率区间关联
- 支持跨文件、跨模块的增量计算

### 4. 错误处理和重试
- 消费者支持消息重试机制（最多 10 次）
- 使用 RabbitMQ 的 headers 传递重试计数
- 失败消息最终丢弃，避免无限重试

### 5. 数据库设计
- 使用 MySQL 存储结构化数据
- 通过索引优化查询性能（repo_id, branch, file_path 等）
- 支持分页查询和条件过滤

