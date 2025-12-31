#!/bin/bash

# 前后端API调用测试脚本
# 用于验证前端是否能正确调用后端API获取文件内容

echo "=========================================="
echo "前后端API调用测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试结果统计
PASSED=0
FAILED=0

# 测试函数
test_api() {
    local name=$1
    local url=$2
    local expected=$3
    
    echo -n "测试: $name ... "
    
    response=$(curl -s -w "\n%{http_code}" "$url")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q "$expected"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  HTTP状态码: $http_code"
        echo "  响应内容: $body"
        ((FAILED++))
        return 1
    fi
}

echo "1. 测试后端API服务器健康状态"
echo "----------------------------------------"
test_api "健康检查" "http://localhost:8826/health" "healthy"
echo ""

echo "2. 测试获取文件内容API"
echo "----------------------------------------"

# 测试用例1: tuna项目的user_repository.go
test_api "获取tuna/models/user_repository.go" \
    "http://localhost:8826/api/coverage/file?repo=tuna&commit=e859c635d19db9fd7250ce668e799f881cc7437a&path=models/user_repository.go" \
    "package models"

# 测试用例2: 带backend前缀的路径
test_api "获取backend/models/user_repository.go" \
    "http://localhost:8826/api/coverage/file?repo=tuna&commit=97d234a830434b7c3b80496d2bb49acc290524b3&path=backend/models/user_repository.go" \
    "package models"

echo ""
echo "3. 测试API响应格式"
echo "----------------------------------------"

# 获取一个文件内容并检查JSON格式
response=$(curl -s "http://localhost:8826/api/coverage/file?repo=tuna&commit=e859c635d19db9fd7250ce668e799f881cc7437a&path=models/user_repository.go")

echo -n "检查响应包含content字段 ... "
if echo "$response" | grep -q '"content"'; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

echo -n "检查响应包含repo字段 ... "
if echo "$response" | grep -q '"repo"'; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

echo -n "检查响应包含commit字段 ... "
if echo "$response" | grep -q '"commit"'; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

echo ""
echo "4. 测试CORS配置"
echo "----------------------------------------"

# 测试CORS头
echo -n "检查CORS头 ... "
cors_headers=$(curl -s -I "http://localhost:8826/api/coverage/file?repo=tuna&commit=e859c635d19db9fd7250ce668e799f881cc7437a&path=models/user_repository.go" | grep -i "access-control")

if [ -n "$cors_headers" ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    echo "  $cors_headers"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} - 未检测到CORS头，可能会导致前端跨域问题"
fi

echo ""
echo "=========================================="
echo "测试结果汇总"
echo "=========================================="
echo -e "通过: ${GREEN}$PASSED${NC}"
echo -e "失败: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 后端API测试全部通过！${NC}"
    echo ""
    echo "前端测试步骤："
    echo "1. 启动前端服务: cd ../coverage-fe && npm run dev"
    echo "2. 打开浏览器: http://localhost:3000"
    echo "3. 打开开发者工具(F12)，切换到Console标签"
    echo "4. 访问任意覆盖率报告详情页"
    echo "5. 选择一个文件，查看控制台日志"
    echo ""
    echo "预期看到类似日志："
    echo "[CoverageDetail] 正在获取文件内容: { repo: 'tuna', commit: '...', path: '...' }"
    echo "[CoverageDetail] ✅ 成功设置真实文件内容"
    echo ""
    exit 0
else
    echo -e "${RED}✗ 部分测试失败，请检查后端API服务器状态${NC}"
    echo ""
    echo "排查步骤："
    echo "1. 检查API服务器是否运行: ps aux | grep 'coverage-api'"
    echo "2. 查看API日志: tail -f logs/api.log"
    echo "3. 重启API服务器: ./run.sh restart api"
    echo ""
    exit 1
fi

