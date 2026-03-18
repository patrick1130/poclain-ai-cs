#!/bin/bash

# Poclain 微信智能客服引擎 - 环境初始化与启动脚本

echo "========================================================="
echo " 🚀 正在初始化 Poclain 微信智能客服引擎 (S级架构版) "
echo "========================================================="

# 1. 检查 Python 版本 (提升基线至 3.10 以完美支持异步与 Pydantic V2)
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "⚠️ 警告: 建议 Python 版本 >= $REQUIRED_VERSION，您的当前版本为 $PYTHON_VERSION"
    echo "若低于 3.10，可能会在运行 Pydantic V2 或高级异步特性时出现兼容性提示。"
else
    echo "✅ Python版本检查通过: $PYTHON_VERSION"
fi

# 2. 基础设施前置检查提醒
echo "---------------------------------------------------------"
echo "🔍 正在进行中间件依赖审计..."
echo "请确保以下本地或远程服务正在运行："
echo "  - MySQL 8.0+ (提供会话持久化与坐席认证)"
echo "  - Redis 7.0+ (提供 O(1) 并发限流与 WebSocket Pub/Sub)"
echo "---------------------------------------------------------"

# 3. 创建虚拟环境
if [ ! -d "backend/venv" ]; then
    echo "📦 创建 Python 专属物理隔离沙盒 (虚拟环境)..."
    python3 -m venv backend/venv
fi

# 4. 激活虚拟环境
echo "🔌 激活安全沙盒..."
source backend/venv/bin/activate

# 5. 安装核心依赖
echo "📥 正在拉取工业级核心依赖 (FastAPI, SQLAlchemy, Chroma, DashScope...)"
pip install -r backend/requirements.txt

# 6. 配置系统环境变量防线
if [ ! -f "backend/.env" ]; then
    echo "🛡️ 初始化环境密钥防线..."
    cp backend/.env.example backend/.env
    echo "========================================================="
    echo "🚨 架构师警告：请立即编辑 backend/.env 文件！"
    echo "您必须配置以下核心物理密钥才能启动系统："
    echo "  1. 微信公众平台 Token 及 EncodingAESKey (安全模式解密必填)"
    echo "  2. 阿里云百炼 (DashScope) 大模型 API_KEY (取代旧版豆包)"
    echo "  3. MySQL 与 Redis 数据库连接串"
    echo "========================================================="
fi

# 7. 建立向量数据库物理存储阵列
if [ ! -d "backend/vector_db" ]; then
    echo "🧠 正在分配 ChromaDB 本地向量大脑存储扇区..."
    mkdir -p backend/vector_db
fi

echo "========================================================="
echo "✅ Poclain 智能引擎环境装甲构建完毕！"
echo "========================================================="
echo "🚀 启动后端研发调试模式:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "🔥 启动生产级守护进程 (推荐):"
echo "  gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000"
echo ""
echo "📖 查阅架构 API 白皮书:"
echo "  http://localhost:8000/docs"
echo "========================================================="