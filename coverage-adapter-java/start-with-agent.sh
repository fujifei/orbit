#!/bin/bash

# 使用Java Agent模式启动被测服务的示例脚本
# 这个脚本展示如何将被测服务和Coverage Adapter一起启动

# 设置Coverage Adapter配置（可以通过环境变量或agent参数传递）
export COVERAGE_ADAPTER_RABBITMQ_URL="${COVERAGE_ADAPTER_RABBITMQ_URL:-amqp://coverage:coverage123@localhost:5672/}"
export COVERAGE_ADAPTER_FLUSH_INTERVAL="${COVERAGE_ADAPTER_FLUSH_INTERVAL:-60}"
export COVERAGE_ADAPTER_JACOCO_ADDRESS="${COVERAGE_ADAPTER_JACOCO_ADDRESS:-localhost}"
export COVERAGE_ADAPTER_JACOCO_PORT="${COVERAGE_ADAPTER_JACOCO_PORT:-6300}"
export COVERAGE_ADAPTER_JACOCO_CLI_JAR="${COVERAGE_ADAPTER_JACOCO_CLI_JAR:-./jacoco/lib/jacococli.jar}"
export COVERAGE_ADAPTER_JACOCO_EXEC_FILE="${COVERAGE_ADAPTER_JACOCO_EXEC_FILE:-./jacoco.exec}"
export COVERAGE_ADAPTER_JACOCO_CLASSFILES="${COVERAGE_ADAPTER_JACOCO_CLASSFILES}"
export COVERAGE_ADAPTER_FINGERPRINT_FILE="${COVERAGE_ADAPTER_FINGERPRINT_FILE:-~/.coverage_adapter_fingerprint}"

# 检查必需参数
if [ -z "$COVERAGE_ADAPTER_JACOCO_CLASSFILES" ]; then
    echo "Error: COVERAGE_ADAPTER_JACOCO_CLASSFILES is required"
    echo "Please set COVERAGE_ADAPTER_JACOCO_CLASSFILES environment variable"
    exit 1
fi

# 查找JAR文件
COVERAGE_ADAPTER_JAR=""
if [ -f "target/coverage-adapter-1.0.0.jar" ]; then
    COVERAGE_ADAPTER_JAR="target/coverage-adapter-1.0.0.jar"
elif [ -f "coverage-adapter-1.0.0.jar" ]; then
    COVERAGE_ADAPTER_JAR="coverage-adapter-1.0.0.jar"
elif [ -f "../coverage-adapter-java/target/coverage-adapter-1.0.0.jar" ]; then
    COVERAGE_ADAPTER_JAR="../coverage-adapter-java/target/coverage-adapter-1.0.0.jar"
else
    echo "Error: coverage-adapter-1.0.0.jar not found"
    echo "Please build the project first: cd coverage-adapter-java && mvn clean package"
    exit 1
fi

# 查找JaCoCo agent JAR
JACOCO_AGENT_JAR=""
if [ -f "jacoco/lib/jacocoagent.jar" ]; then
    JACOCO_AGENT_JAR="jacoco/lib/jacocoagent.jar"
elif [ -f "./jacoco/lib/jacocoagent.jar" ]; then
    JACOCO_AGENT_JAR="./jacoco/lib/jacocoagent.jar"
else
    echo "Error: jacocoagent.jar not found"
    echo "Please ensure jacocoagent.jar exists in jacoco/lib/"
    exit 1
fi

# 被测服务JAR（需要根据实际情况修改）
TARGET_APP_JAR="${1:-your-app.jar}"

if [ ! -f "$TARGET_APP_JAR" ]; then
    echo "Error: Target application JAR not found: $TARGET_APP_JAR"
    echo "Usage: $0 <target-app.jar>"
    exit 1
fi

# 创建日志目录
mkdir -p logs

echo "Starting application with Coverage Adapter Agent..."
echo "  Target app: $TARGET_APP_JAR"
echo "  JaCoCo agent: $JACOCO_AGENT_JAR"
echo "  Coverage Adapter: $COVERAGE_ADAPTER_JAR"
echo "  RabbitMQ URL: $COVERAGE_ADAPTER_RABBITMQ_URL"
echo "  Flush interval: ${COVERAGE_ADAPTER_FLUSH_INTERVAL}s"
echo "  JaCoCo address: $COVERAGE_ADAPTER_JACOCO_ADDRESS:$COVERAGE_ADAPTER_JACOCO_PORT"
echo "  JaCoCo classfiles: $COVERAGE_ADAPTER_JACOCO_CLASSFILES"

# 启动被测服务（同时启动JaCoCo agent和Coverage Adapter agent）
java \
  -javaagent:"$JACOCO_AGENT_JAR"=output=tcpserver,address="$COVERAGE_ADAPTER_JACOCO_ADDRESS",port="$COVERAGE_ADAPTER_JACOCO_PORT" \
  -javaagent:"$COVERAGE_ADAPTER_JAR" \
  -jar "$TARGET_APP_JAR"

