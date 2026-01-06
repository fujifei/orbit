# Coverage Adapter (Java)

Java覆盖率适配器服务，用于从JaCoCo agent获取覆盖率数据并上报到MQ。

## 功能特性

1. **对业务代码无侵入**：可以作为Java Agent与被测服务一起启动，也可以作为独立服务运行
2. **定时采集覆盖率数据**：通过JaCoCo CLI工具定时dump覆盖率数据（默认60秒）
3. **解析覆盖率文件**：解析jacoco.exec文件，提取行级覆盖率信息
4. **行级转区间级**：将Java的行级覆盖率转换为区间级覆盖率
5. **Fingerprint算法**：使用SHA256算法计算覆盖率指纹，仅在覆盖率变化时上报
6. **上报到MQ**：将覆盖率数据上报到RabbitMQ

## 构建

```bash
cd coverage-adapter-java
mvn clean package
```

构建完成后，会在 `target/` 目录下生成 `coverage-adapter-1.0.0.jar` 文件。

## 配置

### 环境变量

- `COVERAGE_ADAPTER_RABBITMQ_URL`: RabbitMQ连接URL（默认：`amqp://coverage:coverage123@localhost:5672/`）
- `COVERAGE_ADAPTER_FLUSH_INTERVAL`: 采集间隔（秒，默认：60）
- `COVERAGE_ADAPTER_JACOCO_ADDRESS`: JaCoCo agent地址（默认：localhost）
- `COVERAGE_ADAPTER_JACOCO_PORT`: JaCoCo agent端口（默认：6300）
- `COVERAGE_ADAPTER_JACOCO_CLI_JAR`: jacococli.jar路径（默认：`./jacoco/lib/jacococli.jar`）
- `COVERAGE_ADAPTER_JACOCO_EXEC_FILE`: jacoco.exec文件路径（默认：`./jacoco.exec`）
- `COVERAGE_ADAPTER_JACOCO_CLASSFILES`: Java class文件路径（必需）
- `COVERAGE_ADAPTER_FINGERPRINT_FILE`: fingerprint存储文件路径（默认：`~/.coverage_adapter_fingerprint`）

### 命令行参数

```bash
java -jar coverage-adapter-1.0.0.jar --help
```

支持的参数：
- `--rabbitmq-url`: RabbitMQ连接URL
- `--flush-interval`: 采集间隔（秒）
- `--jacoco-address`: JaCoCo agent地址
- `--jacoco-port`: JaCoCo agent端口
- `--jacoco-cli-jar`: jacococli.jar路径
- `--jacoco-exec-file`: jacoco.exec文件路径
- `--jacoco-classfiles`: Java class文件路径（必需）
- `--fingerprint-file`: fingerprint文件路径

## 使用方法

Coverage Adapter支持两种启动方式：

### 方式一：作为Java Agent启动（推荐）

**与被测服务一起启动，无需单独启动Coverage Adapter服务**

被测服务同时使用JaCoCo agent和Coverage Adapter agent：

```bash
java \
  -javaagent:jacoco/lib/jacocoagent.jar=output=tcpserver,address=localhost,port=6300 \
  -javaagent:coverage-adapter-1.0.0.jar=rabbitmq-url=amqp://coverage:coverage123@localhost:5672/,flush-interval=60,jacoco-address=localhost,jacoco-port=6300,jacoco-cli-jar=./jacoco/lib/jacococli.jar,jacoco-exec-file=./jacoco.exec,jacoco-classfiles=./target/classes \
  -jar your-app.jar
```

或者使用环境变量（更简洁）：

```bash
export COVERAGE_ADAPTER_RABBITMQ_URL="amqp://coverage:coverage123@localhost:5672/"
export COVERAGE_ADAPTER_FLUSH_INTERVAL=60
export COVERAGE_ADAPTER_JACOCO_ADDRESS=localhost
export COVERAGE_ADAPTER_JACOCO_PORT=6300
export COVERAGE_ADAPTER_JACOCO_CLI_JAR="./jacoco/lib/jacococli.jar"
export COVERAGE_ADAPTER_JACOCO_EXEC_FILE="./jacoco.exec"
export COVERAGE_ADAPTER_JACOCO_CLASSFILES="./target/classes"

java \
  -javaagent:jacoco/lib/jacocoagent.jar=output=tcpserver,address=localhost,port=6300 \
  -javaagent:coverage-adapter-1.0.0.jar \
  -jar your-app.jar
```

**Agent参数说明**（格式：`key1=value1,key2=value2,...`）：
- `rabbitmq-url`: RabbitMQ连接URL
- `flush-interval`: 采集间隔（秒）
- `jacoco-address`: JaCoCo agent地址
- `jacoco-port`: JaCoCo agent端口
- `jacoco-cli-jar`: jacococli.jar路径
- `jacoco-exec-file`: jacoco.exec文件路径
- `jacoco-classfiles`: Java class文件路径（必需）
- `fingerprint-file`: fingerprint文件路径

### 方式二：作为独立服务启动

**需要单独启动Coverage Adapter服务**

1. 启动被测服务（使用JaCoCo agent）：

```bash
java -javaagent:jacoco/lib/jacocoagent.jar=output=tcpserver,address=localhost,port=6300 \
     -jar your-app.jar
```

2. 启动Coverage Adapter服务：

```bash
java -jar coverage-adapter-1.0.0.jar \
    --rabbitmq-url amqp://coverage:coverage123@localhost:5672/ \
    --flush-interval 60 \
    --jacoco-address localhost \
    --jacoco-port 6300 \
    --jacoco-cli-jar ./jacoco/lib/jacococli.jar \
    --jacoco-exec-file ./jacoco.exec \
    --jacoco-classfiles ./target/classes
```

