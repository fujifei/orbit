#!/bin/bash

# 诊断goc MQ上报问题的脚本

echo "=========================================="
echo "Goc MQ Reporting 诊断脚本"
echo "=========================================="
echo ""

# 1. 检查goc版本和编译
echo "1. 检查goc编译状态..."
cd "$(dirname "$0")"
if [ ! -f "./goc" ]; then
    echo "   ❌ goc二进制文件不存在，正在编译..."
    go build -o goc . || {
        echo "   ❌ goc编译失败！"
        exit 1
    }
    echo "   ✅ goc编译成功"
else
    echo "   ✅ goc二进制文件存在"
fi

# 2. 检查RabbitMQ连接
echo ""
echo "2. 检查RabbitMQ服务..."
if command -v curl &> /dev/null; then
    if curl -s -u coverage:coverage123 http://localhost:15672/api/overview > /dev/null 2>&1; then
        echo "   ✅ RabbitMQ Management API可访问"
    else
        echo "   ⚠️  RabbitMQ Management API不可访问"
        echo "      请检查RabbitMQ是否启动：docker ps | grep rabbitmq"
    fi
else
    echo "   ⚠️  curl命令不可用，跳过RabbitMQ检查"
fi

# 3. 测试编译带MQ上报的二进制
echo ""
echo "3. 测试编译带MQ上报功能的二进制..."
cd examples/simple-mq-app

# 清理旧文件
rm -f simple-mq-app _cover_http_apis.go http_cover_apis_auto_generated.go

# 使用goc build编译
echo "   执行: ../../goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o simple-mq-app ."
../../goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o simple-mq-app . 2>&1 | tee /tmp/goc_build.log

if [ $? -ne 0 ]; then
    echo "   ❌ goc build失败！"
    echo "   查看详细日志: cat /tmp/goc_build.log"
    exit 1
fi

if [ ! -f "simple-mq-app" ]; then
    echo "   ❌ 编译后的二进制文件不存在！"
    exit 1
fi

echo "   ✅ 编译成功"

# 4. 检查注入的代码
echo ""
echo "4. 检查注入的覆盖率代码..."

# 查找实际生成的文件（可能是 _cover_http_apis.go 或 http_cover_apis_auto_generated.go）
COVER_FILE=""
if [ -f "http_cover_apis_auto_generated.go" ]; then
    COVER_FILE="http_cover_apis_auto_generated.go"
elif [ -f "_cover_http_apis.go" ]; then
    COVER_FILE="_cover_http_apis.go"
fi

if [ -n "$COVER_FILE" ]; then
    echo "   ✅ 覆盖率代码文件已生成: $COVER_FILE"
    
    # 检查RabbitMQ URL是否注入
    REPORT_URL_LINE=$(grep "gocReportURL" "$COVER_FILE" | head -1)
    if echo "$REPORT_URL_LINE" | grep -q 'gocReportURL.*=.*""'; then
        echo "   ❌ gocReportURL 是空字符串！"
        echo "   这意味着编译时没有传递 --rabbitmq-url 参数"
        echo "   当前值: $REPORT_URL_LINE"
        echo ""
        echo "   💡 解决方案："
        echo "   重新编译时添加 --rabbitmq-url 参数："
        echo "   goc build --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/ -o simple-mq-app ."
    elif echo "$REPORT_URL_LINE" | grep -q "gocReportURL.*amqp://"; then
        echo "   ✅ RabbitMQ URL已正确注入到代码中"
        echo "   注入的URL:"
        echo "   $REPORT_URL_LINE"
    elif echo "$REPORT_URL_LINE" | grep -q "gocReportURL.*http://"; then
        echo "   ✅ HTTP URL已正确注入到代码中"
        echo "   注入的URL:"
        echo "   $REPORT_URL_LINE"
    else
        echo "   ⚠️  无法确定gocReportURL的值"
        echo "   当前行: $REPORT_URL_LINE"
    fi
    
    # 检查repo_id相关代码
    if grep -q "RepoID" "$COVER_FILE"; then
        echo "   ✅ RepoID字段已添加"
    else
        echo "   ⚠️  RepoID字段未找到（可能是旧版本）"
    fi
    
    # 检查上报逻辑
    if grep -q "publishCoverageReportGoc" "$COVER_FILE"; then
        echo "   ✅ 上报逻辑已注入"
    else
        echo "   ❌ 上报逻辑未找到！"
    fi
    
    # 检查定时上报逻辑
    if grep -q "collectAndReportCoverageGoc\|Started periodic coverage reporting" "$COVER_FILE"; then
        echo "   ✅ 定时上报逻辑已注入"
    else
        echo "   ⚠️  定时上报逻辑未找到（可能是旧版本）"
    fi
else
    echo "   ❌ 覆盖率代码文件未生成！"
    echo "   查找的文件: _cover_http_apis.go 或 http_cover_apis_auto_generated.go"
    echo "   这可能意味着代码注入失败"
    echo ""
    echo "   💡 检查编译日志:"
    echo "   cat /tmp/goc_build.log"
    echo ""
    echo "   💡 检查当前目录文件:"
    ls -la *.go 2>/dev/null | head -5
