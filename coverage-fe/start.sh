#!/bin/bash

# 前端服务启动脚本

echo "=========================================="
echo "前端服务启动脚本"
echo "=========================================="

# 检查并处理端口占用
echo ""
echo "检查端口3000..."
PORT_PID=$(lsof -ti:3000 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "端口3000已被占用 (PID: $PORT_PID)"
    echo "正在终止占用端口的进程..."
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
    # 再次检查确保端口已释放
    PORT_PID=$(lsof -ti:3000 2>/dev/null)
    if [ -n "$PORT_PID" ]; then
        echo "警告: 无法释放端口3000，请手动检查"
    else
        echo "端口3000已释放 ✓"
    fi
else
    echo "端口3000可用 ✓"
fi

# 启动前端服务
echo ""
echo "启动前端服务..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 检查node_modules
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 在后台启动前端
npm run dev &
FRONTEND_PID=$!
echo "前端服务已启动 (PID: $FRONTEND_PID) ✓"
echo "前端服务地址: http://localhost:3000"

echo ""
echo "=========================================="
echo "服务启动完成！"
echo "=========================================="
echo "前端: http://localhost:3000"
echo ""
echo "按 Ctrl+C 停止服务"

# 等待用户中断
trap "kill $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait

