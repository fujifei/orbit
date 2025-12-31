#!/bin/bash

# RabbitMQ覆盖率上报诊断脚本

echo "=========================================="
echo "RabbitMQ覆盖率上报诊断"
echo "=========================================="
echo ""

# 1. 检查RabbitMQ服务状态
echo "1. 检查RabbitMQ服务状态..."
if docker ps | grep -q coverage-rabbitmq; then
    echo "   ✓ RabbitMQ服务正在运行"
    docker ps | grep coverage-rabbitmq
else
    echo "   ✗ RabbitMQ服务未运行"
    echo "   请运行: cd docker/rabbitmq && docker-compose up -d"
    exit 1
fi
echo ""

# 2. 检查Exchange
echo "2. 检查Exchange..."
EXCHANGE=$(docker exec coverage-rabbitmq rabbitmqctl list_exchanges name type | grep coverage_exchange)
if [ -n "$EXCHANGE" ]; then
    echo "   ✓ coverage_exchange 存在"
    echo "   $EXCHANGE"
else
    echo "   ✗ coverage_exchange 不存在"
fi
echo ""

# 3. 检查Queue
echo "3. 检查Queue..."
QUEUE_INFO=$(docker exec coverage-rabbitmq rabbitmqctl list_queues name messages consumers | grep coverage_queue)
if [ -n "$QUEUE_INFO" ]; then
    echo "   ✓ coverage_queue 存在"
    echo "   $QUEUE_INFO"
    MESSAGES=$(echo $QUEUE_INFO | awk '{print $2}')
    CONSUMERS=$(echo $QUEUE_INFO | awk '{print $3}')
    echo "   队列中消息数: $MESSAGES"
    echo "   消费者数量: $CONSUMERS"
    if [ "$CONSUMERS" = "0" ]; then
        echo "   ⚠ 警告: 没有消费者连接到队列"
        echo "   请检查 coverage-consumer 服务是否运行"
    fi
else
    echo "   ✗ coverage_queue 不存在"
fi
echo ""

# 4. 检查Binding
echo "4. 检查Binding..."
BINDING=$(docker exec coverage-rabbitmq rabbitmqctl list_bindings | grep "coverage_exchange.*coverage_queue.*coverage.report")
if [ -n "$BINDING" ]; then
    echo "   ✓ Binding 配置正确"
    echo "   coverage_exchange -> coverage.report -> coverage_queue"
else
    echo "   ✗ Binding 配置缺失"
fi
echo ""

# 5. 检查goc wrapper进程
echo "5. 检查goc wrapper进程..."
WRAPPER_PID=$(ps aux | grep "goc wrapper" | grep -v grep | awk '{print $2}')
if [ -n "$WRAPPER_PID" ]; then
    echo "   ✓ goc wrapper 进程运行中 (PID: $WRAPPER_PID)"
    WRAPPER_CMD=$(ps aux | grep "goc wrapper" | grep -v grep)
    echo "   命令: $WRAPPER_CMD"
    
    # 检查是否包含rabbitmq-url参数
    if echo "$WRAPPER_CMD" | grep -q "rabbitmq-url"; then
        echo "   ✓ 已配置 --rabbitmq-url 参数"
    else
        echo "   ✗ 未配置 --rabbitmq-url 参数"
        echo "   ⚠ 这是问题所在！goc wrapper需要 --rabbitmq-url 参数才能发布消息"
        echo ""
        echo "   解决方案:"
        echo "   1. 停止当前wrapper: kill $WRAPPER_PID"
        echo "   2. 使用以下命令重新启动:"
        echo "      goc wrapper --port=:7777 --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/"
    fi
else
    echo "   ✗ goc wrapper 进程未运行"
    echo "   请启动goc wrapper:"
    echo "   goc wrapper --port=:7777 --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/"
fi
echo ""

# 6. 检查Consumer服务
echo "6. 检查Consumer服务..."
CONSUMER_PID=$(ps aux | grep "coverage-consumer" | grep -v grep | awk '{print $2}')
if [ -n "$CONSUMER_PID" ]; then
    echo "   ✓ Consumer服务运行中 (PID: $CONSUMER_PID)"
else
    echo "   ✗ Consumer服务未运行"
    echo "   请运行: cd coverage-platform && ./run.sh start consumer"
fi
echo ""

# 7. 测试消息发布（如果goc wrapper配置正确）
echo "7. 测试消息发布..."
if [ -n "$WRAPPER_PID" ] && echo "$WRAPPER_CMD" | grep -q "rabbitmq-url"; then
    echo "   goc wrapper已配置RabbitMQ，可以测试发布消息"
    echo "   测试方法: 向goc wrapper发送覆盖率请求"
    echo "   curl http://localhost:7777/v1/cover/profile"
else
    echo "   ⚠ 跳过测试（goc wrapper未配置RabbitMQ）"
fi
echo ""

echo "=========================================="
echo "诊断完成"
echo "=========================================="

