# Simple MQ App - Goc Build with RabbitMQ Reporting Example

这是一个简单的示例应用，演示如何使用 `goc build --rabbitmq-url` 功能。

## 快速开始

### 1. 启动 RabbitMQ

```bash
cd ../../coverage-platform/docker/rabbitmq
docker-compose up -d
```

### 2. 编译应用（带 MQ 上报功能）

```bash
# 回到示例目录
cd -

# 使用 goc build 编译，指定 RabbitMQ URL
goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o simple-mq-app .
```

### 3. 运行应用

```bash
./simple-mq-app
```

应该看到类似输出：
```
[goc][INFO] Coverage reporting enabled to: amqp://coverage:***@localhost:5672/
[goc][INFO] Git info: repo=github.com/qiniu/goc, branch=main, commit=abc123
Server starting on port 8080
```

### 4. 访问应用（产生覆盖率数据）

```bash
# 访问不同的端点
curl http://localhost:8080/
curl http://localhost:8080/add
curl http://localhost:8080/multiply
```

### 5. 触发覆盖率上报

```bash
curl http://localhost:7777/v1/cover/profile
```

应该看到应用日志输出：
```
[goc][INFO] Successfully published coverage report
[goc][DEBUG] Coverage report published: repo=github.com/qiniu/goc, branch=main, commit=abc123
```

### 6. 查看 RabbitMQ 中的消息

访问 RabbitMQ Management UI:
```
http://localhost:15672
用户名: coverage
密码: coverage123
```

在 "Queues" 页面可以看到收到的覆盖率报告消息。

## 测试不同的配置

### 使用自定义服务名称

```bash
GOC_SERVICE_NAME=my-test-app ./simple-mq-app
```

### 使用自定义端口

```bash
PORT=9090 ./simple-mq-app
```

### 使用 HTTP Webhook（而不是 RabbitMQ）

```bash
# 编译时指定 HTTP endpoint
goc build --rabbitmq-url=http://your-webhook.com/coverage -o simple-mq-app .

# 运行
./simple-mq-app
```

## 清理

```bash
# 停止应用
# Ctrl+C

# 停止 RabbitMQ
cd ../../coverage-platform/docker/rabbitmq
docker-compose down
```


