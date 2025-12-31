# 快速开始：Goc Build with MQ Reporting

## 5 分钟快速上手

### 前置条件

1. 安装 Go (1.16+)
2. 安装 Docker 和 Docker Compose
3. 安装 goc 工具

```bash
go install github.com/qiniu/goc@latest
```

### 步骤 1: 启动 RabbitMQ

```bash
cd coverage-platform/docker/rabbitmq
docker-compose up -d
```

等待 10 秒让 RabbitMQ 完全启动。

### 步骤 2: 编译你的应用

在你的 Go 项目目录中运行：

```bash
goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o myapp .
```

**就这么简单！** 你的应用现在已经包含了覆盖率收集和 MQ 上报功能。

### 步骤 3: 运行应用

```bash
./myapp
```

你会看到类似的输出：

```
[goc][INFO] Coverage reporting enabled to: amqp://coverage:***@localhost:5672/
[goc][INFO] Git info: repo=github.com/your/project, branch=main, commit=abc123
Server starting...
```

### 步骤 4: 使用你的应用

正常使用你的应用，执行测试或访问功能：

```bash
# 例如，如果是 HTTP 服务
curl http://localhost:8080/api/users
curl http://localhost:8080/api/products
```

### 步骤 5: 获取覆盖率报告

访问内置的覆盖率端点：

```bash
curl http://localhost:7777/v1/cover/profile
```

**自动完成！** 覆盖率数据会：
1. 在 HTTP 响应中返回
2. 自动发送到 RabbitMQ
3. 包含完整的 Git 和 CI 信息

### 步骤 6: 查看 RabbitMQ 中的数据

打开浏览器访问：

```
http://localhost:15672
用户名: coverage
密码: coverage123
```

在 "Queues" 标签页可以看到收到的覆盖率报告。

## 完成！

就是这么简单。你现在已经有了：

✅ 自动覆盖率收集
✅ 自动 MQ 上报
✅ Git 信息追踪
✅ CI 信息追踪
✅ 无需额外的 wrapper 或代理

## 下一步

### 在 CI/CD 中使用

在你的 CI 配置文件中（例如 `.gitlab-ci.yml`）：

```yaml
test:
  script:
    - goc build --rabbitmq-url=amqp://coverage:coverage123@rabbitmq-server:5672/ -o myapp .
    - ./myapp &
    - run_tests.sh
    - curl http://localhost:7777/v1/cover/profile
```

### 自定义配置

#### 使用自定义服务名称

```bash
GOC_SERVICE_NAME=my-service ./myapp
```

#### 使用 HTTP Webhook 而不是 RabbitMQ

```bash
goc build --rabbitmq-url=http://your-webhook.com/coverage -o myapp .
```

#### 同时支持 goc server

```bash
goc build --center=http://goc-server:7777 --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o myapp .
```

## 常见问题

### Q: 如果我不想使用 MQ 上报怎么办？

A: 不指定 `--rabbitmq-url` 参数即可，行为与原来完全一致。

### Q: MQ 连接失败会影响服务运行吗？

A: 不会。上报失败只会记录警告日志，不影响服务正常运行。

### Q: 可以在运行时更改 MQ URL 吗？

A: 不可以。MQ URL 在编译时确定。如需更改，请重新编译。

### Q: 支持哪些 CI 系统？

A: 自动支持 GitLab CI、Jenkins、GitHub Actions、CircleCI。

## 更多信息

- 详细文档：[GOC_BUILD_MQ_REPORTING.md](GOC_BUILD_MQ_REPORTING.md)
- 完整示例：[examples/simple-mq-app/](examples/simple-mq-app/)
- 变更日志：[CHANGELOG_MQ_ENHANCEMENT.md](CHANGELOG_MQ_ENHANCEMENT.md)

## 获取帮助

```bash
goc build --help
```

查看所有可用参数。

