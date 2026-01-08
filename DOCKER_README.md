# Docker Compose 部署指南

本文档说明如何使用 Docker Compose 启动 Orbit 覆盖率平台的所有服务。

## 服务列表

- **MySQL**: 数据库服务（端口 3306）
- **RabbitMQ**: 消息队列服务（端口 5672，管理界面 15672）
- **coverage-api**: 覆盖率 API 服务（端口 8826）
- **coverage-consumer**: 覆盖率消息消费者服务
- **coverage-fe**: 前端服务（端口 3000）

## 快速开始

### 1. 启动所有服务

```bash
# 在 orbit 根目录下执行
docker-compose up -d
```

### 2. 查看服务状态

```bash
docker-compose ps
```

### 3. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f coverage-api
docker-compose logs -f coverage-consumer
docker-compose logs -f coverage-fe
```

### 4. 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止服务并删除数据卷（注意：会删除数据库数据）
docker-compose down -v
```

## 服务访问地址

- **前端界面**: http://localhost:3000
- **API 服务**: http://localhost:8826
- **RabbitMQ 管理界面**: http://localhost:15672
  - 用户名: `coverage`
  - 密码: `coverage123`

## 环境变量配置

可以通过修改 `docker-compose.yml` 中的环境变量来配置服务：

### MySQL 配置
- `MYSQL_ROOT_PASSWORD`: root 用户密码（默认: root123）
- `MYSQL_DATABASE`: 数据库名称（默认: coverage_db）
- `MYSQL_USER`: 数据库用户（默认: coverage）
- `MYSQL_PASSWORD`: 数据库密码（默认: coverage123）

### RabbitMQ 配置
- `RABBITMQ_DEFAULT_USER`: RabbitMQ 用户名（默认: coverage）
- `RABBITMQ_DEFAULT_PASS`: RabbitMQ 密码（默认: coverage123）

### 应用服务配置
- `DB_HOST`: 数据库主机（默认: mysql）
- `DB_PORT`: 数据库端口（默认: 3306）
- `DB_USER`: 数据库用户（默认: coverage）
- `DB_PASSWORD`: 数据库密码（默认: coverage123）
- `DB_NAME`: 数据库名称（默认: coverage_db）
- `RABBITMQ_HOST`: RabbitMQ 主机（默认: rabbitmq）
- `RABBITMQ_PORT`: RabbitMQ 端口（默认: 5672）
- `RABBITMQ_USER`: RabbitMQ 用户名（默认: coverage）
- `RABBITMQ_PASSWORD`: RabbitMQ 密码（默认: coverage123）

## 数据持久化

以下数据会持久化到 Docker volumes：

- `mysql_data`: MySQL 数据文件
- `rabbitmq_data`: RabbitMQ 数据文件
- `./coverage-platform/logs`: 应用日志目录
- `./coverage-platform/repos`: 代码仓库目录

## 服务依赖关系

服务启动顺序由 `depends_on` 配置自动管理：

1. MySQL 和 RabbitMQ 首先启动并等待健康检查通过
2. coverage-api 等待 MySQL 和 RabbitMQ 就绪后启动
3. coverage-consumer 等待所有依赖服务就绪后启动
4. coverage-fe 等待 coverage-api 就绪后启动

## 故障排查

### 1. 服务无法启动

检查服务日志：
```bash
docker-compose logs <service-name>
```

### 2. 数据库连接失败

确保 MySQL 服务已启动并健康：
```bash
docker-compose ps mysql
docker-compose logs mysql
```

### 3. RabbitMQ 连接失败

确保 RabbitMQ 服务已启动并健康：
```bash
docker-compose ps rabbitmq
docker-compose logs rabbitmq
```

### 4. 前端无法访问 API

检查前端和 API 服务是否都在运行：
```bash
docker-compose ps
```

前端通过 nginx 代理 `/api` 请求到 `coverage-api` 服务。

### 5. 重建服务

如果需要重新构建镜像：
```bash
docker-compose build
docker-compose up -d
```

## 开发模式

如果需要修改代码后重新部署：

```bash
# 停止服务
docker-compose down

# 重新构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

## 生产环境建议

在生产环境中，建议：

1. 修改所有默认密码
2. 使用环境变量文件（`.env`）管理敏感信息
3. 配置 SSL/TLS 证书
4. 设置适当的资源限制
5. 配置日志轮转
6. 使用外部数据库和消息队列（如果可能）

## 注意事项

1. 首次启动时，数据库表结构会由 SQLAlchemy 自动创建
2. 确保端口 3000、3306、5672、8826、15672 未被占用
3. 前端服务使用 nginx 代理 API 请求，无需额外配置
4. 所有服务都配置了健康检查，确保服务正常启动

