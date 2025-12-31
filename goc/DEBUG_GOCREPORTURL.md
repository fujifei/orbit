# 如何判断 gocReportURL 是否为空

## 问题描述

使用 `goc build --rabbitmq-url="$RABBITMQ_URL"` 编译后，服务启动后没有收到 MQ 消息。需要判断 `gocReportURL` 是否为空。

## 判断方法

### 方法1：查看服务启动日志（推荐）

服务启动时，会输出 `gocReportURL` 的状态：

**如果 gocReportURL 为空，会看到：**
```
[goc][WARN] gocReportURL is EMPTY - coverage reporting is DISABLED
[goc][WARN] To enable coverage reporting, use: goc build --rabbitmq-url=amqp://...
```

**如果 gocReportURL 已设置，会看到：**
```
[goc][INFO] gocReportURL is set: amqp://coverage:coverage123@localhost:5672/
[goc][INFO] Coverage reporting enabled to: amqp://coverage:coverage123@localhost:5672/
[goc][INFO] Git info: repo=..., repo_id=..., branch=..., commit=...
[goc][INFO] Started periodic coverage reporting (every 1 minute)
```

### 方法2：检查编译生成的代码文件

编译后会生成 `_cover_http_apis.go` 文件，检查其中的 `gocReportURL` 变量：

```bash
# 进入项目目录
cd your-project

# 查找 gocReportURL 的定义
grep "gocReportURL" _cover_http_apis.go
```

**如果为空，会看到：**
```go
gocReportURL  = ""  // HTTP endpoint for coverage reporting
```

**如果已设置，会看到：**
```go
gocReportURL  = "amqp://coverage:coverage123@localhost:5672/"  // HTTP endpoint for coverage reporting
```

### 方法3：使用诊断脚本

运行诊断脚本自动检查：

```bash
cd /path/to/goc
./diagnose_mq_reporting.sh
```

脚本会自动：
1. 检查编译生成的代码中 `gocReportURL` 的值
2. 启动测试服务并检查日志
3. 验证上报功能是否正常

## 常见问题

### Q1: 为什么 gocReportURL 为空？

**可能的原因：**
1. 编译时没有传递 `--rabbitmq-url` 参数
2. 使用了旧版本的 goc 工具（不支持该功能）
3. 环境变量 `$RABBITMQ_URL` 为空

**解决方案：**
```bash
# 确保传递了 --rabbitmq-url 参数
goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o myapp .

# 或者使用环境变量（确保变量不为空）
export RABBITMQ_URL="amqp://coverage:coverage123@localhost:5672/"
goc build --rabbitmq-url="$RABBITMQ_URL" -o myapp .
```

### Q2: 如何验证 gocReportURL 是否正确设置？

**步骤：**
1. 查看服务启动日志，确认看到 `gocReportURL is set: ...`
2. 查看是否看到 `Started periodic coverage reporting` 日志
3. 等待1分钟后，查看是否看到 `Successfully published coverage report (scheduled)` 日志

### Q3: gocReportURL 已设置但仍然没有收到消息？

**检查清单：**
1. ✅ RabbitMQ 服务是否正常运行？
   ```bash
   docker ps | grep rabbitmq
   curl -u coverage:coverage123 http://localhost:15672/api/overview
   ```

2. ✅ RabbitMQ URL 是否正确？
   - 格式：`amqp://user:pass@host:port/`
   - 确保用户名、密码、主机、端口都正确

3. ✅ 服务日志中是否有错误信息？
   ```bash
   # 查看服务日志，查找错误信息
   grep -i "error\|warn\|failed" your-service.log
   ```

4. ✅ 覆盖率数据是否为空？
   - 如果服务刚启动，可能还没有执行任何代码，覆盖率数据为空
   - 等待服务运行一段时间后再检查

## 调试日志说明

新增的调试日志会输出以下信息：

1. **启动时：**
   - `[goc][INFO] gocReportURL is set: ...` - URL 已设置
   - `[goc][WARN] gocReportURL is EMPTY` - URL 为空
   - `[goc][INFO] Started periodic coverage reporting` - 定时上报已启动

2. **定时上报时：**
   - `[goc][DEBUG] Timer ticked, collecting and reporting coverage...` - 定时器触发
   - `[goc][DEBUG] collectAndReportCoverageGoc: gocReportURL=...` - 开始收集覆盖率
   - `[goc][DEBUG] Coverage data collected: length=...` - 覆盖率数据已收集
   - `[goc][DEBUG] Publishing coverage report: ...` - 开始上报
   - `[goc][INFO] Successfully published coverage report (scheduled)` - 上报成功
   - `[goc][WARN] Failed to publish coverage report: ...` - 上报失败

3. **HTTP 请求时：**
   - `[goc][DEBUG] Creating HTTP POST request to: ...` - 创建 HTTP 请求
   - `[goc][DEBUG] Sending HTTP request...` - 发送请求
   - `[goc][DEBUG] HTTP response status: ...` - HTTP 响应状态码

## 快速检查命令

```bash
# 1. 检查编译后的代码
grep "gocReportURL" _cover_http_apis.go

# 2. 启动服务并查看日志
./your-app 2>&1 | grep -i "gocReportURL\|coverage reporting"

# 3. 检查是否有上报日志
tail -f your-service.log | grep -i "published\|failed\|gocReportURL"
```