fi

# 5. 运行测试
echo ""
echo "5. 启动测试服务..."
echo "   正在后台启动 simple-mq-app..."

# 启动服务
./simple-mq-app > /tmp/simple-mq-app.log 2>&1 &
APP_PID=$!
echo "   服务PID: $APP_PID"

# 等待服务启动
echo "   等待服务启动..."
sleep 3

# 检查进程是否还在运行
if ! ps -p $APP_PID > /dev/null 2>&1; then
    echo "   ❌ 服务启动失败！"
    echo "   查看日志: cat /tmp/simple-mq-app.log"
    cat /tmp/simple-mq-app.log
    exit 1
fi

echo "   ✅ 服务已启动"

# 查找服务端口
echo ""
echo "6. 查找服务监听端口..."
sleep 1
PORT=$(lsof -nP -p $APP_PID 2>/dev/null | grep LISTEN | awk '{print $9}' | cut -d: -f2 | head -1)

if [ -z "$PORT" ]; then
    echo "   ⚠️  无法自动检测端口，尝试使用默认端口..."
    # 尝试常见端口
    for p in 8080 8000 3000; do
        if curl -s http://localhost:$p/health > /dev/null 2>&1; then
            PORT=$p
            break
        fi
    done
fi

if [ -z "$PORT" ]; then
    echo "   ❌ 无法找到服务端口！"
    echo "   服务日志:"
    cat /tmp/simple-mq-app.log
    kill $APP_PID 2>/dev/null
    exit 1
fi

echo "   ✅ 服务监听在端口: $PORT"

# 7. 触发覆盖率上报
echo ""
echo "7. 触发覆盖率上报..."
echo "   访问: http://localhost:$PORT/v1/cover/profile"

RESPONSE=$(curl -s http://localhost:$PORT/v1/cover/profile)
echo "   响应内容:"
echo "$RESPONSE" | head -20

# 8. 检查日志
echo ""
echo "8. 检查服务日志..."
echo "   查找MQ上报相关日志:"

# 检查 gocReportURL 是否为空
if grep -q "gocReportURL is EMPTY" /tmp/simple-mq-app.log; then
    echo "   ❌ gocReportURL 为空！覆盖率上报已禁用"
    echo "   这意味着编译时没有传递 --rabbitmq-url 参数"
    echo ""
    echo "   💡 解决方案："
    echo "   1. 重新编译时添加 --rabbitmq-url 参数"
    echo "   2. 检查编译命令是否正确"
elif grep -q "gocReportURL is set:" /tmp/simple-mq-app.log; then
    echo "   ✅ gocReportURL 已设置"
    grep "gocReportURL is set:" /tmp/simple-mq-app.log | head -1
fi

if grep -i "coverage reporting enabled" /tmp/simple-mq-app.log; then
    echo "   ✅ 找到覆盖率上报配置日志"
    grep -i "coverage reporting enabled" /tmp/simple-mq-app.log | head -1
else
    echo "   ⚠️  未找到覆盖率上报配置日志"
fi

if grep -i "Started periodic coverage reporting" /tmp/simple-mq-app.log; then
    echo "   ✅ 定时上报已启动"
    grep -i "Started periodic coverage reporting" /tmp/simple-mq-app.log | head -1
else
    echo "   ⚠️  未找到定时上报启动日志"
fi

if grep -i "Successfully published coverage report" /tmp/simple-mq-app.log; then
    echo "   ✅ 找到上报成功日志"
    grep -i "Successfully published coverage report" /tmp/simple-mq-app.log | tail -3
elif grep -i "Failed to publish coverage report" /tmp/simple-mq-app.log; then
    echo "   ❌ 上报失败！"
    echo "   错误信息:"
    grep -i "Failed to publish coverage report" /tmp/simple-mq-app.log | tail -3
else
    echo "   ⚠️  未找到上报相关日志"
fi

echo ""
echo "   完整服务日志:"
cat /tmp/simple-mq-app.log

# 9. 清理
echo ""
echo "9. 清理测试环境..."
kill $APP_PID 2>/dev/null
echo "   ✅ 服务已停止"

# 10. 总结
echo ""
echo "=========================================="
echo "诊断完成！"
echo "=========================================="
echo ""
echo "如果上报失败，请检查："
echo "1. RabbitMQ是否正常运行"
echo "2. 覆盖率代码文件中的gocReportURL是否正确"
echo "3. 服务日志中是否有错误信息"
echo ""
echo "相关文件位置："
echo "- goc编译日志: /tmp/goc_build.log"
echo "- 服务运行日志: /tmp/simple-mq-app.log"
if [ -n "$COVER_FILE" ]; then
    echo "- 注入的代码: $(pwd)/$COVER_FILE"
else
    echo "- 注入的代码: 未找到（检查 http_cover_apis_auto_generated.go 或 _cover_http_apis.go）"
fi
echo ""

