# 微信AI客服系统技术文档

## 1. 系统架构概述

微信AI客服系统采用现代化的微服务架构设计，实现了"AI知识库客服+人工兜底"的完整解决方案。系统分为四个主要层次：

### 1.1 分层架构

```
+---------------------+
|      用户层         |
|  微信公众号/小程序   |
+---------------------+
          ↓
+---------------------+
|      接入层         |
|  微信消息接入/API网关 |
+---------------------+
          ↓
+---------------------+
|    核心服务层       |
|  AI客服/人工客服/知识库|
+---------------------+
          ↓
+---------------------+
|    数据存储层       |
| MySQL/Redis/ChromaDB|
+---------------------+
```

### 1.2 技术栈选择

| 类别 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 后端框架 | FastAPI | 0.104+ | 高性能异步框架，自动生成API文档 |
| 前端框架 | Vue3 | 3.3+ | 现代化前端框架，Composition API |
| UI组件库 | Element Plus | 2.4+ | 企业级UI组件库，丰富的组件支持 |
| 数据库 | MySQL | 8.0+ | 关系型数据库，稳定可靠 |
| 缓存 | Redis | 7.0+ | 高性能内存数据库，支持Pub/Sub |
| 向量数据库 | ChromaDB | 0.4+ | 轻量级向量数据库，适合RAG场景 |
| AI模型 | 豆包大模型 | - | 中文理解能力强，API接入简单 |
| WebSocket | Socket.IO | 4.7+ | 实时双向通信，支持断线重连 |
| ORM | SQLAlchemy | 2.0+ | 功能强大的Python ORM框架 |

## 2. 核心功能模块

### 2.1 微信消息接入模块

#### 2.1.1 功能说明
负责接收和处理来自微信公众号的消息，包括文本、图片、语音等多种消息类型。

#### 2.1.2 技术实现
- 使用FastAPI的Web框架接收微信服务器的POST请求
- 实现微信消息的签名验证和加解密
- 支持微信消息的被动回复和客服消息主动推送
- 使用Redis缓存微信access_token，避免频繁调用接口

#### 2.1.3 关键代码
```python
# 微信消息验证和处理
@app.post("/api/wechat/callback")
async def wechat_callback(request: Request):
    # 验证微信消息签名
    signature = request.query_params.get("signature")
    timestamp = request.query_params.get("timestamp")
    nonce = request.query_params.get("nonce")
    
    if not verify_signature(signature, timestamp, nonce):
        return "Invalid signature"
    
    # 处理消息内容
    data = await request.body()
    message = parse_wechat_message(data)
    
    # 根据消息类型分发处理
    return await handle_wechat_message(message)
```

### 2.2 AI客服引擎模块

#### 2.2.1 功能说明
AI客服引擎是系统的核心，负责基于知识库内容生成回答，当AI无法回答时自动转接人工客服。

#### 2.2.2 RAG技术实现
- **检索增强生成（RAG）**：结合向量检索和大语言模型
- **相似度匹配**：使用余弦相似度计算文本相关性
- **上下文构建**：将相关文档片段作为上下文传递给AI模型
- **回答验证**：确保AI回答严格基于知识库内容

#### 2.2.3 关键流程
```python
async def handle_ai_message(query: str, session_id: int, db: Session):
    # 1. 向量检索相关文档
    relevant_docs = vector_db.search(query, top_k=3)
    
    if not relevant_docs:
        # 无相关文档，转接人工
        return None, True
    
    # 2. 构建上下文和提示词
    prompt = build_rag_prompt(query, relevant_docs)
    
    # 3. 调用AI模型生成回答
    response = await call_ai_model(prompt)
    
    # 4. 验证回答是否基于知识库
    if not is_answer_based_on_knowledge(response, relevant_docs):
        return None, True
    
    return response, False
```

### 2.3 知识库管理模块

#### 2.3.1 功能说明
支持多种格式文档的上传、处理、存储和管理，为AI客服提供知识来源。

