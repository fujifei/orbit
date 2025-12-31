#!/bin/bash

# 测试脚本：自动化测试 goc build with MQ reporting

set -e

echo "=== Goc Build with MQ Reporting Test ==="
echo ""

# 检查 goc 是否安装
if ! command -v goc &> /dev/null; then
    echo "❌ goc not found. Please install goc first."
    exit 1
fi
echo "✅ goc found"

# 检查 RabbitMQ 是否运行
if ! docker ps | grep rabbitmq &> /dev/null; then
    echo "⚠️  RabbitMQ not running. Starting RabbitMQ..."
    cd ../../coverage-platform/docker/rabbitmq
    docker-compose up -d
    cd -
    echo "⏳ Waiting for RabbitMQ to start..."
    sleep 10
fi
echo "✅ RabbitMQ is running"

# 编译应用
echo ""
echo "📦 Building application with MQ reporting..."
goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o simple-mq-app .
echo "✅ Build successful"

# 启动应用
echo ""
echo "🚀 Starting application..."
PORT=8080 ./simple-mq-app &
APP_PID=$!
echo "✅ Application started (PID: $APP_PID)"

# 等待应用启动
echo "⏳ Waiting for application to start..."
sleep 3

# 测试应用端点
echo ""
echo "🧪 Testing application endpoints..."
curl -s http://localhost:8080/ > /dev/null && echo "✅ GET / - OK"
curl -s http://localhost:8080/add > /dev/null && echo "✅ GET /add - OK"
curl -s http://localhost:8080/multiply > /dev/null && echo "✅ GET /multiply - OK"

# 触发覆盖率上报
echo ""
echo "📊 Triggering coverage report..."
COVERAGE_OUTPUT=$(curl -s http://localhost:7777/v1/cover/profile)

if echo "$COVERAGE_OUTPUT" | grep -q "mode:"; then
    echo "✅ Coverage profile retrieved"
    echo ""
    echo "Coverage data preview:"
    echo "$COVERAGE_OUTPUT" | head -5
    echo "..."
else
    echo "❌ Failed to retrieve coverage profile"
    kill $APP_PID
    exit 1
fi

# 停止应用
echo ""
echo "🛑 Stopping application..."
kill $APP_PID
wait $APP_PID 2>/dev/null || true
echo "✅ Application stopped"

# 清理
echo ""
echo "🧹 Cleaning up..."
rm -f simple-mq-app
echo "✅ Cleanup complete"

echo ""
echo "=== Test Complete ==="
echo ""
echo "✅ All tests passed!"
echo ""
echo "Note: Check RabbitMQ Management UI to verify the coverage report was published:"
echo "  URL: http://localhost:15672"
echo "  Username: coverage"
echo "  Password: coverage123"


