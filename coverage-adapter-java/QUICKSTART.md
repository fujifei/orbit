# Coverage Adapter 快速开始

## 方式一：Java Agent模式（推荐）

**与被测服务一起启动，最简单方便**

### 1. 构建项目

```bash
cd coverage-adapter-java
mvn clean package
```

### 2. 启动被测服务（同时启动Coverage Adapter）

```bash
# 设置环境变量
export COVERAGE_ADAPTER_RABBITMQ_URL="amqp://coverage:coverage123@localhost:5672/"
export COVERAGE_ADAPTER_JACOCO_CLASSFILES="./target/classes"

# 启动被测服务（同时启动Coverage Adapter）
# 如果从orbit根目录运行，使用：coverage-adapter-java/target/coverage-adapter-1.0.0.jar
# 如果从coverage-adapter-java目录运行，使用：target/coverage-adapter-1.0.0.jar
java \
  -javaagent:jacoco/lib/jacocoagent.jar=output=tcpserver,address=localhost,port=6300 \
  -javaagent:coverage-adapter-java/target/coverage-adapter-1.0.0.jar \
  -jar your-app.jar
```

### 3. 验证

查看日志文件 `logs/adapter.log`，应该能看到Coverage Adapter启动和采集覆盖率的日志。

## 方式二：独立服务模式

**需要单独启动Coverage Adapter服务**

### 1. 构建项目

```bash
cd coverage-adapter-java
mvn clean package
```

### 2. 启动被测服务

```bash
java -javaagent:jacoco/lib/jacocoagent.jar=output=tcpserver,address=localhost,port=6300 \
     -jar your-app.jar
```

### 3. 启动Coverage Adapter服务

```bash
cd coverage-adapter-java
export COVERAGE_ADAPTER_JACOCO_CLASSFILES="./target/classes"
./start.sh
```

或者直接使用java命令：

```bash
java -jar target/coverage-adapter-1.0.0.jar \
    --rabbitmq-url amqp://coverage:coverage123@localhost:5672/ \
    --jacoco-classfiles ./target/classes
```

## 配置说明

### 必需配置

- `COVERAGE_ADAPTER_JACOCO_CLASSFILES` 或 `--jacoco-classfiles`: Java class文件路径

### 可选配置（有默认值）

- `COVERAGE_ADAPTER_RABBITMQ_URL`: RabbitMQ连接URL（默认：`amqp://coverage:coverage123@localhost:5672/`）
- `COVERAGE_ADAPTER_FLUSH_INTERVAL`: 采集间隔（秒，默认：60）
- `COVERAGE_ADAPTER_JACOCO_ADDRESS`: JaCoCo agent地址（默认：localhost）
- `COVERAGE_ADAPTER_JACOCO_PORT`: JaCoCo agent端口（默认：6300）
- `COVERAGE_ADAPTER_JACOCO_CLI_JAR`: jacococli.jar路径（默认：`./jacoco/lib/jacococli.jar`）
- `COVERAGE_ADAPTER_JACOCO_EXEC_FILE`: jacoco.exec文件路径（默认：`./jacoco.exec`）

## 常见问题

### Q: 如何确认Coverage Adapter是否正常工作？

A: 查看日志文件 `logs/adapter.log`，应该能看到：
- "Coverage Adapter Agent started successfully" 或 "CoverageAdapterAgent started"
- 每60秒（或配置的间隔）会有覆盖率采集和上报的日志

### Q: 覆盖率数据没有上报？

A: 检查：
1. RabbitMQ是否正常运行
2. RabbitMQ URL配置是否正确
3. 覆盖率数据是否有变化（如果fingerprint未变化，不会上报，只会打印日志）

### Q: 使用Java Agent模式时，如何传递配置？

A: 有两种方式：
1. 通过agent参数：`-javaagent:coverage-adapter.jar=key1=value1,key2=value2`
2. 通过环境变量：`export COVERAGE_ADAPTER_XXX=value`，然后在agent参数中不指定该参数

### Q: 可以同时使用多个Java Agent吗？

A: 可以，JaCoCo agent和Coverage Adapter agent可以同时使用：
```bash
java \
  -javaagent:jacoco/lib/jacocoagent.jar=... \
  -javaagent:coverage-adapter-1.0.0.jar=... \
  -jar your-app.jar
```

