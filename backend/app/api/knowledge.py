# File: backend/app/api/knowledge.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging

from ..core.database import get_db
from ..models.database import KnowledgeDoc
from ..core.config import settings
from ..utils.vector_db import VectorDB
from ..utils.document_processor import split_document

logger = logging.getLogger(__name__)
router = APIRouter()

# 初始化向量数据库
vector_db = VectorDB(settings.VECTOR_DB_PATH)

# 初始化进程池，用于剥离 CPU 密集型切片任务
process_pool = ProcessPoolExecutor(max_workers=2)


def cpu_bound_split_document(title: str, content: str, category: str):
    """包装原始切片逻辑以便丢入进程池执行"""
    return split_document(title, content, category)


# Pydantic模型
class KnowledgeDocCreate(BaseModel):
    title: str
    content: str
    category: str


class KnowledgeDocUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


class KnowledgeDocResponse(BaseModel):
    id: int
    title: str
    category: str
    version: int
    create_time: datetime
    update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class KnowledgeDocDetailResponse(KnowledgeDocResponse):
    content: str


# ==========================================
# 辅助函数：将同步的 SQLAlchemy I/O 隔离进线程
# ==========================================
def _create_doc_db(db: Session, doc: KnowledgeDocCreate) -> KnowledgeDoc:
    existing_doc = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.title == doc.title, KnowledgeDoc.category == doc.category)
        .first()
    )

    if existing_doc:
        new_version = existing_doc.version + 1
        db_doc = KnowledgeDoc(
            title=doc.title,
            content=doc.content,
            category=doc.category,
            version=new_version,
        )
    else:
        db_doc = KnowledgeDoc(
            title=doc.title, content=doc.content, category=doc.category
        )

    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc


def _delete_doc_db(db: Session, db_doc: KnowledgeDoc) -> None:
    db.delete(db_doc)
    db.commit()


def _update_doc_db(db: Session, doc_id: int, update_data: dict):
    db_doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not db_doc:
        return None, None

    # 备份用于 Saga 补偿
    old_data = {
        "content": db_doc.content,
        "title": db_doc.title,
        "category": db_doc.category,
        "version": db_doc.version,
    }

    if "content" in update_data:
        db_doc.version += 1

    for key, value in update_data.items():
        setattr(db_doc, key, value)

    db.commit()
    db.refresh(db_doc)
    return db_doc, old_data


def _rollback_update_db(db: Session, db_doc: KnowledgeDoc, old_data: dict) -> None:
    db_doc.content = old_data["content"]
    db_doc.title = old_data["title"]
    db_doc.category = old_data["category"]
    db_doc.version = old_data["version"]
    db.commit()


def _get_doc_for_delete(db: Session, doc_id: int):
    return db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()


def _save_upload_db(db: Session, title: str, content: str, category: str):
    db_doc = KnowledgeDoc(title=title, content=content, category=category)
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc


# ==========================================
# 知识库文档核心接口
# ==========================================


@router.post("/docs", response_model=KnowledgeDocResponse)
async def create_knowledge_doc(doc: KnowledgeDocCreate, db: Session = Depends(get_db)):
    """
    创建新的知识库文档（引入原子性事务补偿机制）
    """
    # 【架构修复】利用 to_thread 避免同步 DB 插入锁死主线程
    db_doc = await asyncio.to_thread(_create_doc_db, db, doc)

    # 立即提取 DTO 数据，切断与 SQLAlchemy Session 的绑定
    doc_id = db_doc.id
    doc_title = db_doc.title
    doc_content = db_doc.content
    doc_category = db_doc.category

    response_data = {
        "id": doc_id,
        "title": doc_title,
        "category": doc_category,
        "version": db_doc.version,
        "create_time": db_doc.create_time,
        "update_time": db_doc.update_time,
    }

    try:
        # 将繁重的字符串切分任务抛给进程池执行
        loop = asyncio.get_running_loop()
        chunks = await loop.run_in_executor(
            process_pool, cpu_bound_split_document, doc_title, doc_content, doc_category
        )
        await vector_db.add_document(doc_id, doc_title, chunks, doc_category)
    except Exception as e:
        logger.error(f"向量库写入失败，准备回滚数据库记录 [DocID: {doc_id}]: {e}")
        await asyncio.to_thread(_delete_doc_db, db, db_doc)
        raise HTTPException(status_code=500, detail="文档解析或向量化失败，已回滚。")

    return response_data


@router.put("/docs/{doc_id}", response_model=KnowledgeDocResponse)
async def update_knowledge_doc(
    doc_id: int, doc: KnowledgeDocUpdate, db: Session = Depends(get_db)
):
    """
    更新知识库文档（引入补偿回滚机制）
    """
    update_data = doc.dict(exclude_unset=True)

    # 【架构修复】异步线程执行更新
    db_doc, old_data = await asyncio.to_thread(_update_doc_db, db, doc_id, update_data)

    if not db_doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    response_data = {
        "id": db_doc.id,
        "title": db_doc.title,
        "category": db_doc.category,
        "version": db_doc.version,
        "create_time": db_doc.create_time,
        "update_time": db_doc.update_time,
    }

    if "content" in update_data or "title" in update_data or "category" in update_data:
        try:
            loop = asyncio.get_running_loop()
            chunks = await loop.run_in_executor(
                process_pool,
                cpu_bound_split_document,
                db_doc.title,
                db_doc.content,
                db_doc.category,
            )
            await vector_db.update_document(
                doc_id, db_doc.title, chunks, db_doc.category
            )
        except Exception as e:
            logger.error(f"向量库更新失败，准备回滚 [DocID: {doc_id}]: {e}")
            await asyncio.to_thread(_rollback_update_db, db, db_doc, old_data)
            raise HTTPException(status_code=500, detail="向量化更新失败，已回滚。")

    return response_data


