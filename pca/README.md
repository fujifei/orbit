# PCA (Python Coverage Agent)

业务无侵入的Python覆盖率上报插件

## 功能特性

1. **无侵入性**: 使用 `.pth` + `sitecustomize` 双钩子方案，无需修改业务代码
2. **增量上报**: 使用"已覆盖行指纹（Incremental Coverage）"算法，只在覆盖率变化时上报
3. **定时采集**: 自动定时采集覆盖率数据
4. **MQ上报**: 支持上报到RabbitMQ，协议兼容goc格式

## 安装

### 快速安装

```bash
# 方式1: 从本地路径安装（开发测试推荐）
pip install /path/to/orbit/pca

# 方式2: 从 Git 仓库安装
pip install git+https://github.com/your-org/orbit.git#subdirectory=pca

# 方式3: 从 PyPI 安装（如果已发布）
pip install python-coverage-agent
```

### 安装验证

安装成功后，会在 `site-packages` 中自动生成：
- `platform_coverage_agent.pth` - Python路径钩子
- `sitecustomize.py` - Python启动钩子

验证安装：
```bash
pip show python-coverage-agent
pca status
```

> **详细安装方式请参考**: [INSTALL.md](INSTALL.md) 和 [DEPLOYMENT.md](DEPLOYMENT.md)

## 配置

### 环境变量

- `PCA_ENABLED`: 是否启用PCA（默认: 1）
- `PCA_RABBITMQ_URL`: RabbitMQ连接URL（默认: `amqp://coverage:coverage123@localhost:5672/`）
- `PCA_FLUSH_INTERVAL`: 采集间隔（秒，默认: 60）
- `GITHUB_TOKEN` 或 `PCA_GITHUB_TOKEN`: GitHub Personal Access Token（可选，用于获取 repo_id，提升 API rate limit）

### GitHub Token 配置（可选）

PCA 会自动从 GitHub API 获取仓库的 `repo_id`。为了提升 API rate limit（从 60次/小时 提升到 5000次/小时），可以配置 GitHub Token：

#### 1. 创建 GitHub Personal Access Token

1. 访问 [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. 点击 "Generate new token (classic)"
3. 设置 token 名称和过期时间
4. 选择权限（至少需要 `public_repo` 权限来读取公开仓库信息）
5. 点击 "Generate token"
6. **重要**: 复制生成的 token（只显示一次）

#### 2. 设置环境变量

```bash
# 方式1: 使用 GITHUB_TOKEN（标准环境变量）
export GITHUB_TOKEN=your_github_personal_access_token

# 方式2: 使用 PCA_GITHUB_TOKEN（PCA 专用）
export PCA_GITHUB_TOKEN=your_github_personal_access_token
```

#### 3. 验证

设置 token 后，PCA 会在首次获取 repo_id 时使用认证请求，并缓存结果。后续上报将使用缓存的 repo_id，不会重复调用 API。

**注意**: 
- Token 是可选的，不设置也能正常工作（但可能遇到 rate limit）
- repo_id 会被缓存到 `~/.pca_repo_id_cache`，避免重复调用 API
- 如果遇到 rate limit 错误，设置 token 可以解决问题

### 示例

```bash
# 使用默认配置（RabbitMQ: amqp://coverage:coverage123@localhost:5672/, 间隔: 60秒）
python your_app.py

# 自定义配置（包含 GitHub Token）
export PCA_RABBITMQ_URL="amqp://user:pass@localhost:5672/"
export PCA_FLUSH_INTERVAL=30
export GITHUB_TOKEN=your_github_token
python your_app.py
```

## 工作原理

1. **启动钩子**: Python解释器启动时自动加载 `sitecustomize.py`
2. **初始化Agent**: 创建 `CoverageAgent` 实例并启动
3. **定时采集**: 每隔 `flush_interval` 秒执行一次采集流程：
   - `cov.stop()` - 停止覆盖率收集
   - 生成 coverage data
   - 提取 executed_lines
   - 行 → 区间压缩
   - 计算 fingerprint（区间级hash）
   - 对比上一次 fingerprint
   - 如果变化 → 上报到MQ
   - 更新 fingerprint
   - `cov.start()` - 继续覆盖率收集

## Fingerprint算法

- Python覆盖率是行级的，但最终转换成区间级
- 连续的覆盖行为一个区间（如：10-15行）
- 对每个文件的区间列表计算SHA256 hash
- 格式：`filename:start-end,start-end;filename:start-end,...`

## 上报协议

上报消息格式参考goc协议：

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
    "format": "pca",
    "raw": "mode: count\nfile.py:10.0,15.0 6 1\n..."
  },
  "timestamp": 1234567890
}
```

覆盖率原始数据格式（类似goc）：
```
mode: count
file.py:10.0,15.0 6 1
file.py:20.0,20.0 1 1
```

格式说明：
- `file.py:start_line.col,end_line.col statements count`
- `statements`: 区间内的语句数（end-start+1）
- `count`: 执行次数（1表示已覆盖）

## CLI工具

```bash
# 查看状态
pca status

# 测试agent
pca test
```

## 开发

```bash
# 安装开发版本
pip install -e .

# 运行测试
python -m pytest tests/
```

## 许可证

MIT License

