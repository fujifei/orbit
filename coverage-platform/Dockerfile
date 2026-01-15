FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# 配置 SSH 以支持 Git 操作
# 创建 .ssh 目录并添加常见 Git 服务器的主机密钥
RUN mkdir -p /root/.ssh && \
    chmod 700 /root/.ssh && \
    ssh-keyscan -t rsa,ecdsa,ed25519 github.com >> /root/.ssh/known_hosts 2>/dev/null || true && \
    ssh-keyscan -t rsa,ecdsa,ed25519 gitlab.com >> /root/.ssh/known_hosts 2>/dev/null || true && \
    ssh-keyscan -t rsa,ecdsa,ed25519 bitbucket.org >> /root/.ssh/known_hosts 2>/dev/null || true && \
    ssh-keyscan -t rsa,ecdsa,ed25519 gitee.com >> /root/.ssh/known_hosts 2>/dev/null || true && \
    chmod 600 /root/.ssh/known_hosts

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志目录
RUN mkdir -p logs

# 暴露端口（coverage-api使用8826）
EXPOSE 8826

# 默认命令（可以在docker-compose中覆盖）
CMD ["python3", "coverage-api/main.py"]