#### 2.3.2 文档处理流程
1. **文档上传**：支持PDF、Word、TXT等格式
2. **内容提取**：使用专业库提取文档文本内容
3. **文本分块**：将长文本分割成适合向量存储的小块
4. **向量嵌入**：生成文本的向量表示
5. **存储索引**：将向量和文本存储到向量数据库

#### 2.3.3 支持的文档格式

| 格式 | MIME类型 | 处理方式 | 依赖库 |
|------|----------|----------|--------|
| PDF | application/pdf | PyPDF2提取文本 | PyPDF2 |
| Word | application/vnd.openxmlformats-officedocument.wordprocessingml.document | docx2txt提取文本 | docx2txt |
| TXT | text/plain | 直接读取文本 | 内置 |
| Markdown | text/markdown | 解析Markdown格式 | markdown |

### 2.4 人工客服工作台模块

#### 2.4.1 功能说明
为人工客服提供处理会话的工作台，支持实时消息交互和会话管理。

#### 2.4.2 实时通信实现
- 使用Socket.IO建立WebSocket连接
- 支持多客服同时在线，自动分配会话
- 实现消息的实时推送和状态同步
- 支持会话转移和协作处理

#### 2.4.3 前端技术实现
```javascript
// Socket.IO连接初始化
const socket = io('http://localhost:8000', {
  auth: {
    token: userToken
  },
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000
});

// 监听新消息
socket.on('new_message', (data) => {
  if (data.session_id === currentSessionId) {
    addMessageToChat(data);
  } else {
    updateSessionList(data);
    showNotification(data);
  }
});
```

### 2.5 数据统计分析模块

#### 2.5.1 功能说明
收集和分析系统运行数据，提供可视化的统计报表。

#### 2.5.2 关键指标
- **会话统计**：总会话数、AI处理数、人工处理数
- **服务质量**：平均响应时间、用户满意度
- **知识库效果**：覆盖率、准确率、召回率
- **系统性能**：并发数、响应时间、错误率

#### 2.5.3 数据可视化
使用ECharts实现多种图表：
- 折线图：会话趋势分析
- 饼图：服务类型分布
- 柱状图：问题类型统计
- 雷达图：系统性能指标

## 3. 数据库设计

### 3.1 关系型数据库（MySQL）

#### 3.1.1 用户表（users）
| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | 用户ID |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 用户名 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| role | ENUM('admin', 'agent', 'user') | NOT NULL | 用户角色 |
| email | VARCHAR(100) | UNIQUE | 邮箱 |
| phone | VARCHAR(20) | | 手机号 |
| status | ENUM('active', 'inactive') | NOT NULL | 状态 |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

#### 3.1.2 会话表（customer_sessions）
| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | 会话ID |
| user_id | VARCHAR(50) | NOT NULL | 用户ID（微信openid） |
| user_name | VARCHAR(100) | NOT NULL | 用户名称 |
| user_avatar | VARCHAR(255) | | 用户头像 |
| status | ENUM('waiting', 'ai_handling', 'human_handling', 'completed', 'abandoned') | NOT NULL | 会话状态 |
| current_agent_id | INT | FOREIGN KEY | 当前处理客服ID |
| start_time | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 开始时间 |
| end_time | DATETIME | | 结束时间 |
| last_message_time | DATETIME | NOT NULL | 最后消息时间 |
| wait_duration | INT | | 等待时长(秒) |
| handling_duration | INT | | 处理时长(秒) |

#### 3.1.3 消息表（messages）
| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | 消息ID |
| session_id | INT | FOREIGN KEY, NOT NULL | 会话ID |
| sender | ENUM('user', 'ai', 'agent') | NOT NULL | 发送者类型 |
| sender_id | VARCHAR(50) | | 发送者ID |
| content | TEXT | NOT NULL | 消息内容 |
| message_type | ENUM('text', 'image', 'voice', 'video', 'file') | NOT NULL | 消息类型 |
| media_url | VARCHAR(255) | | 媒体文件URL |
| status | ENUM('sent', 'delivered', 'read') | NOT NULL | 消息状态 |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| is_from_knowledge | BOOLEAN | DEFAULT FALSE | 是否基于知识库 |

