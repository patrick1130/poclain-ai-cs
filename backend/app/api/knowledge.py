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
import re  # 【架构引入】用于物理级正则替换

from ..core.database import get_db
from ..models.database import KnowledgeDoc
from ..core.config import settings
from ..utils.vector_db import VectorDB
from ..utils.document_processor import split_document

logger = logging.getLogger(__name__)
router = APIRouter()

vector_db = VectorDB(settings.VECTOR_DB_PATH)
process_pool = ProcessPoolExecutor(max_workers=2)


def cpu_bound_split_document(title: str, content: str, category: str):
    return split_document(title, content, category)


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


async def _enrich_single_chunk(
    client: httpx.AsyncClient, chunk: str, sem: asyncio.Semaphore
) -> str:
    async with sem:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        }
        system_prompt = (
            "你是一个企业级数据清洗专家。\n"
            "请将以下文档碎片重写为连贯、语义丰富且独立完整的自然语言描述。\n"
            "规则：\n"
            "1. 补全参数的上下文（例如'最大排量: 1000' -> '该型号的最大排量为 1000 cc'）。\n"
            "2. 严禁输出任何多余的解释、问候语或Markdown格式，直接输出清洗后的纯文本。"
        )
        payload = {
            "model": settings.PRIMARY_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"原始碎片：\n{chunk}"},
            ],
            "temperature": 0.1,
        }
        try:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"大模型清洗碎片失败，回退使用原始碎片: {e}")
            return chunk


async def async_enrich_chunks(chunks: List[str]) -> List[str]:
    sem = asyncio.Semaphore(5)
    async with httpx.AsyncClient(timeout=40.0, verify=False, trust_env=False) as client:
        tasks = [_enrich_single_chunk(client, chunk, sem) for chunk in chunks]
        enriched_chunks = await asyncio.gather(*tasks)
    return enriched_chunks


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        import fitz
    except ImportError:
        logger.error("缺少关键依赖: 请执行 pip install pymupdf")
        raise ValueError("系统缺失 PDF 解析引擎，请联系管理员")

    text_content = []
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text_content.append(page.get_text())
        return "\n".join(text_content)
    except Exception as e:
        logger.error(f"PDF 文件损坏或解析失败: {e}")
        raise ValueError(f"无法读取该 PDF 文件结构: {str(e)}")


def _extract_text_from_excel(excel_bytes: bytes) -> str:
    try:
        import pandas as pd
    except ImportError:
        logger.error("缺少关键依赖: 请执行 pip install pandas openpyxl")
        raise ValueError("系统缺失 Excel 解析引擎，请联系管理员执行依赖安装")

    try:
        df_dict = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=None)
        text_content = []

        for sheet_name, df in df_dict.items():
            text_content.append(f"【表格区域: {sheet_name}】")
            df.dropna(how="all", inplace=True)
            df.dropna(axis=1, how="all", inplace=True)

            columns = df.columns.tolist()
            for index, row in df.iterrows():
                row_strs = []
                for col in columns:
                    val = row[col]
                    if pd.notna(val):
                        str_val = str(val).strip()
                        # 【S级架构加固】物理级正则清洗：暴力拆解连体型号
                        # 如果单元格内容包含连字符或斜杠，且看起来像型号代码，强行将其转换为独立词根
                        if re.search(r"[A-Za-z0-9]+[-/][A-Za-z0-9]+", str_val):
                            str_val = re.sub(r"[-/]", " 和 ", str_val)
                            str_val += " (这两种型号通用上述参数)"

                        row_strs.append(f"{col}: {str_val}")

                if row_strs:
                    text_content.append(" | ".join(row_strs))

            text_content.append("")

        return "\n".join(text_content)
    except Exception as e:
        logger.error(f"Excel 文件结构异常或解析失败: {e}")
        raise ValueError(f"无法读取该 Excel 矩阵结构: {str(e)}")


@router.post("/docs", response_model=KnowledgeDocResponse)
async def create_knowledge_doc(doc: KnowledgeDocCreate, db: Session = Depends(get_db)):
    db_doc = await asyncio.to_thread(_create_doc_db, db, doc)

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
        loop = asyncio.get_running_loop()
        chunks = await loop.run_in_executor(
            process_pool, cpu_bound_split_document, doc_title, doc_content, doc_category
        )
        logger.info(
            f"开始使用大模型对 {len(chunks)} 个碎片进行深度语义清洗 (LLM-Assisted ETL)..."
        )
        enriched_chunks = await async_enrich_chunks(chunks)

        await vector_db.add_document(doc_id, doc_title, enriched_chunks, doc_category)
    except Exception as e:
        logger.error(f"向量库写入失败，准备回滚数据库记录 [DocID: {doc_id}]: {e}")
        await asyncio.to_thread(_delete_doc_db, db, db_doc)
        raise HTTPException(status_code=500, detail="文档解析或向量化失败，已回滚。")

    return response_data


