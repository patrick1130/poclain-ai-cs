# Poclain 微信 AI 智能客服系统技术文档

## 1. 系统架构概述

本项目是为 Poclain (波克兰液压) 定制开发的工业级人工智能技术支持系统。系统采用现代化的微服务架构设计，实现了“高保真 RAG 知识库客服 + 物理级安全防护 + 人工实时兜底”的完整企业级解决方案，彻底根绝了工业参数领域的“AI 幻觉”。

### 1.1 分层架构

**Plaintext**

```
+---------------------------------------------------+
|               离线数据预处理层 (ETL)              |
| Excel -> 通用语义平铺引擎 (Semantic Flattening)   |
+---------------------------------------------------+
                         ↓
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
|                 核心认知引擎层                    |
| O(K) 双轨制混合检索 | 防幻觉沙箱 | LLM 推理生成   |
+---------------------------------------------------+
                         ↓
+---------------------------------------------------+
|                 数据与持久化层                    |
|    MySQL(业务) | Redis(缓存/PubSub) | ChromaDB    |
+---------------------------------------------------+
```

### 1.2 技术栈选择 (生产级基线)


| **类别**     | **技术 / 组件**             | **选型理由**                                           |
| ------------ | --------------------------- | ------------------------------------------------------ |
| 后端框架     | FastAPI 0.104+              | 高性能异步框架，原生支持 WebSocket 与高并发调度        |
| 大语言模型   | 阿里云百炼 (DashScope)      | 主引擎`Qwen-Max`，工业逻辑推理能力强，温度锁定 0.1     |
| 数据清洗引擎 | 自研`universal_flattener`   | O(N\*M) 复杂度，将二维表格物理平铺为高密度语义切片     |
| 向量数据库   | ChromaDB                    | 本地轻量级向量检索，配合 Python 内存层过滤实现精准召回 |
| 关系型数据   | MySQL + SQLAlchemy 2.0      | `selectin`现代化急加载策略，杜绝 N+1 性能瓶颈          |
| 实时通信     | WebSockets                  | 全双工通信，支持管理员大屏实时监控与会话接管           |
| 核心安全     | `pycryptodome`/`defusedxml` | 抵御 XML 炸弹，支持微信 AES-CBC 硬件级解密             |

---

## 2. 核心功能模块与 S 级防御设计

### 2.1 微信消息网关模块

#### 2.1.1 物理级安全防线

系统在接入层引入了硬件级的并发与恶意流量防护：

* **滑动窗口限流器 (Rate Limiter)**：基于内存的 **O(1)** 拦截，单 OpenID 限制频率，防御 CC 刷单攻击。
* **Payload 截断防护**：强制截断所有超过 1000 字符的输入，防止内存溢出 (OOM) 与超长 Context 攻击。

### 2.2 认知引擎与合规模块 (核心重构)

#### 2.2.1 增强型 RAG：O(K) 双轨制自适应混合检索

彻底抛弃了脆弱的数据库底层布尔过滤，将逻辑上移至 Python 内存层：

1. **轨 1：严格型号锁定 (Exact Match)**：利用正则嗅探用户提问中的工业型号（如 `MS18`），在召回的 Top 15 切片中强制进行字面量匹配，防型号张冠李戴。
2. **轨 2：语义宽泛召回 (Semantic Fallback)**：当未探测到具体型号时，自动降级为纯语义检索，保障“售后政策”、“故障排查”等通用咨询的召回率。

#### 2.2.2 钢铁苍穹 (Security & Compliance)

* **指令注入防火墙 (`SecurityGuardian`)**：前置正则扫描，瞬间拦截带有“忽略设定”、“扮演角色”等特征的越狱 Prompt。
* **反商业幻觉断路器 (Anti-Commercial Hallucination)**：底层硬编码红线，严禁 AI 擅自捏造 Poclain 与第三方品牌（如三一、徐工、维特根）的虚假合作案例及商业背书。
* **BOM 级数据原教旨主义 (Data Fundamentalism)**：剥夺 AI 的自然语言“润色”本能。强制要求输出配置清单时，必须【像素级】复刻知识库，严禁替换专业词汇（如“行走泵”），严禁私自添加中文量词（强制使用 `1 x PM20` 而非 `1台`）。

#### 2.2.3 核心处理伪代码

**Python**

```
async def handle_ai_response_impl(context):
    # 1. 双轨制自适应混合检索 (型号嗅探 + 语义降级)
    docs = await vector_db.search(context.content, top_k=5, threshold=0.05)
  
    # 2. 注入绝对隔离的防幻觉 System Prompt (包含 BOM 级死命令)
    system_prompt = load_base_sop().replace("{knowledge}", docs)
  
    # 3. 严格受控的 LLM 流式/同步生成 (Temperature 锁定 0.1，防发散)
    raw_answer = await _call_bailian_api(context.content, system_prompt)
  
    # 4. 业务状态机判断 (工作时间外自动转 OOO 表单，命中销售意图流转路由表)
    final_answer = apply_business_logic(raw_answer)
  
    # 5. 落库并下发微信 / 广播至坐席 WebSocket
    await _finalize_ai_reply(context, final_answer)
```

### 2.3 人工客服工作台模块

* 支持 WebSocket 实时监听微信会话流。
* 客服介入时，系统自动将状态切换为 `ACTIVE`，AI 引擎被物理静默，客服回复直达用户微信，杜绝“机器抢答”。

---

## 3. 数据库核心设计

### 3.1 关系型数据库优化 (MySQL)

为避免 SQLAlchemy 的全表扫描隐患，系统已全面废除 `lazy="dynamic"`。

#### 3.1.1 动态配置表 (`prompt_configs`)


| **字段名**    | **类型**    | **约束**      | **描述**                |
| ------------- | ----------- | ------------- | ----------------------- |
| config\_key   | VARCHAR(50) | UNIQUE, INDEX | 配置键 (如`system_sop`) |
| config\_value | TEXT        |               | 核心系统提示词与路由表  |

*(注：系统底层内置了 Fallback 级 SOP，即使此表数据被误删，核心防幻觉防线依然生效)*

---

## 4. 关键环境配置清单

系统强制使用 `.env` 文件隔离所有敏感密钥。生产环境必须配置以下参数：

**Ini, TOML**

```
# --- 数据库与中间件 ---
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/poclain_ai
VECTOR_DB_PATH=./chroma_db

# --- 微信公众平台凭证 (安全模式) ---
WECHAT_APPID=your_appid
WECHAT_APPSECRET=your_appsecret
WECHAT_TOKEN=your_token
WECHAT_ENCODING_AES_KEY=your_encoding_aes_key 

# --- 阿里云百炼大模型引擎 ---
DASHSCOPE_API_KEY=sk-your-aliyun-key
PRIMARY_CHAT_MODEL=qwen-max  
```

---

## 5. 部署指南与数据冷启动

### 5.1 数据 ETL 预处理 (冷启动必做)

在启动后端服务前，必须运行离线平铺脚本，将关系型工业数据转化为 AI 易读语料：

**Bash**

```
# 将业务 Excel 置于同级目录，运行平铺引擎
python data_flattener.py
# 输出 knowledge_base_flattened.txt 后，通过管理后台上传至 ChromaDB
```

### 5.2 生产环境启动 (推荐架构)

严禁在生产环境直接使用 `python main.py`。使用 Gunicorn 配合 Uvicorn Worker 守护进程：

**Bash**

```
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 120
```

### 5.3 合规提醒

由于对接微信公众平台，绑定的生产域名必须拥有**企业主体 ICP 备案**，并配置强制 HTTPS (TLS 1.2+)。
