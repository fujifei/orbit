# RabbitMQ Docker 部署

## 快速启动

```bash
cd docker/rabbitmq
docker-compose up -d
```

## 访问管理界面

- URL: http://localhost:15672
- 用户名: coverage
- 密码: coverage123

## 停止服务

```bash
docker-compose down
```

## 查看日志

```bash
docker-compose logs -f rabbitmq
```

## 连接信息

- Host: localhost
- Port: 5672
- Username: coverage
- Password: coverage123
- VHost: /

## 队列配置

默认会创建以下队列和交换机（由consumer服务自动创建）：
- Exchange: coverage_exchange
- Queue: coverage_queue
- Routing Key: coverage.report

