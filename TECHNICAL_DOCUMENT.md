这是一份基于我们近期所有\*\*“S 级架构加固”**与**“业务逻辑重构”**（包括阿里百炼大模型切换、GTE-Rerank 交叉重排、SecurityGuardian 物理防火墙、并发限流、免责声明正则清洗等）全面更新后的**《Poclain 微信智能客服系统技术文档》\*\*。

你可以直接用这份文档覆盖之前的旧版本：

---

# Poclain 微信 AI 智能客服系统技术文档

## 1. 系统架构概述

本项目是为 Poclain (波克兰液压) 定制开发的工业级人工智能技术支持系统。系统采用现代化的微服务架构设计，实现了"高保真 RAG 知识库客服 + 物理级安全防护 + 人工实时兜底"的完整企业级解决方案。

### 1.1 分层架构

**Plaintext**

```
+---------------------------------------------------+
|                     用户层                        |
|             微信公众号 (原生消息流)               |
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|               接入与安全防线层                    |
| 微信签名校验 | 滑动窗口 CC 限流 | 注入攻击正则拦截|
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|                  核心认知引擎层                   |
| RAG 粗筛(Chroma) | GTE-Rerank 精排 | LLM 推理生成 |
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|                  数据与持久化层                   |
|    MySQL(业务) | Redis(缓存/PubSub) | 向量数据库  |
+---------------------------------------------------+
```

### 1.2 技术栈选择 (已升级为生产级)


| **类别**   | **技术 / 组件**             | **选型理由**                                    |
| ---------- | --------------------------- | ----------------------------------------------- |
| 后端框架   | FastAPI 0.104+              | 高性能异步框架，原生支持 WebSocket 与高并发调度 |
| 大语言模型 | 阿里云百炼 (DashScope)      | 主引擎`DeepSeek-v3`/`Qwen`，工业逻辑推理能力强  |
| 重排模型   | `gte-rerank`                | S 级交叉重排引擎，将知识片段浓缩提纯至 Top 3    |
| 向量数据库 | ChromaDB                    | 本地轻量级向量检索，支持阈值硬性过滤            |
| 关系型数据 | MySQL + SQLAlchemy 2.0      | `selectin`现代化急加载策略，杜绝 N+1 性能瓶颈   |
| 实时通信   | WebSockets                  | 全双工通信，支持管理员大屏实时监控与会话接管    |
| 核心安全   | `pycryptodome`/`defusedxml` | 抵御 XML 炸弹，支持微信 AES-CBC 硬件级解密      |
| 前端中台   | Vue3 + Element Plus         | 现代化中后台 UI，支持 AI 参数热重载             |

---

## 2. 核心功能模块与 S 级防御设计

### 2.1 微信消息网关模块

#### 2.1.1 物理级安全防线

系统在接入层不仅负责解密，更引入了硬件级的并发与恶意流量防护：

* **滑动窗口限流器 (Rate Limiter)**：基于内存的 **\$O(1)\$** 拦截，单个 OpenID 限制 `60秒内最多10次请求`，防御 CC 刷单攻击。
* **Payload 截断防护**：强制截断所有超过 1000 字符的输入，防止内存溢出 (OOM) 攻击。

### 2.2 认知引擎与合规模块 (核心重构)

#### 2.2.1 增强型 RAG (Retrieval-Augmented Generation)

彻底抛弃了传统的“单次检索+生成”，采用工业级双段检索：

1. **高阈值粗筛**：向 ChromaDB 请求 Top 15 片段，硬性设定最低匹配阈值 `0.5`，过滤无关噪音。如果未命中，直接向 LLM 注入“资料缺失警告”。
2. **交叉重排 (Cross-Encoder)**：调用阿里 `gte-rerank`，对粗筛结果进行二次语义打分，提纯出最核心的 Top 3 片段。

#### 2.2.2 钢铁苍穹 (Security & Compliance)

* **指令注入防火墙 (`SecurityGuardian`)**：前置正则扫描，瞬间拦截带有“忽略设定”、“扮演角色”、“脱口秀”等特征的恶意 Prompt，不消耗 LLM 算力。
* **极致确定性锁**：后端代码强制锁定大模型 `temperature=0.0`，彻底剥夺 AI 的“创造力”与“幽默感”，根绝型号伪造 (如 `MSF05`) 等幻觉现象。
* **免责声明自动清洗**：利用正则表达式强行切除 LLM 惯性生成的免责废话，并在最后统一挂载 Poclain 官方硬编码声明，实现“首条重度告知，后续极简脚注”。

#### 2.2.3 核心处理伪代码

**Python**

```
async def handle_ai_response_impl(context):
    # 1. 高阈值粗筛 (Threshold: 0.5)
    raw_docs = vector_db.search(context.content, top_k=15, threshold=0.5)
  
    # 2. Reranker 交叉重排
    refined_docs = await _call_reranker(context.content, raw_docs)
  
    # 3. 严格受控的 LLM 生成 (Temperature 0.0)
    raw_answer = await generate_answer(context.content, refined_docs)
  
    # 4. 正则清洗幻觉声明，附加官方合规免责条款
    clean_answer = re.sub(r"⚠️?免责声明.*", "", raw_answer)
    final_answer = append_official_disclaimer(clean_answer, session_msg_count)
  
    # 5. 安全截断并下发微信
    await send_wx_msg(context.openid, _safe_truncate(final_answer))
```

