import logging
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
import asyncio
from functools import partial
import re

logger = logging.getLogger(__name__)


class VectorDB:
    """向量数据库操作类 (Chroma 0.4.x 适配版)"""

    def __init__(self, persist_directory: str):
        try:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base", metadata={"hnsw:space": "cosine"}
            )
            self._semaphore = asyncio.Semaphore(5)
            logger.info("VectorDB (Chroma) initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize VectorDB: {e}", exc_info=True)
            raise e

    async def add_document(
        self, doc_id: int, title: str, chunks: List[str], category: str
    ):
        """异步添加文档到向量库"""
        if not chunks:
            return

        ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]
        # 【核心修复】强制将 doc_id 转换为 string，彻底解决 ChromaDB 幽灵碎片删除失效的 Bug
        metadatas = [
            {
                "doc_id": str(doc_id),
                "title": title,
                "category": category,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        async with self._semaphore:
            try:
                loop = asyncio.get_running_loop()
                # 【核心修复】改用 upsert 替代 add，根除 Add of existing embedding ID 警告
                add_func = partial(
                    self.collection.upsert,
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids,
                )
                await loop.run_in_executor(None, add_func)

                logger.info(
                    f"Added/Upserted {len(chunks)} chunks for document {doc_id} to VectorDB."
                )
            except Exception as e:
                logger.error(
                    f"Error adding document {doc_id} to VectorDB: {e}", exc_info=True
                )
                raise e

    async def update_document(
        self, doc_id: int, title: str, chunks: List[str], category: str
    ):
        """更新文档 (先删后加)"""
        await self.delete_document(doc_id)
        await self.add_document(doc_id, title, chunks, category)

    async def delete_document(self, doc_id: int):
        """删除特定文档的所有切片"""
        async with self._semaphore:
            try:
                loop = asyncio.get_running_loop()
                # 【核心修复】使用 str(doc_id) 匹配刚才写入的字符串类型，实现物理级连带擦除
                delete_func = partial(
                    self.collection.delete, where={"doc_id": str(doc_id)}
                )
                await loop.run_in_executor(None, delete_func)

                logger.info(f"Deleted chunks for document {doc_id} from VectorDB.")
            except Exception as e:
                logger.error(
                    f"Error deleting document {doc_id} from VectorDB: {e}",
                    exc_info=True,
                )

    async def search(
        self, query: str, top_k: int = 10, threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """检索相关知识 (引入物理字面量混合检索)"""
        async with self._semaphore:
            try:
                loop = asyncio.get_running_loop()

                # 【S级架构杀器：混合检索预过滤 (Hybrid Search Pre-filter)】
                # 嗅探用户问题中是否包含类似 "MS18", "MK04" 这样的工业型号特征词汇
                model_keywords = re.findall(
                    r"(?=[A-Za-z]*[0-9])[A-Za-z0-9\-_/]{3,}", query
                )
                where_doc = None
                target_model = None

                if model_keywords:
                    # 将嗅探到的型号转为大写，强制 ChromaDB 在底层必须先匹配该字符串
                    target_model = model_keywords[0].upper()
                    where_doc = {"$contains": target_model}
                    logger.info(
                        f"🔍 触发物理型号锁定: 强制召回必须包含字面量 '{target_model}' 的记忆碎片"
                    )

                # 构建带锁定的查询参数
                query_kwargs = {"query_texts": [query], "n_results": top_k}
                if where_doc:
                    query_kwargs["where_document"] = where_doc

                # 执行带锁定的物理检索
                query_func = partial(self.collection.query, **query_kwargs)
                results = await loop.run_in_executor(None, query_func)

                # 【防熔断降级】如果强制锁定型号后啥也没搜到（比如用户拼错了），降级为纯向量模糊检索
                if (
                    not results
                    or not results["documents"]
                    or not results["documents"][0]
                ):
                    if where_doc:
                        logger.warning(
                            f"⚠️ 物理锁定 '{target_model}' 未命中，降级为纯向量模糊检索..."
                        )
                        fallback_func = partial(
                            self.collection.query, query_texts=[query], n_results=top_k
                        )
                        results = await loop.run_in_executor(None, fallback_func)

                formatted_results = []
                if (
                    not results
                    or not results["documents"]
                    or not results["documents"][0]
                ):
                    return formatted_results

                docs = results["documents"][0]
                metas = results["metadatas"][0]
                distances = results["distances"][0]

                for i in range(len(docs)):
                    # Cosine space 下，distance 越小越相似 (1 - distance 即为相似度)
                    similarity = 1 - distances[i]
                    if similarity >= threshold:
                        formatted_results.append(
                            {
                                "document": docs[i],
                                "metadata": metas[i],
                                "distance": distances[i],
                                "similarity": similarity,
                            }
                        )

                return formatted_results
            except Exception as e:
                logger.error(f"Error searching VectorDB: {e}", exc_info=True)
                return []
