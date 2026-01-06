#!/bin/bash

# Coverage Adapter启动脚本

# 设置默认值
RABBITMQ_URL="${COVERAGE_ADAPTER_RABBITMQ_URL:-amqp://coverage:coverage123@localhost:5672/}"
FLUSH_INTERVAL="${COVERAGE_ADAPTER_FLUSH_INTERVAL:-60}"
JACOCO_ADDRESS="${COVERAGE_ADAPTER_JACOCO_ADDRESS:-localhost}"
JACOCO_PORT="${COVERAGE_ADAPTER_JACOCO_PORT:-6300}"
JACOCO_CLI_JAR="${COVERAGE_ADAPTER_JACOCO_CLI_JAR:-./jacoco/lib/jacococli.jar}"
JACOCO_EXEC_FILE="${COVERAGE_ADAPTER_JACOCO_EXEC_FILE:-./jacoco.exec}"
JACOCO_CLASSFILES="${COVERAGE_ADAPTER_JACOCO_CLASSFILES}"
FINGERPRINT_FILE="${COVERAGE_ADAPTER_FINGERPRINT_FILE:-~/.coverage_adapter_fingerprint}"

# 检查必需参数
if [ -z "$JACOCO_CLASSFILES" ]; then
    echo "Error: COVERAGE_ADAPTER_JACOCO_CLASSFILES is required"
    echo "Please set COVERAGE_ADAPTER_JACOCO_CLASSFILES environment variable"
    exit 1
fi

# 查找JAR文件
JAR_FILE=""
if [ -f "target/coverage-adapter-1.0.0.jar" ]; then
    JAR_FILE="target/coverage-adapter-1.0.0.jar"
elif [ -f "coverage-adapter-1.0.0.jar" ]; then
    JAR_FILE="coverage-adapter-1.0.0.jar"
else
    echo "Error: coverage-adapter-1.0.0.jar not found"
    echo "Please build the project first: mvn clean package"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 启动服务
echo "Starting Coverage Adapter..."
echo "  RabbitMQ URL: $RABBITMQ_URL"
echo "  Flush interval: ${FLUSH_INTERVAL}s"
echo "  JaCoCo address: $JACOCO_ADDRESS:$JACOCO_PORT"
echo "  JaCoCo CLI jar: $JACOCO_CLI_JAR"
echo "  JaCoCo exec file: $JACOCO_EXEC_FILE"
echo "  JaCoCo classfiles: $JACOCO_CLASSFILES"
echo "  Fingerprint file: $FINGERPRINT_FILE"

java -jar "$JAR_FILE" \
    --rabbitmq-url "$RABBITMQ_URL" \
    --flush-interval "$FLUSH_INTERVAL" \
    --jacoco-address "$JACOCO_ADDRESS" \
    --jacoco-port "$JACOCO_PORT" \
    --jacoco-cli-jar "$JACOCO_CLI_JAR" \
    --jacoco-exec-file "$JACOCO_EXEC_FILE" \
    --jacoco-classfiles "$JACOCO_CLASSFILES" \
    --fingerprint-file "$FINGERPRINT_FILE"