### 2.3 人工客服工作台模块

* 支持 WebSocket 实时监听微信会话流。
* 客服介入时，系统自动将状态切换为 `human_handling`，AI 引擎被静默，客服回复直达用户微信。

---

## 3. 数据库核心设计

### 3.1 关系型数据库优化 (MySQL)

为避免 SQLAlchemy 的全表扫描隐患，系统已全面废除 `lazy="dynamic"`，采用 `lazy="selectin"` 急加载策略。

#### 3.1.1 客服坐席表 (`service_agents`)


| **字段名**     | **类型**     | **约束**        | **描述**       |
| -------------- | ------------ | --------------- | -------------- |
| id             | INT          | PK              | 坐席内部ID     |
| username       | VARCHAR(50)  | UNIQUE          | 登录账号       |
| password\_hash | VARCHAR(255) | NOT NULL        | bcrypt加密哈希 |
| role           | VARCHAR(20)  | DEFAULT 'agent' | 权限角色       |

#### 3.1.2 会话与消息表 (`customer_sessions` & `messages`)

引入了严格的外键约束与级联删除 (`cascade="all, delete-orphan"`)，防止僵尸数据占用空间。支持 `user`, `ai`, `agent` 三方消息身份标识。

#### 3.1.3 系统动态配置表 (`system_configs`)


| **字段名**                                                                  | **类型**     | **约束**      | **描述**                      |
| --------------------------------------------------------------------------- | ------------ | ------------- | ----------------------------- |
| config\_key                                                                 | VARCHAR(50)  | UNIQUE, INDEX | 配置键 (如`vector_threshold`) |
| config\_value                                                               | VARCHAR(255) |               | 配置值                        |
| *说明：前端 UI 可通过此表热重载 RAG 的搜索阈值与召回数量，无需重启服务器。* |              |               |                               |

---

## 4. 关键环境配置清单

系统强制使用 `.env` 文件隔离所有敏感密钥。生产环境必须配置以下参数：

**Ini, TOML**

```
# --- 数据库与中间件 ---
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/poclain_ai
REDIS_URL=redis://localhost:6379/0

# --- 微信公众平台凭证 (安全模式) ---
WECHAT_APPID=your_appid
WECHAT_APPSECRET=your_appsecret
WECHAT_TOKEN=your_token
WECHAT_ENCODING_AES_KEY=your_encoding_aes_key # 必须配置，启用硬件级解密

# --- 阿里云百炼大模型引擎 ---
DASHSCOPE_API_KEY=sk-your-aliyun-key
PRIMARY_CHAT_MODEL=qwen-max  # 主力逻辑模型
BACKUP_CHAT_MODEL=qwen-plus  # 故障降级模型

# --- 安全与加密 ---
SECRET_KEY=your_jwt_secret_key
ALGORITHM=HS256
```

---

## 5. 故障处理与性能调优

### 5.1 典型风险与应对策略

#### 5.1.1 微信被动回复 5 秒超时熔断

* **原因**：RAG 检索 + LLM 推理耗时偶尔会超过微信官方的 5 秒硬性限制。
* **处理**：系统采用“异步剥离”设计，先向微信返回空串（`success`）挂起连接，待 AI 生成完毕后，调用微信的**客服消息主动发送接口 (`/cgi-bin/message/custom/send`)** 进行投递。

#### 5.1.2 Token 爆炸 (Context Length Exceeded)

* **原因**：用户提问过于复杂，召回了大量超长说明书。
* **处理**：通过前端【系统设置】或数据库 `system_configs`，将 `Top K` 参数硬性限制在 5 以内；多轮对话记忆 `chat_history` 强制截取最近的 7 条交互。

#### 5.1.3 AI 幻觉与违规报价

* **原因**：模型过度自信或遭遇恶意绕过指令。
* **处理**：检查代码中 `_call_bailian_api_with_fallback` 的 `temperature` 是否严格保持为 `0.0`；在 System Prompt 中维持“禁止对丹佛斯等竞品进行对比”和“严禁报价，引导至人工”的绝对红线指令。

---

## 6. 部署指南

### 6.1 依赖安装

系统已通过严格的依赖审查，包含工业级安全加密库。

**Bash**

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 6.2 生产环境启动 (推荐架构)

严禁在生产环境直接使用 `python main.py`。建议使用 Gunicorn 配合 Uvicorn Worker 守护进程：

**Bash**

```
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 120
```

### 6.3 合规提醒

由于对接微信公众平台，绑定的生产域名必须拥有**企业主体 ICP 备案**（禁止使用个人备案，防止涉商业类目触发微信接口物理封禁），并配置强制 HTTPS (TLS 1.2+)。
