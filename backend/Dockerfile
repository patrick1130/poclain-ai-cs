FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 Python 缓冲 stdout 和写 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 安装系统级依赖（编译 C 扩展所需，如 numpy, passlib 等）
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制后端源代码
COPY . .

# 暴露 FastAPI 端口
EXPOSE 8000

# 启动命令（测试环境使用 reload，生产环境需移除 --reload 并增加 workers）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]