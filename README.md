# Poclain 微信智能客服引擎 (Enterprise Edition)

这是一个专为 **Poclain Hydraulics (波克兰液压)** 设计的工业级 AI 客服系统。采用 **RAG (检索增强生成)** 架构，结合阿里云百炼 (DashScope) 大模型内核，实现了针对液压马达技术手册的精准问答与全双工人工接管链路。

---

## 🏗️ 系统物理架构 (System Architecture)

系统由四个核心层级组成，确保了高性能与数据隔离：

1. **接入网关层 (Nginx)**: 实施 S 级安全加固（HSTS、XSS-Protection、nosniff），处理 Vue 静态路由回退及 WebSocket 全双工协议升级。
2. **核心引擎层 (FastAPI)**: 异步非阻塞内核。集成 JWT 鉴权、WebSocket 实时分发，以及基于 **ChromaDB** 的向量检索逻辑。
3. **向量大脑 (Vector Brain)**: 物理隔离的本地向量数据库。将 PDF/Markdown 技术手册通过 `text-embedding-v2` 嵌入模型转化为高维向量。
4. **前端视窗 (Vue3/Vite)**:
   * **Agent Workbench**: 坐席实时工作台，支持人工强行接管 AI 会话。
   * **Customer H5**: 适配微信环境，集成 **OAuth2.0 静默授权引擎**，支持本地沙盒调试与生产环境动态切换。

---

## 🛡️ 安全协议与防线 (Security Protocol)

* **双环境鉴权 (Hybrid Auth)**:
  * **坐席端**: 基于 JWT (RS256) 的短效令牌。
  * **访客端**: 基于微信 OpenID 的物理识别。本地开发环境自动降级为 UUID 安全沙盒。
* **物理连接防线**:
  * WebSocket 连接池动态回收机制，防止数据库会话 (DB Session) 长期占用导致的资源干涸。
  * 后端负载溢出拦截 (Max Payload Size: 64KB)，防御恶意大包攻击。
* **AI 安全沙盒**:
  * 大模型 `Temperature` 强制锁定为 `0.0`，从物理层消除 AI “幻觉”。
  * Prompt 注入防护：在上下文注入阶段采用 XML Tag 隔离技术。

---

## 🚀 快速起航 (Getting Started)

### 1. 环境依赖 (Prerequisites)

* Docker & Docker-Compose (生产环境推荐)
* Python 3.10+
* Node.js 18+

### 2. 本地物理隔离启动 (Local Sandbox)

**Bash**

```
# 克隆仓库
git clone https://github.com/你的用户名/poclain-ai-cs.git
cd poclain-ai-cs

# 启动全栈容器阵列
docker-compose up -d --build
```

### 3. 初始化向量大脑 (Knowledge Injection)

将液压产品手册放入 `backend/data/manuals/`，执行：

**Bash**

```
docker exec -it poclain_wechat_backend python import_knowledge.py
```

---

## 🛠️ 技术栈清单 (Tech Stack)


| **模块**          | **技术实现**           | **核心价值**                     |
| ----------------- | ---------------------- | -------------------------------- |
| **API Framework** | FastAPI                | 高并发异步处理，O(1) 路由寻址    |
| **ORM / DB**      | SQLAlchemy / MySQL 8.0 | 结构化数据持久化与会话追踪       |
| **Real-time**     | WebSocket (Native)     | 全双工双向通信，毫秒级响应       |
| **Vector DB**     | ChromaDB               | 本地私有化语料存储，保障数据合规 |
| **UI Engine**     | Vue 3.x + Element Plus | 响应式大屏坐席台 & 微信端 H5     |
| **LLM Interface** | DashScope (Qwen-Max)   | 针对中文工业语料优化的推理能力   |

---

## 📜 归档记录 (Changelog)

* **v1.0.0-rc.1**:
  * ✅ 完成 S 级安全审计，修复 WebSocket 连接池漏洞。
  * ✅ 补全微信 OAuth2.0 授权链路与本地沙盒降级逻辑。
  * ✅ 优化 Vite 环境环境变量探针，解决白屏崩溃隐患。

---

## 👤 联系与维护

**Patrick** - Senior Security & Performance Architect

*Poclain Hydraulics (Shanghai) Co., Ltd.*

---

### 🏁 最终操作建议：

1. **创建文件**：在终端执行 `touch README.md`，然后粘贴上述内容。
2. **最后一次归档提交**：
   **Bash**

   ```
   git add README.md
   git commit -m "docs: 建立工业级项目架构白皮书"
   git push origin main
   ```


```
