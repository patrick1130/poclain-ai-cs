# Poclain 微信智能客服引擎 (Enterprise Edition)

这是一个专为 **Poclain Hydraulics (波克兰液压)** 设计的工业级 AI 客服系统。采用 **RAG (检索增强生成)** 架构，结合阿里云百炼 (DashScope) 大模型内核，实现了针对液压马达技术手册的精准问答与全双工人工接管链路。

---

## 🏗️ 系统物理架构 (System Architecture)

系统由五个核心层级组成，确保了高性能、高召回率与数据绝对隔离：

1. **离线数据预处理层 (ETL Pipeline)**: 引入 O(N*M) 复杂度的通用语义平铺引擎 (`data_flattener.py`)，将二维关系型 Excel 参数表物理重构为高密度 RAG 语义切片，从源头消灭切片断裂。
2. **接入网关层 (Nginx)**: 实施 S 级安全加固（HSTS、XSS-Protection、nosniff），处理 Vue 静态路由回退及 WebSocket 全双工协议升级。
3. **核心引擎层 (FastAPI)**: 异步非阻塞内核。集成 JWT 鉴权、WebSocket 实时分发，以及搭载 **O(K) 双轨制自适应混合检索** 的路由逻辑。
4. **向量大脑 (Vector Brain)**: 物理隔离的本地 ChromaDB 向量数据库。在 Python 内存层强制进行字面量型号锁定与语义降级探测，确保零漏检。
5. **前端视窗 (Vue3/Vite)**:
   * **Agent Workbench**: 坐席实时工作台，支持人工一键强行接管/静默 AI 会话。
   * **Customer H5**: 适配微信环境，集成 **OAuth2.0 静默授权引擎**，支持本地沙盒调试与生产环境动态切换。

---

## 🛡️ 安全协议与防线 (Security Protocol)

* **双环境鉴权 (Hybrid Auth)**:
  * **坐席端**: 基于 JWT (RS256) 的短效令牌。
  * **访客端**: 基于微信 OpenID 的物理识别。本地开发环境自动降级为 UUID 安全沙盒。
* **物理连接防线**:
  * WebSocket 连接池动态回收机制，防止数据库会话 (DB Session) 长期占用导致的资源干涸。
  * 后端负载溢出拦截 (Max Payload Size: 64KB)，防御恶意 Payload 炸弹攻击。
* **S 级 AI 业务沙盒 (钢铁苍穹)**:
  * **极致确定性**: 大模型 `Temperature` 强制锁定为 `0.1`，兼顾自然对话流畅度与物理防幻觉。
  * **商业合规断路器**: 物理锁死越权背书权限，严禁 AI 捏造 Poclain 与第三方客户（如三一、徐工）的虚假商业案例。
  * **BOM 级数据原教旨主义**: 强制 100% 像素级复刻官方工业名词与数量单位（严禁私自将 `1 x PM20` 篡改为 `1台`），彻底剥夺大模型的“语言润色”权限。

---

## 🚀 快速起航 (Getting Started)

### 1. 环境依赖 (Prerequisites)

* Docker & Docker-Compose (生产环境推荐)
* Python 3.10+
* Node.js 18+

### 2. 本地物理隔离启动 (Local Sandbox)

```bash
# 克隆仓库
git clone [https://github.com/你的用户名/poclain-ai-cs.git](https://github.com/你的用户名/poclain-ai-cs.git)
cd poclain-ai-cs

# 启动全栈容器阵列
docker-compose up -d --build
```

### 3. 数据冷启动与向量大脑初始化 (Knowledge Injection)

严禁直接导入原始表格！必须先执行 ETL 清洗流程：

**Bash**

```
# Step 1: 执行 O(N*M) 语义平铺，将业务 Excel 转化为 AI 易读文本
python utils/data_flattener.py

# Step 2: 登录系统管理后台，清空旧索引，并将生成的 knowledge_base_flattened.txt 上传注入向量大脑
```

---

## 🛠️ 技术栈清单 (Tech Stack)


| **模块**          | **技术实现**           | **核心价值**                                 |
| ----------------- | ---------------------- | -------------------------------------------- |
| **API Framework** | FastAPI                | 高并发异步处理，O(1) 路由寻址                |
| **ORM / DB**      | SQLAlchemy / MySQL 8.0 | 结构化数据持久化与急加载 (selectin) 优化     |
| **Data ETL**      | Pandas / 自研引擎      | O(N\*M) 降维平铺，消灭数据歧义               |
| **Real-time**     | WebSocket (Native)     | 全双工双向通信，毫秒级响应人工接管           |
| **Vector DB**     | ChromaDB + 双轨算法    | 本地私有化存储，物理锁定型号，拒绝幻觉       |
| **UI Engine**     | Vue 3.x + Element Plus | 响应式大屏坐席台 & 微信端 H5                 |
| **LLM Interface** | DashScope (Qwen-Max)   | 针对中文工业语料优化的推理能力，温度锁死 0.1 |

---

## 📜 归档记录 (Changelog)

* **v2.0.0-rc.1 (Current)**:
  * 🚀 重构底层 RAG 检索链路，引入 O(K) 动态型号嗅探与纯语义降级双轨制。
  * 🛡️ 实装 ETL 语义平铺引擎，彻底解决 Token 截断导致的参数乱编。
  * 🔒 部署 BOM 级防幻觉沙箱与商业合规红线，阉割模型过度润色权限。
* **v1.0.0-rc.1**:
  * ✅ 完成 S 级安全审计，修复 WebSocket 连接池漏洞。
  * ✅ 补全微信 OAuth2.0 授权链路与本地沙盒降级逻辑。
  * ✅ 优化 Vite 环境环境变量探针，解决白屏崩溃隐患。

---

## 👤 联系与维护

**Patrick** - Senior Lead Developer

*Poclain Hydraulics (Shanghai) Co., Ltd.*
