# File: backend/app/utils/vector_db.py

import logging
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
import asyncio
from functools import partial

logger = logging.getLogger(__name__)


class VectorDB:
    """向量数据库操作类 (Chroma 0.4.x 适配版)"""

    def __init__(self, persist_directory: str):
        try:
            # 适配 Chroma 0.4.x+ 的新版 API，废弃旧版字典配置
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False, allow_reset=True  # 关闭官方的遥测收集
                ),
            )
            # 获取或创建 Collection，使用 cosine 距离计算相似度
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base", metadata={"hnsw:space": "cosine"}
            )
            # 引入并发信号量，防止高并发下系统资源枯竭
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

        # 为每个 chunk 生成唯一的 ID
        ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]
        # 为每个 chunk 附加元数据
        metadatas = [
            {"doc_id": doc_id, "title": title, "category": category, "chunk_index": i}
            for i in range(len(chunks))
        ]

        async with self._semaphore:
            try:
                # 【核心修复】将同步阻塞的 ChromaDB 计算与 I/O 操作剥离到默认线程池
                # 彻底解救主事件循环 (Event Loop)，防止全站请求被单一的 Embedding 任务卡死
                loop = asyncio.get_running_loop()
                add_func = partial(
                    self.collection.add, documents=chunks, metadatas=metadatas, ids=ids
                )
                await loop.run_in_executor(None, add_func)

                logger.info(
                    f"Added {len(chunks)} chunks for document {doc_id} to VectorDB."
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
                # 【核心修复】剥离阻塞型 Delete 擦除操作
                loop = asyncio.get_running_loop()
                delete_func = partial(self.collection.delete, where={"doc_id": doc_id})
                await loop.run_in_executor(None, delete_func)

                logger.info(f"Deleted chunks for document {doc_id} from VectorDB.")
            except Exception as e:
                logger.error(
                    f"Error deleting document {doc_id} from VectorDB: {e}",
                    exc_info=True,
                )

    async def search(
        self, query: str, top_k: int = 3, threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """检索相关知识"""
        async with self._semaphore:
            try:
                # 【核心修复】剥离阻塞型 Query 检索与余弦距离运算
                loop = asyncio.get_running_loop()
                query_func = partial(
                    self.collection.query, query_texts=[query], n_results=top_k
                )
                results = await loop.run_in_executor(None, query_func)

                formatted_results = []
                # Chroma query 返回的结构是二维列表
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
