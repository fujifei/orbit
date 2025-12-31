FROM rabbitmq:3.12-management

# 设置环境变量
ENV RABBITMQ_DEFAULT_USER=coverage
ENV RABBITMQ_DEFAULT_PASS=coverage123

# 暴露端口
# 5672: AMQP协议端口
# 15672: 管理界面端口
EXPOSE 5672 15672

# 创建队列和交换机的初始化脚本目录
RUN mkdir -p /etc/rabbitmq/definitions

# 复制队列定义文件（可选）
# COPY definitions.json /etc/rabbitmq/definitions/