#### 3.1.4 知识库文档表（knowledge_documents）
| 字段名 | 数据类型 | 约束 | 描述 |
|--------|----------|------|------|
| id | INT | PRIMARY KEY, AUTO_INCREMENT | 文档ID |
| file_name | VARCHAR(255) | NOT NULL | 文件名 |
| file_path | VARCHAR(255) | NOT NULL | 文件路径 |
| file_size | INT | NOT NULL | 文件大小(字节) |
| file_type | VARCHAR(50) | NOT NULL | 文件类型 |
| status | ENUM('uploading', 'processing', 'processed', 'failed') | NOT NULL | 处理状态 |
| chunk_count | INT | DEFAULT 0 | 分块数量 |
| created_by | INT | FOREIGN KEY | 创建者ID |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 |
| error_message | TEXT | | 错误信息 |

### 3.2 向量数据库（ChromaDB）

#### 3.2.1 集合结构
- **集合名称**：`knowledge_base`
- **文档结构**：
  ```python
  {
      "content": "文本内容",
      "metadata": {
          "document_id": 1,
          "chunk_id": "1-1",
          "page": 1,
          "created_at": "2024-01-01T00:00:00Z"
      }
  }
  ```

#### 3.2.2 索引优化
- 使用HNSW（Hierarchical Navigable Small World）算法加速向量检索
- 配置适当的向量维度（默认1536维）
- 设置合理的相似度阈值（默认0.7）

## 4. API接口设计

### 4.1 RESTful API

#### 4.1.1 认证相关接口

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 用户登录 | POST | /api/auth/login | 用户登录认证 |
| 用户登出 | POST | /api/auth/logout | 用户登出 |
| 获取当前用户 | GET | /api/auth/me | 获取当前登录用户信息 |
| 刷新令牌 | POST | /api/auth/refresh | 刷新访问令牌 |

#### 4.1.2 知识库管理接口

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 上传文档 | POST | /api/knowledge/documents | 上传知识库文档 |
| 获取文档列表 | GET | /api/knowledge/documents | 获取文档列表 |
| 获取文档详情 | GET | /api/knowledge/documents/{id} | 获取文档详情 |
| 删除文档 | DELETE | /api/knowledge/documents/{id} | 删除文档 |
| 搜索知识库 | GET | /api/knowledge/search | 搜索知识库内容 |

#### 4.1.3 会话管理接口

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 获取会话列表 | GET | /api/sessions | 获取会话列表 |
| 获取会话详情 | GET | /api/sessions/{id} | 获取会话详情 |
| 获取会话消息 | GET | /api/sessions/{id}/messages | 获取会话消息 |
| 转接人工客服 | POST | /api/sessions/{id}/transfer | 转接人工客服 |
| 结束会话 | POST | /api/sessions/{id}/end | 结束会话 |

#### 4.1.4 统计分析接口

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 获取会话统计 | GET | /api/stats/sessions | 获取会话统计数据 |
| 获取服务质量统计 | GET | /api/stats/quality | 获取服务质量统计 |
| 获取知识库统计 | GET | /api/stats/knowledge | 获取知识库使用统计 |
| 获取系统性能统计 | GET | /api/stats/performance | 获取系统性能统计 |

### 4.2 WebSocket事件

#### 4.2.1 客户端事件

| 事件名 | 数据结构 | 描述 |
|--------|----------|------|
| send_message | `{session_id: int, content: string, message_type: string}` | 发送消息 |
| join_session | `{session_id: int}` | 加入会话 |
| leave_session | `{session_id: int}` | 离开会话 |
| typing | `{session_id: int, is_typing: boolean}` | 输入状态通知 |

