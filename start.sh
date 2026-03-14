#!/bin/bash

# 微信智能客服系统启动脚本

echo "========================================="
echo "微信智能客服系统启动脚本"
echo "========================================="

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "错误: Python版本需要 >= $REQUIRED_VERSION，当前版本为 $PYTHON_VERSION"
    exit 1
fi

echo "Python版本检查通过: $PYTHON_VERSION"

# 创建虚拟环境
if [ ! -d "backend/venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv backend/venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source backend/venv/bin/activate

# 安装依赖
echo "安装Python依赖..."
pip install -r backend/requirements.txt

# 复制环境变量配置文件
if [ ! -f "backend/.env" ]; then
    echo "创建环境变量配置文件..."
    cp backend/.env.example backend/.env
    echo "请编辑 backend/.env 文件，配置必要的环境变量"
    echo "特别是微信公众号配置和豆包大模型API配置"
fi

# 创建向量数据库目录
if [ ! -d "backend/vector_db" ]; then
    echo "创建向量数据库目录..."
    mkdir -p backend/vector_db
fi

echo "========================================="
echo "环境准备完成！"
echo "========================================="
echo "启动后端服务:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "访问API文档:"
echo "  http://localhost:8000/docs"
echo ""
echo "========================================="