或者使用环境变量：

```bash
export COVERAGE_ADAPTER_RABBITMQ_URL="amqp://coverage:coverage123@localhost:5672/"
export COVERAGE_ADAPTER_FLUSH_INTERVAL=60
export COVERAGE_ADAPTER_JACOCO_ADDRESS=localhost
export COVERAGE_ADAPTER_JACOCO_PORT=6300
export COVERAGE_ADAPTER_JACOCO_CLI_JAR="./jacoco/lib/jacococli.jar"
export COVERAGE_ADAPTER_JACOCO_EXEC_FILE="./jacoco.exec"
export COVERAGE_ADAPTER_JACOCO_CLASSFILES="./target/classes"

java -jar coverage-adapter-1.0.0.jar
```

## 工作原理

1. **定时采集**：每隔指定间隔（默认60秒），执行以下操作：
   - 执行 `java -jar jacococli.jar dump --address localhost --port 6300 --destfile jacoco.exec` 获取覆盖率数据
   - 执行 `java -jar jacococli.jar report jacoco.exec --classfiles <classfiles> --xml temp.xml` 生成XML报告
   - 解析XML报告，提取行级覆盖率信息

2. **行级转区间级**：
   - 收集所有被覆盖的行号
   - 将连续的行号压缩为区间（例如：[10, 11, 12, 15, 16] → [(10, 12), (15, 16)]）

3. **Fingerprint计算**：
   - 对每个文件的覆盖率区间进行排序
   - 构建字符串：`filename:start-end,start-end;filename:start-end,...`
   - 使用SHA256计算hash值

4. **变化检测**：
   - 比较当前fingerprint与上次保存的fingerprint
   - 如果相同，打印日志并跳过上报
   - 如果不同，上报覆盖率数据

5. **格式化**：将区间级覆盖率格式化为goc格式：
   ```
   mode: count
   com/example/MyClass.java:10.0,12.0 3 1
   com/example/MyClass.java:15.0,16.0 2 1
   ```

6. **上报到MQ**：将格式化后的覆盖率数据上报到RabbitMQ，消息格式：
   ```json
   {
     "repo": "github.com/example/repo",
     "repo_id": "...",
     "branch": "main",
     "commit": "...",
     "ci": {
       "provider": "gitlab",
       "pipeline_id": "...",
       "job_id": "..."
     },
     "coverage": {
       "format": "jacoco",
       "raw": "mode: count\n..."
     },
     "timestamp": 1234567890
   }
   ```

## 覆盖率数据格式

Coverage Adapter生成的覆盖率数据格式与goc格式相同：

```
mode: count
file.java:startLine.startCol,endLine.endCol statements count
```

- `file.java`: 文件路径（相对于项目根目录）
- `startLine.startCol`: 区间起始行号和列号
- `endLine.endCol`: 区间结束行号和列号
- `statements`: 该区间包含的语句数
- `count`: 执行次数（覆盖的行，count=1；未覆盖的行，count=0）

## 注意事项

1. **JaCoCo agent配置**：确保被测服务使用TCP server模式启动JaCoCo agent
2. **网络连接**：如果使用独立服务模式，确保Coverage Adapter能够连接到JaCoCo agent的TCP端口
3. **Java环境**：确保系统已安装Java 11或更高版本，并且能够执行`java -jar`命令
4. **jacococli.jar**：确保jacococli.jar文件存在且可访问
5. **Git信息**：Coverage Adapter会自动检测Git信息（repo、branch、commit），如果不在Git仓库中，这些字段可能为空
6. **对业务代码无侵入**：Coverage Adapter作为Java Agent或独立服务运行，不需要修改被测服务代码
7. **推荐使用Java Agent模式**：与被测服务一起启动，更简单方便，无需单独管理Coverage Adapter进程

## 故障排查

### 1. 无法连接到JaCoCo agent

检查：
- JaCoCo agent是否已启动
- 地址和端口是否正确
- 防火墙是否阻止连接

### 2. jacococli.jar执行失败

检查：
- Java环境是否正确安装
- jacococli.jar路径是否正确
- 文件权限是否正确

### 3. 覆盖率数据为空

检查：
- 被测服务是否正在运行
- 是否有代码被执行
- JaCoCo agent是否正确配置

### 4. Fingerprint未变化但覆盖率变化

检查：
- Fingerprint算法是否正确计算
- Fingerprint文件是否被正确保存和加载

## 项目结构

```
coverage-adapter-java/
├── pom.xml
├── README.md
├── start.sh
└── src/
    └── main/
        ├── java/
        │   └── com/
        │       └── coverage/
        │           └── adapter/
        │               ├── CoverageAdapter.java          # 主类
        │               ├── agent/
        │               │   └── CoverageAdapterAgent.java # 核心代理类
        │               ├── jacoco/
        │               │   └── JaCoCoClient.java         # JaCoCo客户端
        │               ├── mq/
        │               │   └── RabbitMQPublisher.java    # RabbitMQ发布器
        │               ├── git/
        │               │   ├── GitInfo.java             # Git信息模型
        │               │   └── GitInfoCollector.java     # Git信息收集器
        │               ├── model/
        │               │   ├── CoverageData.java        # 覆盖率数据模型
        │               │   └── CoverageRange.java        # 覆盖率区间模型
        │               └── util/
        │                   └── FingerprintCalculator.java # Fingerprint计算器
        └── resources/
            └── logback.xml                              # 日志配置
```

## License

MIT License