#### 4.2.2 服务端事件

| 事件名 | 数据结构 | 描述 |
|--------|----------|------|
| new_message | `{session_id: int, message: object}` | 新消息通知 |
| session_updated | `{session_id: int, status: string}` | 会话状态更新 |
| agent_joined | `{session_id: int, agent: object}` | 客服加入通知 |
| agent_left | `{session_id: int}` | 客服离开通知 |
| typing_indicator | `{session_id: int, user_id: string, is_typing: boolean}` | 输入状态指示 |

## 5. 安全与性能优化

### 5.1 安全措施

#### 5.1.1 认证与授权
- 使用JWT（JSON Web Token）进行身份认证
- 实现基于角色的访问控制（RBAC）
- 密码使用bcrypt进行哈希存储
- 敏感操作需要二次验证

#### 5.1.2 数据安全
- 微信消息使用AES加密传输
- 敏感数据在数据库中加密存储
- 实现数据访问审计日志
- 定期数据备份和恢复测试

#### 5.1.3 API安全
- 实现请求频率限制（Rate Limiting）
- 防止SQL注入和XSS攻击
- 验证请求来源和Referer
- HTTPS加密传输

### 5.2 性能优化

#### 5.2.1 缓存策略
- Redis缓存热点数据和会话信息
- 缓存微信access_token避免频繁调用
- 缓存知识库搜索结果
- 实现多级缓存架构

#### 5.2.2 数据库优化
- 合理设计数据库索引
- 使用连接池管理数据库连接
- 实现数据库读写分离
- 定期数据库维护和优化

#### 5.2.3 异步处理
- 使用FastAPI的异步特性处理请求
- 文档处理使用后台任务异步执行
- 消息推送使用异步WebSocket
- 实现任务队列处理耗时操作

#### 5.2.4 负载均衡
- 支持多实例部署
- 会话状态在Redis中共享
- 实现客服工作负载均衡
- 支持水平扩展

## 6. 部署与运维

### 6.1 部署架构

#### 6.1.1 开发环境
- Docker Compose一键部署
- 本地开发服务器

#### 6.1.2 测试环境
- 独立的测试服务器
- 自动化测试脚本
- 模拟数据生成

#### 6.1.3 生产环境
- 容器化部署（Docker/Kubernetes）
- 负载均衡和高可用
- 监控和告警系统

### 6.2 配置管理

#### 6.2.1 环境变量
所有配置通过环境变量管理，支持不同环境的配置隔离：

