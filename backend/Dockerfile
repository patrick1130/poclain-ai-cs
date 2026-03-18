FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量：防缓冲、防字节码、强制设定中国标准时区 (关键：防止微信签名时间戳失效)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统级依赖（编译 C 扩展及数据库驱动所需）
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装
COPY requirements.txt .
# 额外安装 gunicorn 作为生产级 WSGI/ASGI 调度服务器
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn==21.2.0

# 复制后端源代码
COPY . .

# 暴露 FastAPI 端口
EXPOSE 8000

# 🚀 架构师生产级启动命令：Gunicorn (4个Worker) 调度 Uvicorn
# 确保在面对突发微信并发流量时，拥有 4 倍的吞吐吞吐能力
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]