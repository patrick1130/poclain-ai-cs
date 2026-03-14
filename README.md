# 微信AI客服系统

基于微信生态的智能客服系统，实现"AI知识库客服+人工兜底"的完整解决方案。

## 🌟 系统特点

- **智能AI客服**：基于知识库的智能问答，确保回答100%基于企业知识
- **人工客服兜底**：AI无法回答时自动转接人工客服
- **微信生态集成**：支持微信公众号、小程序等多渠道接入
- **实时消息通信**：基于WebSocket的实时消息推送
- **知识库管理**：支持PDF、Word、TXT等多种文档格式
- **数据统计分析**：会话数据可视化分析

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Node.js 16+
- MySQL 5.7+
- Redis 6.0+
- 微信公众号（服务号）
- 豆包大模型API账号

### 安装部署

1. **克隆项目**

```bash
git clone https://github.com/your-repo/wechat-ai-customer-service.git
cd wechat-ai-customer-service
```

2. **配置环境变量**

```bash
# 复制环境变量示例文件
cp backend/.env.example backend/.env

# 编辑环境变量配置
vim backend/.env
```

配置说明：
- `DOUBAO_API_KEY`、`DOUBAO_API_SECRET`：豆包大模型API凭证
- `WECHAT_APPID`、`WECHAT_APPSECRET`：微信公众号开发凭证
- `WECHAT_TOKEN`、`WECHAT_ENCODING_AES_KEY`：微信消息加密配置
- `DATABASE_URL`：MySQL数据库连接字符串
- `REDIS_URL`：Redis缓存连接字符串

3. **启动服务**

```bash
# 使用启动脚本一键部署
./start.sh
```

或者手动启动：

```bash
# 启动后端服务
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端服务
cd ../frontend
npm install
npm run dev
```

4. **微信公众号配置**

- 登录微信公众平台，进入"开发-基本配置"
- 服务器配置：
  - URL: `http://your-server.com/api/wechat/callback`
  - Token: 与环境变量中配置的一致
  - 消息加解密方式：选择"安全模式"
- 启用服务器配置

## 📖 使用指南

### 1. 知识库管理

1. 登录管理后台（默认账号：admin/admin123）
2. 进入"知识库管理"页面
3. 点击"上传文档"，支持PDF、Word、TXT格式
4. 等待文档处理完成后即可在AI客服中使用

### 2. 客服工作台

1. 使用客服账号登录（默认账号：agent/agent123）
2. 在"会话列表"查看待处理的会话
3. 点击会话进入聊天界面
4. 支持文本、图片、表情等多种消息类型

### 3. 数据统计

- 查看会话总数、AI处理率、人工转接率等关键指标
- 分析用户问题类型分布
- 监控系统响应时间和服务质量

## 🏗️ 系统架构

### 技术栈

- **后端**：FastAPI + SQLAlchemy + Redis + ChromaDB
- **前端**：Vue3 + Element Plus + Socket.IO
- **AI模型**：豆包大模型API
- **向量数据库**：ChromaDB
- **消息队列**：Redis Pub/Sub

### 核心流程

1. 用户发送消息到微信公众号
2. 系统接收微信消息并进行处理
3. 在知识库中检索相关信息
4. AI基于知识库内容生成回答
5. 如果AI无法回答，自动转接人工客服
6. 人工客服在工作台处理转接的会话

## 🔧 开发与扩展

### 目录结构

```
wechat-ai-customer-service/
├── backend/                # 后端代码
│   ├── app/                # 应用主目录
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # 数据校验
│   │   └── utils/          # 工具函数
│   ├── tests/              # 单元测试
│   └── requirements.txt    # 依赖列表
├── frontend/               # 前端代码
│   ├── src/                # 源代码
│   │   ├── api/            # API调用
│   │   ├── components/     # 组件
│   │   ├── views/          # 页面
│   │   └── App.vue         # 应用入口
│   └── package.json        # NPM配置
├── start.sh                # 启动脚本
└── README.md               # 项目说明
```

### 添加新功能

1. **添加新的API端点**：
   - 在 `backend/app/api/` 目录下创建新的路由文件
   - 在 `backend/app/api/__init__.py` 中注册路由

2. **扩展知识库支持的文档格式**：
   - 在 `backend/app/utils/document_processor.py` 中添加新的处理器
   - 确保添加相应的依赖包到 `requirements.txt`

3. **自定义AI提示词模板**：
   - 修改 `backend/app/utils/message_handler.py` 中的 `_build_prompt` 方法

## 🐛 常见问题

### 微信消息无法接收

1. 检查微信公众号服务器配置是否正确
2. 确认服务器可以正常访问（端口80/443）
3. 查看日志中的错误信息

### AI回答不准确

1. 检查知识库中是否有相关文档
2. 尝试重新上传更详细的文档
3. 调整向量搜索的相似度阈值

### 系统性能问题

1. 确保Redis服务正常运行
2. 检查数据库连接和索引优化
3. 考虑增加服务器资源或进行负载均衡

## 📄 许可证

MIT License - 详见 LICENSE 文件

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

## 📞 支持

如有问题，请通过以下方式联系：
- 邮箱：support@example.com
- 微信：YourWeChatID
- GitHub Issues：[项目Issues页面](https://github.com/your-repo/wechat-ai-customer-service/issues)