```bash
# 数据库配置
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/wechat_customer_service

# Redis配置
REDIS_URL=redis://localhost:6379/0

# 微信配置
WECHAT_APPID=your_appid
WECHAT_APPSECRET=your_appsecret
WECHAT_TOKEN=your_token
WECHAT_ENCODING_AES_KEY=your_encoding_aes_key

# 豆包AI配置
DOUBAO_API_KEY=your_api_key
DOUBAO_API_SECRET=your_api_secret

# 系统配置
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 6.3 监控与日志

#### 6.3.1 日志系统
- 使用结构化日志格式
- 支持不同级别的日志（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- 日志轮转和归档
- 支持日志聚合和分析

#### 6.3.2 监控指标
- API请求量和响应时间
- 系统资源使用情况（CPU, 内存, 磁盘）
- 数据库连接和查询性能
- 微信消息处理延迟
- AI模型调用成功率

#### 6.3.3 告警机制
- 异常情况邮件/短信通知
- 性能指标超过阈值告警
- 服务不可用自动告警
- 定期健康检查

## 7. 开发与扩展指南

### 7.1 开发规范

#### 7.1.1 代码规范
- 遵循PEP 8 Python代码规范
- 使用Type Hints进行类型检查
- 完善的代码注释和文档
- 单元测试覆盖率要求

#### 7.1.2 Git工作流
- 使用Git Flow工作流
- 功能分支开发
- 代码审查机制
- 自动化CI/CD流程

### 7.2 扩展接口

#### 7.2.1 AI模型扩展
系统支持多种AI模型的接入，可以通过实现统一的接口来扩展：

```python
class AIModelInterface:
    """AI模型接口基类"""
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成回答"""
        raise NotImplementedError
    
    def get_model_info(self) -> dict:
        """获取模型信息"""
        raise NotImplementedError
```

#### 7.2.2 文档处理器扩展
支持扩展新的文档格式处理器：

```python
class DocumentProcessorInterface:
    """文档处理器接口基类"""
    
    def can_handle(self, file_type: str) -> bool:
        """检查是否支持该文件类型"""
        raise NotImplementedError
    
    def process(self, file_content: bytes) -> list:
        """处理文档内容"""
        raise NotImplementedError
```

#### 7.2.3 渠道接入扩展
支持扩展新的消息渠道：

```python
class MessageChannelInterface:
    """消息渠道接口基类"""
    
    async def send_message(self, user_id: str, content: str, **kwargs) -> bool:
        """发送消息"""
        raise NotImplementedError
    
    async def receive_message(self, message: dict) -> dict:
        """接收消息"""
        raise NotImplementedError
```

## 8. 故障处理与恢复

### 8.1 常见故障类型

#### 8.1.1 微信消息接收失败
- **原因**：网络问题、服务器配置错误、签名验证失败
- **处理**：检查网络连接、验证微信配置、查看日志错误信息

#### 8.1.2 AI模型调用失败
- **原因**：API密钥错误、配额用尽、网络超时
- **处理**：检查API凭证、增加重试机制、设置合理超时

#### 8.1.3 数据库连接异常
- **原因**：数据库服务停止、连接池耗尽、网络问题
- **处理**：监控数据库状态、调整连接池配置、实现故障转移

#### 8.1.4 WebSocket连接断开
- **原因**：网络波动、服务器重启、客户端异常
- **处理**：实现自动重连、会话状态恢复、心跳检测

### 8.2 容灾与恢复

#### 8.2.1 数据备份策略
- 数据库定期全量备份
- 增量备份和二进制日志
- 备份数据异地存储
- 定期恢复测试

#### 8.2.2 高可用设计
- 关键服务多实例部署
- 自动故障检测和转移
- 会话状态外部存储
- 支持灰度发布和回滚

#### 8.2.3 灾难恢复计划
- 制定详细的恢复流程
- 明确各角色责任
- 定期演练和测试
- 恢复时间目标（RTO）和恢复点目标（RPO）定义

## 9. 总结与展望

### 9.1 系统优势

1. **完整的解决方案**：从微信接入到AI回答再到人工兜底，形成完整闭环
2. **技术先进性**：采用现代化技术栈，支持异步处理和高并发
3. **可扩展性强**：模块化设计，支持多种AI模型和文档格式
4. **安全性高**：多层次安全措施，保护数据和通信安全
5. **运维友好**：完善的监控、日志和告警机制

### 9.2 未来规划

1. **多渠道支持**：扩展支持小程序、企业微信、APP等更多渠道
2. **智能路由**：基于AI的智能会话分配和路由
3. **情感分析**：识别用户情绪，提供个性化服务
4. **语音交互**：支持语音消息的识别和合成
5. **多语言支持**：扩展支持多语言客服
6. **自动化工作流**：基于规则的自动化处理流程
7. **知识图谱**：构建领域知识图谱，提升回答准确性
8. **模型微调**：基于业务数据进行模型微调优化

### 9.3 技术债务与改进方向

1. **代码优化**：部分紧急功能的代码需要重构和优化
2. **测试覆盖**：增加更多的单元测试和集成测试
3. **性能优化**：进一步优化向量检索和AI模型调用性能
4. **文档完善**：补充更多的开发文档和使用说明
5. **用户体验**：持续优化前端界面和交互体验