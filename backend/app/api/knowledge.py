from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging
import io
import httpx
import re
import pandas as pd

from ..core.database import get_db
from ..models.database import KnowledgeDoc
from ..core.config import settings
from ..utils.vector_db import VectorDB
from ..utils.document_processor import split_document

# 初始化日志记录器
logger = logging.getLogger(__name__)
router = APIRouter()

# 初始化全局组件：向量数据库和用于 CPU 密集型任务的进程池
vector_db = VectorDB(settings.VECTOR_DB_PATH)
process_pool = ProcessPoolExecutor(max_workers=2)

# ==========================================
# 1. Pydantic 数据模型定义
# ==========================================


class KnowledgeDocResponse(BaseModel):
    """基础文档信息响应模型"""

    id: int
    title: str
    category: str
    version: int
    create_time: datetime
    update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class KnowledgeDocDetailResponse(KnowledgeDocResponse):
    """带内容的详细文档响应模型"""

    content: str


# ==========================================
# 2. 内部逻辑辅助函数 (同步解析与异步增强)
# ==========================================


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """利用 PyMuPDF (fitz) 提取 PDF 文本内容"""
    import fitz

    text_content = []
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text_content.append(page.get_text())
        return "\n".join(text_content)
    except Exception as e:
        logger.error(f"PDF 解析失败: {e}")
        raise ValueError(f"PDF 文件结构异常: {str(e)}")


def _extract_text_from_excel(excel_bytes: bytes) -> str:
    """🚨 架构师补丁：利用 Pandas 确保 Excel 小数点精度不丢失"""
    try:
        # 使用 openpyxl 引擎确保读取原始数值
        df_dict = pd.read_excel(
            io.BytesIO(excel_bytes), sheet_name=None, engine="openpyxl"
        )
        text_content = []
        for sheet_name, df in df_dict.items():
            text_content.append(f"【表格区域: {sheet_name}】")
            # 过滤全空行
            df.dropna(how="all", inplace=True)
            # 核心：转化为 Markdown 字符串，Pandas 会自动保留 29.5 这种浮点精度
            markdown_table = df.to_markdown(index=False)
            # 业务逻辑补丁：将连体型号(如 MG02/MGE02)进行语义炸裂处理
            clean_table = re.sub(
                r"([A-Za-z0-9]+)[-/]([A-Za-z0-9]+)",
                r"\1 和 \2 (这两种型号通用上述参数)",
                markdown_table,
            )
            text_content.append(clean_table)
            text_content.append("")
        return "\n".join(text_content)
    except Exception as e:
        logger.error(f"Excel 解析失败: {e}")
        raise ValueError(f"Excel 矩阵读取失败: {str(e)}")


async def _enrich_single_chunk(
    client: httpx.AsyncClient, chunk: str, sem: asyncio.Semaphore
) -> str:
    """调用大模型对清洗后的碎片进行语义补全"""
    async with sem:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        }
        payload = {
            "model": settings.PRIMARY_CHAT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个工业数据专家。请将以下文档碎片重写为语义完整的自然语言描述，补全上下文参数，严禁输出问候语。",
                },
                {"role": "user", "content": f"原始碎片内容：\n{chunk}"},
            ],
            "temperature": 0.1,
        }
        try:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"大模型清洗碎片失败，保留原始版本: {e}")
            return chunk


async def _async_enrich_chunks(chunks: List[str]) -> List[str]:
    """并发执行大模型增强任务"""
    sem = asyncio.Semaphore(5)
    # 🚨 架构师修正：强制移除 verify=False，杜绝中间人劫持与证书伪造攻击
    async with httpx.AsyncClient(timeout=40.0, verify=True) as client:
        tasks = [_enrich_single_chunk(client, chunk, sem) for chunk in chunks]
        return await asyncio.gather(*tasks)


# ==========================================
# 3. 业务路由接口
# ==========================================


