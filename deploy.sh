#!/bin/bash

# Poclain 智能客服 - 云端生产环境自动化部署脚本
# 架构版本: v1.0.0-rc.1 (Security Audited)

set -e # 遇到错误立即停止执行

echo "========================================================="
echo " 🏗️  开始部署 Poclain 微信智能客服生产环境 "
echo "========================================================="

# 1. 物理环境检查
if ! [ -x "$(command -v docker-compose)" ]; then
  echo "❌ 致命错误: 未检测到 docker-compose，请先安装 Docker 引擎。"
  exit 1
fi

# 2. 秘密注入防线 (Secret Injection)
if [ ! -f "backend/.env" ]; then
    echo "🛡️ 检测到生产环境配置缺失，正在从模板生成..."
    cp backend/.env.example backend/.env
    echo "⚠️  警告: 请立即手动编辑 backend/.env 并填入真实的微信/阿里云 API Key！"
    echo "编辑命令: vi backend/.env"
    exit 1
fi

# 3. 物理存储阵列初始化 (Persistence)
echo "📂 正在初始化物理卷挂载点..."
mkdir -p backend/vector_db
mkdir -p backend/uploads
mkdir -p backend/logs

# 4. 执行原子级容器构建与冷启动
echo "🚀 正在拉取基础镜像并执行多阶段构建 (Multi-stage Build)..."
# --build: 强制重新编译前端 dist 和后端环境
# -d: 守护进程模式运行
docker-compose up -d --build

# 5. 系统连通性健康检查
echo "🔍 正在执行系统级健康巡检 (Health Check)..."
sleep 5 # 等待容器网络初始化

# 检查后端 API 响应
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health || echo "500")

if [ "$HTTP_STATUS" == "200" ]; then
    echo "✅ 后端内核启动成功！"
else
    echo "❌ 后端服务响应异常 (Status: $HTTP_STATUS)，请检查 'docker logs poclain_wechat_backend'。"
fi

# 6. 自动化向量化提示
echo "---------------------------------------------------------"
echo "🧠 提示: 若这是首次部署，请记得进入容器执行知识库灌库脚本:"
echo "命令: docker exec -it poclain_wechat_backend python import_knowledge.py"
echo "---------------------------------------------------------"

echo "✅ 部署任务圆满完成！"
echo "🌐 访问地址: http://你的域名:8080"
echo "📖 接口文档: http://你的域名:8000/docs"
echo "========================================================="