@router.delete("/docs/{doc_id}")
async def delete_knowledge_doc(doc_id: int, db: Session = Depends(get_db)):
    """
    删除知识库文档
    """
    db_doc = await asyncio.to_thread(_get_doc_for_delete, db, doc_id)

    if not db_doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 优先从向量数据库中删除
    try:
        await vector_db.delete_document(doc_id)
    except Exception as e:
        logger.error(f"从向量库删除文档失败 [DocID: {doc_id}]: {e}")
        raise HTTPException(status_code=500, detail="向量库清理失败，终止删除。")

    await asyncio.to_thread(_delete_doc_db, db, db_doc)

    return {"success": True}


# 【架构重塑核心】将纯数据库查询从 async def 降维为普通 def。
# 这样 FastAPI 自动分配底层线程池执行同步 SQL 查询，彻底消除并发拥堵和 15 秒超时风暴！
@router.get("/docs", response_model=List[KnowledgeDocResponse])
def get_knowledge_docs(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    获取知识库文档列表
    """
    query = db.query(KnowledgeDoc)

    if category:
        query = query.filter(KnowledgeDoc.category == category)

    if keyword:
        query = query.filter(
            KnowledgeDoc.title.contains(keyword)
            | KnowledgeDoc.content.contains(keyword)
        )

    # 聚合最新版本
    subquery = (
        db.query(
            KnowledgeDoc.title,
            KnowledgeDoc.category,
            func.max(KnowledgeDoc.version).label("max_version"),
        )
        .group_by(KnowledgeDoc.title, KnowledgeDoc.category)
        .subquery()
    )

    query = query.join(
        subquery,
        (KnowledgeDoc.title == subquery.c.title)
        & (KnowledgeDoc.category == subquery.c.category)
        & (KnowledgeDoc.version == subquery.c.max_version),
    )

    offset = (page - 1) * page_size
    docs = query.offset(offset).limit(page_size).all()

    # 转换为字典列表
    result = []
    for doc in docs:
        result.append(
            {
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "version": doc.version,
                "create_time": doc.create_time,
                "update_time": doc.update_time,
            }
        )

    return result


@router.get("/docs/{doc_id}", response_model=KnowledgeDocDetailResponse)
def get_knowledge_doc(doc_id: int, db: Session = Depends(get_db)):
    """
    获取知识库文档详情 (包含正文内容)
    """
    db_doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()

    if not db_doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "id": db_doc.id,
        "title": db_doc.title,
        "category": db_doc.category,
        "version": db_doc.version,
        "create_time": db_doc.create_time,
        "update_time": db_doc.update_time,
        "content": db_doc.content,
    }


# ==========================================
# 文件上传与检索接口
# ==========================================


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    上传文档文件（支持txt、md格式）
    """
    if not file.filename.endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="仅支持txt和md格式的文件")

    # 分块读取，限制硬性体积（最大 10MB）
    content_bytes = bytearray()
    file_size = 0
    MAX_FILE_SIZE = 10 * 1024 * 1024

    while chunk := await file.read(1024 * 1024):
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，最大允许 10MB")
        content_bytes.extend(chunk)

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content = content_bytes.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400, detail="无法解析文件编码，请使用UTF-8或GBK编码"
            )

    title = file.filename.rsplit(".", 1)[0]

    # 【架构修复】隔离同步 DB 写入
    db_doc = await asyncio.to_thread(_save_upload_db, db, title, content, category)
    doc_id = db_doc.id

    try:
        loop = asyncio.get_running_loop()
        chunks = await loop.run_in_executor(
            process_pool, cpu_bound_split_document, title, content, category
        )
        await vector_db.add_document(doc_id, title, chunks, category)
    except Exception as e:
        logger.error(f"文件上传后向量化失败，回滚数据库 [DocID: {doc_id}]: {e}")
        await asyncio.to_thread(_delete_doc_db, db, db_doc)
        raise HTTPException(status_code=500, detail="解析或向量化失败，已回滚。")

    return {"id": doc_id, "title": title, "category": category}


# 【引发报错的元凶点修复】取消 async，让 FastAPI 以防拥堵多线程模式执行 GROUP BY 查询
@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """
    获取所有文档分类
    """
    categories = db.query(KnowledgeDoc.category).distinct().all()
    # 严格过滤空分类防范下游 NullPointBug
    return [cat[0] for cat in categories if cat[0]]


@router.post("/retrieve")
async def retrieve_knowledge(
    question: str,
    top_k: int = Query(settings.RETRIEVAL_TOP_K, ge=1, le=10),
    threshold: float = Query(settings.RETRIEVAL_THRESHOLD, ge=0.0, le=1.0),
):
    """
    根据问题检索相关知识库内容
    """
    results = await vector_db.search(question, top_k, threshold)

    return {
        "content": "\n\n".join([r["document"] for r in results]),
        "has_related": len(results) > 0,
        "sources": [
            {
                "title": r["metadata"]["title"],
                "category": r["metadata"]["category"],
                "similarity": 1 - r["distance"],
            }
            for r in results
        ],
    }
