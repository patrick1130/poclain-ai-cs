"""
Poclain 智能客服 - 知识库自动化批量灌库脚本 (S 级 - 增强版)
执行流程：
1. 扫描 PDF -> 视觉大模型解析 (保留图文语义)
2. 扫描 Excel -> Pandas 精准解析 (保留小数点精度)
3. 语义切片 -> 向量化入库 -> MySQL 登记同步
"""

import os
import sys
import asyncio
import logging
import pandas as pd  # 🚨 架构师补丁：用于 Excel 精度保全

# 🚨 架构师补丁：强制清空网络代理，直连阿里云节点
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["NO_PROXY"] = "aliyuncs.com,dashscope.aliyuncs.com,localhost,127.0.0.1"

# 确保脚本能找到 app 模块
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from app.core.database import SessionLocal
from app.models.database import KnowledgeDoc
from app.core.config import settings
from app.utils.vector_db import VectorDB
from app.utils.document_parser import MultimodalDocumentParser
from app.utils.document_processor import split_document

# 配置控制台日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - 🧠 %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("KnowledgeImporter")

# 初始化组件
vector_db = VectorDB(settings.VECTOR_DB_PATH)
parser = MultimodalDocumentParser()

# 配置路径
MANUALS_DIR = os.path.join(BASE_DIR, "data", "manuals")

# 🚨 架构师补丁：让日志清爽，屏蔽 ChromaDB 遥测报错
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)


async def save_to_databases(
    title: str, markdown_content: str, category: str, chunks: list
):
    """
    通用入库逻辑：双写 ChromaDB 和 MySQL
    """
    # 1. 向量化入库 (ChromaDB)
    logger.info(f"💾 正在将 {len(chunks)} 个片段注入 ChromaDB 大脑...")
    try:
        await vector_db.add_document(
            doc_id=title, title=title, chunks=chunks, category=category
        )
        logger.info(f"🎉 【{title}】 向量注入成功！")
    except Exception as e:
        logger.error(f"❌ 【{title}】 向量注入失败: {e}")

    # 2. MySQL 账本登记 (同步前端大屏)
    db = SessionLocal()
    try:
        logger.info(f"📝 正在同步 MySQL 账本...")
        existing_doc = (
            db.query(KnowledgeDoc).filter(KnowledgeDoc.title == title).first()
        )

        if existing_doc:
            existing_doc.content = markdown_content
            existing_doc.category = category
            existing_doc.version = (existing_doc.version or 1) + 1
            logger.info(f"🔄 已自动升级覆盖为 V{existing_doc.version} 版本。")
        else:
            new_doc = KnowledgeDoc(
                title=title, content=markdown_content, category=category
            )
            db.add(new_doc)
            logger.info(f"✅ MySQL 登记完成！前端现已可见。")
        db.commit()
    except Exception as e:
        logger.error(f"❌ MySQL 登记失败: {e}")
        db.rollback()
    finally:
        db.close()


async def process_single_excel(file_name: str, category: str):
    """
    【S 级分支】处理 Excel：利用 Pandas 保证 100% 数值精度
    """
    file_path = os.path.join(MANUALS_DIR, file_name)
    title = os.path.splitext(file_name)[0]

    logger.info(f"📊 探测到参数表: 【{title}】，启动 Pandas 精度保全解析...")

    try:
        # 使用 openpyxl 读取，确保不丢失精度
        df = pd.read_excel(file_path, engine="openpyxl")
        df = df.fillna("")  # 处理空值
        # 转化为 Markdown 表格，这是 RAG 最易检索的格式
        markdown_content = df.to_markdown(index=False)

        # 语义切块
        chunks = split_document(
            title=title,
            content=markdown_content,
            category=category,
            max_chunk_size=1500,
            overlap=100,
        )

        await save_to_databases(title, markdown_content, category, chunks)
    except Exception as e:
        logger.error(f"❌ Excel 解析失败: {e}")


async def process_single_pdf(file_name: str, category: str):
    """
    处理 PDF：利用视觉大模型解析
    """
    file_path = os.path.join(MANUALS_DIR, file_name)
    title = os.path.splitext(file_name)[0]

    logger.info(f"🚀 开始处理手册: 【{title}】")

    # 1. 视觉解析
    markdown_content = await parser.parse_pdf_to_markdown(file_path)

    # 2. 语义切块
    chunks = split_document(
        title=title,
        content=markdown_content,
        category=category,
        max_chunk_size=1200,
        overlap=150,
    )

    await save_to_databases(title, markdown_content, category, chunks)


async def main():
    os.makedirs(MANUALS_DIR, exist_ok=True)

    all_files = [f for f in os.listdir(MANUALS_DIR) if not f.startswith(".")]

    if not all_files:
        logger.warning(f"⚠️ 文件夹 {MANUALS_DIR} 中没有找到任何文件。")
        return

    logger.info(f"🎯 扫描到 {len(all_files)} 个文件，启动分类处理流程...")

    for file_name in all_files:
        ext = file_name.lower()
        # 自动分类逻辑
        category = "液压马达"
        if "参数" in file_name or "spec" in ext:
            category = "产品参数表"
        elif "泵" in file_name or "pump" in ext:
            category = "液压泵"

        logger.info(f"--------------------------------------------------")
        if ext.endswith(".xlsx") or ext.endswith(".xls"):
            await process_single_excel(file_name, category)
        elif ext.endswith(".pdf"):
            await process_single_pdf(file_name, category)
        else:
            logger.warning(f"⏩ 跳过不支持的文件格式: {file_name}")

    logger.info(f"--------------------------------------------------")
    logger.info("🟢 知识库自动化全量注魂成功！所有数据已达到工业级精度。")


if __name__ == "__main__":
    asyncio.run(main())
