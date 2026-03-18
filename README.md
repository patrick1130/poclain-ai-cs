# Poclain Hydraulics 微信智能客服引擎 (Enterprise AGI Assistant)

## 📌 项目愿景

本项目是为 Poclain (波克兰液压) 定制开发的 S 级企业级人工智能技术支持系统。通过深度集成大语言模型 (LLM)、检索增强生成 (RAG) 以及微信公众平台全双工通信，为客户提供毫秒级、零幻觉、高度专业的液压技术参数查询与选型建议。

## 🚀 核心特性 (Core Features)

- **微信原生态接入**：支持微信公众平台标准消息流，底层防丢包重试与 5 秒超时熔断机制。
- **钢铁苍穹安全防御**：内置 `SecurityGuardian` 物理拦截器，免疫提示词注入 (Prompt Injection) 及脱口秀篡改攻击。
- **高保真 RAG 架构**：本地 ChromaDB 粗筛 (阈值 0.5) + 阿里云 GTE-Rerank 交叉精排，确保绝对的事实准确性。
- **品牌合规护城河**：代码级锁定 `Temperature=0.0`，全量剔除竞品 (如丹佛斯) 讨论，内置动态法务免责声明引擎。
- **全双工坐席监控**：基于 WebSockets 的管理端大屏，支持管理员实时介入与安全断流。

## 🛠️ 技术栈 (Tech Stack)

- **后端框架**: FastAPI, Uvicorn (Python 3.10+)
- **大模型引擎**: 阿里云百炼 (DeepSeek-v3 / Qwen), Dashscope API
- **向量数据库**: ChromaDB
- **关系型数据库**: MySQL (SQLAlchemy ORM + pymysql/aiomysql)
- **前端架构**: Vue 3, Element-Plus (管理后台)

## 📦 快速启动 (Quick Start)

* **环境准备**：
  ```bash
  python -m venv .venv
  source .venv/bin/activate  # Mac/Linux
  pip install -r requirements.txt
  ```


* **环境变量**： 复制 `.env.example` 为 `.env`，填入 `WX_TOKEN`、`DASHSCOPE_API_KEY` 等核心密钥。
* **启动服务**：

```bash
puvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