@router.put("/docs/{doc_id}", response_model=KnowledgeDocResponse)
async def update_knowledge_doc(
    doc_id: int, doc: KnowledgeDocUpdate, db: Session = Depends(get_db)
):
    update_data = doc.dict(exclude_unset=True)
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
            logger.info(
                f"开始使用大模型对 {len(chunks)} 个碎片进行深度语义清洗 (LLM-Assisted ETL)..."
            )
            enriched_chunks = await async_enrich_chunks(chunks)

            await vector_db.update_document(
                doc_id, db_doc.title, enriched_chunks, db_doc.category
            )
        except Exception as e:
            logger.error(f"向量库更新失败，准备回滚 [DocID: {doc_id}]: {e}")
            await asyncio.to_thread(_rollback_update_db, db, db_doc, old_data)
            raise HTTPException(status_code=500, detail="向量化更新失败，已回滚。")

    return response_data


@router.delete("/docs/{doc_id}")
async def delete_knowledge_doc(doc_id: int, db: Session = Depends(get_db)):
    db_doc = await asyncio.to_thread(_get_doc_for_delete, db, doc_id)

    if not db_doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        await vector_db.delete_document(doc_id)
    except Exception as e:
        logger.error(f"从向量库删除文档失败 [DocID: {doc_id}]: {e}")
        raise HTTPException(status_code=500, detail="向量库清理失败，终止删除。")

    await asyncio.to_thread(_delete_doc_db, db, db_doc)
    return {"success": True}


@router.get("/docs", response_model=List[KnowledgeDocResponse])
def get_knowledge_docs(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(KnowledgeDoc)
    if category:
        query = query.filter(KnowledgeDoc.category == category)
    if keyword:
        query = query.filter(
            KnowledgeDoc.title.contains(keyword)
            | KnowledgeDoc.content.contains(keyword)
        )

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


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
):
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if file_ext not in ["txt", "md", "pdf", "xlsx", "xls"]:
        raise HTTPException(
            status_code=400, detail="仅支持 txt, md, pdf, xlsx, xls 格式的文件"
        )

    content_bytes = bytearray()
    file_size = 0
    MAX_FILE_SIZE = 15 * 1024 * 1024

    while chunk := await file.read(1024 * 1024):
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，最大允许 15MB")
        content_bytes.extend(chunk)

    content = ""
    try:
        loop = asyncio.get_running_loop()
        if file_ext == "pdf":
            content = await loop.run_in_executor(
                process_pool, _extract_text_from_pdf, bytes(content_bytes)
            )
        elif file_ext in ["xlsx", "xls"]:
            content = await loop.run_in_executor(
                process_pool, _extract_text_from_excel, bytes(content_bytes)
            )
        else:
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = content_bytes.decode("gbk")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"文件解码异常: {e}")
        raise HTTPException(
            status_code=400, detail="无法解析该文件，请确认格式无误或未加密"
        )

    if not content.strip():
        raise HTTPException(
            status_code=400, detail="提取失败：文档中没有可读文本或有效表格内容。"
        )

    title = file.filename.rsplit(".", 1)[0]
    db_doc = await asyncio.to_thread(_save_upload_db, db, title, content, category)
    doc_id = db_doc.id

    try:
        loop = asyncio.get_running_loop()
        chunks = await loop.run_in_executor(
            process_pool, cpu_bound_split_document, title, content, category
        )
        logger.info(
            f"开始使用大模型对 {len(chunks)} 个碎片进行深度语义清洗 (LLM-Assisted ETL)..."
        )
        enriched_chunks = await async_enrich_chunks(chunks)

        await vector_db.add_document(doc_id, title, enriched_chunks, category)
    except Exception as e:
        logger.error(f"文件上传后向量化失败，回滚数据库 [DocID: {doc_id}]: {e}")
        await asyncio.to_thread(_delete_doc_db, db, db_doc)
        raise HTTPException(
            status_code=500, detail="文本切片或向量化失败，已触发回滚。"
        )

    return {"id": doc_id, "title": title, "category": category}


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(KnowledgeDoc.category).distinct().all()
    return [cat[0] for cat in categories if cat[0]]


@router.post("/retrieve")
async def retrieve_knowledge(
    question: str,
    top_k: int = Query(settings.RETRIEVAL_TOP_K, ge=1, le=10),
    threshold: float = Query(settings.RETRIEVAL_THRESHOLD, ge=0.0, le=1.0),
):
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