@router.get("/docs", response_model=List[KnowledgeDocResponse])
def get_knowledge_docs(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取文档列表：包含搜索、分类过滤和分页 (修复前端 404)"""
    query = db.query(KnowledgeDoc)
    if category:
        query = query.filter(KnowledgeDoc.category == category)
    if keyword:
        query = query.filter(
            KnowledgeDoc.title.contains(keyword)
            | KnowledgeDoc.content.contains(keyword)
        )

    # 逻辑：在前端展示时，对于同名文件只显示最高版本的记录
    subquery = (
        db.query(
            KnowledgeDoc.title, func.max(KnowledgeDoc.version).label("max_version")
        )
        .group_by(KnowledgeDoc.title)
        .subquery()
    )

    query = query.join(
        subquery,
        (KnowledgeDoc.title == subquery.c.title)
        & (KnowledgeDoc.version == subquery.c.max_version),
    )

    offset = (page - 1) * page_size
    docs = (
        query.order_by(KnowledgeDoc.create_time.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return docs


@router.get("/docs/{doc_id}", response_model=KnowledgeDocDetailResponse)
def get_knowledge_doc(doc_id: int, db: Session = Depends(get_db)):
    """获取特定文档的详细 Markdown 内容"""
    db_doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not db_doc:
        raise HTTPException(status_code=404, detail="该文档在账本中不存在")
    return db_doc


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    S 级上传路由：
    1. 动态识别文件类型 (PDF/Excel)，高保真提取文本
    2. 智能版本控制：同名文件自动升级版本
    3. 物理覆盖：自动擦除旧版本向量，防止 AI 检索到脏数据
    """
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in ["txt", "md", "pdf", "xlsx", "xls"]:
        raise HTTPException(
            status_code=400, detail="不支持的格式。请上传 PDF, Excel, TXT 或 MD 文件。"
        )

    # 读取文件流
    content_bytes = await file.read()
    title = file.filename.rsplit(".", 1)[0]

    content = ""
    try:
        loop = asyncio.get_running_loop()
        # 根据后缀分流解析任务到进程池
        if file_ext == "pdf":
            content = await loop.run_in_executor(
                process_pool, _extract_text_from_pdf, content_bytes
            )
        elif file_ext in ["xlsx", "xls"]:
            content = await loop.run_in_executor(
                process_pool, _extract_text_from_excel, content_bytes
            )
        else:
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = content_bytes.decode("gbk")
    except Exception as e:
        logger.error(f"解析过程崩溃: {e}")
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="文档中未发现有效文本内容。")

    # ==========================================
    # 🚨 架构师核心修改区：版本控制与物理擦除
    # ==========================================

    # 1. 查找是否存在同名文档，计算新版本号
    existing_doc = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.title == title)
        .order_by(KnowledgeDoc.version.desc())
        .first()
    )
    new_version = (existing_doc.version + 1) if existing_doc else 1

    # 2. 登记 MySQL 账本 (带上计算好的版本号)
    db_doc = KnowledgeDoc(
        title=title, content=content, category=category, version=new_version
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    doc_id = db_doc.id

    try:
        # 3. 入库前物理清洗旧版本向量，防止“向量分身”
        if existing_doc:
            try:
                await vector_db.delete_document(title)
                logger.info(f"♻️ 检测到同名文档更新，已清理历史向量数据：{title}")
            except Exception as e:
                logger.warning(f"清理历史向量失败 (可能原先就不存在): {e}")

        # 4. 语义切片
        chunks = await loop.run_in_executor(
            process_pool, split_document, title, content, category
        )

        # 5. 大模型深度清洗 (与 import_knowledge.py 保持同等洗数据能力)
        enriched_chunks = await _async_enrich_chunks(chunks)

        # 6. 核心写入
        await vector_db.add_document(
            doc_id=title, title=title, chunks=enriched_chunks, category=category
        )
        logger.info(f"✅ 文档 【{title}】 (v{new_version}) 向量化入库大功告成。")

    except Exception as e:
        logger.error(f"向量化环节失败，启动 MySQL 原子回滚 [ID: {doc_id}]: {e}")
        db.delete(db_doc)
        db.commit()
        raise HTTPException(
            status_code=500, detail=f"向量化服务异常，已撤销数据库登记: {str(e)}"
        )

    return {"id": doc_id, "title": title, "category": category, "version": new_version}


@router.delete("/docs/{doc_id}")
async def delete_knowledge_doc(doc_id: int, db: Session = Depends(get_db)):
    """物理删除：同步清理 MySQL 记录和 ChromaDB 中的所有向量碎片"""
    db_doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not db_doc:
        raise HTTPException(status_code=404, detail="未找到要删除的文档")

    doc_title = db_doc.title
    try:
        # 🚨 物理连带擦除：先清理向量库
        await vector_db.delete_document(doc_title)

        # 再清理 MySQL
        db.delete(db_doc)
        db.commit()
        logger.info(f"🗑️ 文档 【{doc_title}】 及其所有向量碎片已从系统中彻底移除。")
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.error(f"删除失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除操作失败: {str(e)}")


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """获取当前知识库中已存在的所有业务分类"""
    categories = db.query(KnowledgeDoc.category).distinct().all()
    return [cat[0] for cat in categories if cat[0]]


@router.post("/retrieve")
async def retrieve_knowledge(
    question: str,
    top_k: int = Query(5, ge=1, le=10),
    threshold: float = Query(0.1, ge=0.0, le=1.0),
):
    """手动测试接口：根据问题检索最相关的知识切片"""
    results = await vector_db.search(question, top_k, threshold)
    return {
        "content": "\n\n".join([r["document"] for r in results]),
        "has_related": len(results) > 0,
        "sources": [
            {"title": r["metadata"]["title"], "similarity": r["similarity"]}
            for r in results
        ],
    }
