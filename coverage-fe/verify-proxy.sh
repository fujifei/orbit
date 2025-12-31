#!/bin/bash

# API 代理验证脚本
# 用于验证前端代理配置是否正确

echo "=========================================="
echo "API 代理配置验证"
echo "=========================================="
echo ""

# 检查后端服务是否运行
echo "1. 检查后端服务（端口 8826）..."
if curl -s http://localhost:8826/health > /dev/null 2>&1; then
    echo "   ✓ 后端服务运行正常"
    BACKEND_STATUS=$(curl -s http://localhost:8826/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "   状态: $BACKEND_STATUS"
else
    echo "   ✗ 后端服务未运行或无法访问"
    echo "   请先启动后端服务: ./run.sh start api"
    exit 1
fi

echo ""

# 检查前端服务是否运行
echo "2. 检查前端服务（端口 3000）..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✓ 前端服务运行正常"
else
    echo "   ✗ 前端服务未运行"
    echo "   请先启动前端服务: cd frontend && npm run dev"
    exit 1
fi

echo ""

# 测试代理是否工作
echo "3. 测试代理配置..."
echo "   通过前端代理访问后端 API..."

# 通过前端代理测试
PROXY_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/v1/coverage/reports 2>/dev/null)

if [ "$PROXY_RESPONSE" = "200" ] || [ "$PROXY_RESPONSE" = "404" ]; then
    echo "   ✓ 代理配置正常（HTTP $PROXY_RESPONSE）"
    echo "   注意: 404 表示代理工作正常，但可能没有数据"
else
    echo "   ✗ 代理可能未正常工作（HTTP $PROXY_RESPONSE）"
    echo "   请检查 Vite 配置和浏览器控制台"
fi

echo ""

# 直接测试后端
echo "4. 直接测试后端 API..."
DIRECT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8826/api/v1/coverage/reports 2>/dev/null)
if [ "$DIRECT_RESPONSE" = "200" ] || [ "$DIRECT_RESPONSE" = "404" ]; then
    echo "   ✓ 后端 API 可访问（HTTP $DIRECT_RESPONSE）"
else
    echo "   ✗ 后端 API 无法访问（HTTP $DIRECT_RESPONSE）"
fi

echo ""
echo "=========================================="
echo "验证完成"
echo "=========================================="
echo ""
echo "重要提示："
echo "- 浏览器显示 http://localhost:3000/api/... 是正常的"
echo "- Vite 会自动将 /api 请求代理到 http://localhost:8826"
echo "- 查看浏览器控制台和 Vite 终端日志以确认代理工作"
echo ""

