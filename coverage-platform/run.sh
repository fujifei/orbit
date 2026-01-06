#!/bin/bash

# 覆盖率平台服务管理脚本
# 支持启动、停止、重启 coverage-api 和 coverage-consumer 服务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$SCRIPT_DIR/coverage-api"
CONSUMER_DIR="$SCRIPT_DIR/coverage-consumer"
ADAPTER_DIR="$SCRIPT_DIR/coverage-adapter"
PID_DIR="$SCRIPT_DIR/.pids"

# 创建PID目录
mkdir -p "$PID_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查服务是否运行
is_running() {
    local service=$1
    local pid_file="$PID_DIR/${service}.pid"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# 启动API服务
start_api() {
    if is_running "coverage-api"; then
        print_warn "Coverage API服务已在运行中"
        return 1
    fi

    print_info "启动Coverage API服务..."
    cd "$API_DIR" || exit 1

    if [ ! -f "main.py" ]; then
        print_error "未找到main.py文件: $API_DIR"
        return 1
    fi

    # 检查Python依赖
    if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
        print_error "未找到requirements.txt文件: $SCRIPT_DIR"
        return 1
    fi

    # 检查并安装Python依赖
    if ! python3 -c "import flask" 2>/dev/null; then
        print_info "安装Python依赖..."
        pip3 install -r "$SCRIPT_DIR/requirements.txt"
    fi

    # 在后台启动API服务
    nohup python3 main.py > "$SCRIPT_DIR/logs/api.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/coverage-api.pid"
    
    # 等待服务启动
    sleep 2
    
    if is_running "coverage-api"; then
        print_info "Coverage API服务已启动 (PID: $pid) ✓"
        print_info "API服务地址: http://localhost:8826"
        print_info "日志文件: $SCRIPT_DIR/logs/api.log"
        return 0
    else
        print_error "Coverage API服务启动失败"
        rm -f "$PID_DIR/coverage-api.pid"
        return 1
    fi
}

# 启动Consumer服务
start_consumer() {
    if is_running "coverage-consumer"; then
        print_warn "Coverage Consumer服务已在运行中"
        return 1
    fi

    print_info "启动Coverage Consumer服务..."
    cd "$CONSUMER_DIR" || exit 1

    if [ ! -f "main.py" ]; then
        print_error "未找到main.py文件: $CONSUMER_DIR"
        return 1
    fi

    # 检查Python依赖
    if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
        print_error "未找到requirements.txt文件: $SCRIPT_DIR"
        return 1
    fi

    # 检查并安装Python依赖
    if ! python3 -c "import pika" 2>/dev/null; then
        print_info "安装Python依赖..."
        pip3 install -r "$SCRIPT_DIR/requirements.txt"
    fi

    # 在后台启动Consumer服务
    nohup python3 main.py > "$SCRIPT_DIR/logs/consumer.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/coverage-consumer.pid"
    
    # 等待服务启动
    sleep 2
    
    if is_running "coverage-consumer"; then
        print_info "Coverage Consumer服务已启动 (PID: $pid) ✓"
        print_info "日志文件: $SCRIPT_DIR/logs/consumer.log"
        return 0
    else
        print_error "Coverage Consumer服务启动失败"
        rm -f "$PID_DIR/coverage-consumer.pid"
        return 1
    fi
}

# 启动Adapter服务
start_adapter() {
    if is_running "coverage-adapter"; then
        print_warn "Coverage Adapter服务已在运行中"
        return 1
    fi

    print_info "启动Coverage Adapter服务..."
    cd "$ADAPTER_DIR" || exit 1

    if [ ! -f "agent.py" ] || [ ! -f "cli.py" ]; then
        print_error "未找到agent.py或cli.py文件: $ADAPTER_DIR"
        return 1
    fi

    # 检查并安装coverage-adapter
    if ! command -v coverage-adapter > /dev/null 2>&1; then
        print_info "安装Coverage Adapter..."
        if ! pip3 install -e "$ADAPTER_DIR"; then
            print_error "Coverage Adapter安装失败"
            return 1
        fi
        # 验证安装是否成功
        if ! command -v coverage-adapter > /dev/null 2>&1; then
            print_warn "coverage-adapter命令未找到，尝试使用python3 cli.py作为后备方案"
            # 使用PYTHONPATH确保可以导入agent模块
            export PYTHONPATH="$ADAPTER_DIR:$PYTHONPATH"
            COVERAGE_ADAPTER_CMD="python3 cli.py"
        else
            COVERAGE_ADAPTER_CMD="coverage-adapter"
        fi
    else
        COVERAGE_ADAPTER_CMD="coverage-adapter"
    fi

    # 检查jacococli.jar（使用环境变量或默认路径）
    JACOCO_CLI_JAR="${JACOCO_CLI_JAR:-$SCRIPT_DIR/../jacoco/lib/jacococli.jar}"
    if [ ! -f "$JACOCO_CLI_JAR" ]; then
        print_warn "jacococli.jar not found at $JACOCO_CLI_JAR"
        print_warn "Coverage Adapter may not work properly. Please set JACOCO_CLI_JAR environment variable."
    fi

    # 设置默认配置
    JACOCO_EXEC_FILE="${JACOCO_EXEC_FILE:-$SCRIPT_DIR/../jacoco.exec}"
    JACOCO_ADDRESS="${JACOCO_ADDRESS:-localhost}"
    JACOCO_PORT="${JACOCO_PORT:-6300}"
    RABBITMQ_URL="${RABBITMQ_URL:-amqp://coverage:coverage123@localhost:5672/}"
    FLUSH_INTERVAL="${FLUSH_INTERVAL:-60}"

    # 在后台启动Adapter服务
    nohup $COVERAGE_ADAPTER_CMD \
        --rabbitmq-url "$RABBITMQ_URL" \
        --flush-interval "$FLUSH_INTERVAL" \
        --jacoco-address "$JACOCO_ADDRESS" \
        --jacoco-port "$JACOCO_PORT" \
        --jacoco-cli-jar "$JACOCO_CLI_JAR" \
        --jacoco-exec-file "$JACOCO_EXEC_FILE" \
        > "$SCRIPT_DIR/logs/adapter.log" 2>&1 &
    local pid=$!
    echo $pid > "$PID_DIR/coverage-adapter.pid"
    
    # 等待服务启动
    sleep 2
    
    if is_running "coverage-adapter"; then
        print_info "Coverage Adapter服务已启动 (PID: $pid) ✓"
        print_info "日志文件: $SCRIPT_DIR/logs/adapter.log"
        return 0
    else
        print_error "Coverage Adapter服务启动失败"
        rm -f "$PID_DIR/coverage-adapter.pid"
        return 1
    fi
}

# 停止API服务
stop_api() {
    if ! is_running "coverage-api"; then
        print_warn "Coverage API服务未运行"
        return 1
    fi

    local pid_file="$PID_DIR/coverage-api.pid"
    local pid=$(cat "$pid_file")
    
    print_info "停止Coverage API服务 (PID: $pid)..."
    kill "$pid" 2>/dev/null
    
    # 等待进程结束
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if ps -p "$pid" > /dev/null 2>&1; then
        print_warn "强制停止Coverage API服务..."
        kill -9 "$pid" 2>/dev/null
    fi
    
    rm -f "$pid_file"
    print_info "Coverage API服务已停止 ✓"
    return 0
}

# 停止Consumer服务
stop_consumer() {
    if ! is_running "coverage-consumer"; then
        print_warn "Coverage Consumer服务未运行"
        return 1
    fi

    local pid_file="$PID_DIR/coverage-consumer.pid"
    local pid=$(cat "$pid_file")
    
    print_info "停止Coverage Consumer服务 (PID: $pid)..."
    kill "$pid" 2>/dev/null
    
    # 等待进程结束
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if ps -p "$pid" > /dev/null 2>&1; then
        print_warn "强制停止Coverage Consumer服务..."
        kill -9 "$pid" 2>/dev/null
    fi
    
    rm -f "$pid_file"
    print_info "Coverage Consumer服务已停止 ✓"
    return 0
}

# 停止Adapter服务
stop_adapter() {
    if ! is_running "coverage-adapter"; then
        print_warn "Coverage Adapter服务未运行"
        return 1
    fi

    local pid_file="$PID_DIR/coverage-adapter.pid"
    local pid=$(cat "$pid_file")
    
    print_info "停止Coverage Adapter服务 (PID: $pid)..."
    kill "$pid" 2>/dev/null
    
    # 等待进程结束
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if ps -p "$pid" > /dev/null 2>&1; then
        print_warn "强制停止Coverage Adapter服务..."
        kill -9 "$pid" 2>/dev/null
    fi
    
    rm -f "$pid_file"
    print_info "Coverage Adapter服务已停止 ✓"
    return 0
}

# 重启API服务
restart_api() {
    print_info "重启Coverage API服务..."
    stop_api
    sleep 1
    start_api
}

# 重启Consumer服务
restart_consumer() {
    print_info "重启Coverage Consumer服务..."
    stop_consumer
    sleep 1
    start_consumer
}

# 重启Adapter服务
restart_adapter() {
    print_info "重启Coverage Adapter服务..."
    stop_adapter
    sleep 1
    start_adapter
}

# 检查RabbitMQ服务
check_rabbitmq() {
    if ! docker ps | grep -q coverage-rabbitmq; then
        print_warn "RabbitMQ服务未运行，正在启动..."
        cd "$SCRIPT_DIR/docker/rabbitmq" || exit 1
        docker-compose up -d
        cd "$SCRIPT_DIR" || exit 1
        print_info "等待RabbitMQ启动..."
        sleep 5
        print_info "RabbitMQ服务已启动 ✓"
        print_info "RabbitMQ管理界面: http://localhost:15672 (用户名: coverage, 密码: coverage123)"
    else
        print_info "RabbitMQ服务已在运行 ✓"
    fi
}

# 显示服务状态
status() {
    echo ""
    echo "=========================================="
    echo "服务状态"
    echo "=========================================="
    
    # RabbitMQ状态
    if docker ps | grep -q coverage-rabbitmq; then
        echo -e "RabbitMQ:     ${GREEN}运行中${NC}"
    else
        echo -e "RabbitMQ:     ${RED}未运行${NC}"
    fi
    
    # API服务状态
    if is_running "coverage-api"; then
        local pid=$(cat "$PID_DIR/coverage-api.pid")
        echo -e "Coverage API: ${GREEN}运行中${NC} (PID: $pid)"
    else
        echo -e "Coverage API: ${RED}未运行${NC}"
    fi
    
    # Consumer服务状态
    if is_running "coverage-consumer"; then
        local pid=$(cat "$PID_DIR/coverage-consumer.pid")
        echo -e "Consumer:    ${GREEN}运行中${NC} (PID: $pid)"
    else
        echo -e "Consumer:    ${RED}未运行${NC}"
    fi
    
    # Adapter服务状态
    if is_running "coverage-adapter"; then
        local pid=$(cat "$PID_DIR/coverage-adapter.pid")
        echo -e "Adapter:     ${GREEN}运行中${NC} (PID: $pid)"
    else
        echo -e "Adapter:     ${RED}未运行${NC}"
    fi
    
    echo ""
}

# 创建日志目录
mkdir -p "$SCRIPT_DIR/logs"

# 主函数
main() {
    case "${1:-}" in
        start)
            case "${2:-all}" in
                api)
                    start_api
                    ;;
                consumer)
                    check_rabbitmq
                    start_consumer
                    ;;
                adapter)
                    check_rabbitmq
                    start_adapter
                    ;;
                all|*)
                    check_rabbitmq
                    start_api
                    start_consumer
                    start_adapter
                    echo ""
                    print_info "所有服务已启动！"
                    status
                    ;;
            esac
            ;;
        stop)
            case "${2:-all}" in
                api)
                    stop_api
                    ;;
                consumer)
                    stop_consumer
                    ;;
                adapter)
                    stop_adapter
                    ;;
                all|*)
                    stop_api
                    stop_consumer
                    stop_adapter
                    echo ""
                    print_info "所有服务已停止！"
                    ;;
            esac
            ;;
        restart)
            case "${2:-all}" in
                api)
                    restart_api
                    ;;
                consumer)
                    check_rabbitmq
                    restart_consumer
                    ;;
                adapter)
                    check_rabbitmq
                    restart_adapter
                    ;;
                all|*)
                    check_rabbitmq
                    restart_api
                    restart_consumer
                    restart_adapter
                    echo ""
                    print_info "所有服务已重启！"
                    status
                    ;;
            esac
            ;;
        status)
            status
            ;;
        *)
            echo "覆盖率平台服务管理脚本"
            echo ""
            echo "用法: $0 {start|stop|restart|status} [api|consumer|adapter|all]"
            echo ""
            echo "命令:"
            echo "  start [api|consumer|adapter|all]    启动服务 (默认: all)"
            echo "  stop [api|consumer|adapter|all]      停止服务 (默认: all)"
            echo "  restart [api|consumer|adapter|all]  重启服务 (默认: all)"
            echo "  status                                查看服务状态"
            echo ""
            echo "示例:"
            echo "  $0 start                    # 启动所有服务"
            echo "  $0 start api                # 仅启动API服务"
            echo "  $0 start consumer           # 仅启动Consumer服务"
            echo "  $0 start adapter            # 仅启动Adapter服务"
            echo "  $0 stop api                 # 停止API服务"
            echo "  $0 restart consumer         # 重启Consumer服务"
            echo "  $0 restart adapter         # 重启Adapter服务"
            echo "  $0 status                   # 查看服务状态"
            echo ""
            exit 1
            ;;
    esac
}

main "$@"

