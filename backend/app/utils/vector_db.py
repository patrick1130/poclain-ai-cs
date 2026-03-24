import logging
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
import asyncio
from functools import partial
import re

logger = logging.getLogger(__name__)


class VectorDB:
    """向量数据库操作类 (Chroma 0.4.x 架构优化版)"""

    def __init__(self, persist_directory: str):
        try:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base", metadata={"hnsw:space": "cosine"}
            )
            # 引入信号量限制并发，保护 ChromaDB 底层 SQLite 的文件句柄
            self._semaphore = asyncio.Semaphore(10)
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

        # 使用整型 ID 生成唯一哈希索引，防止向量覆盖错乱
        ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]

        # 强制类型转换，规避 ChromaDB 元数据查询的类型严格匹配 Bug
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
                # 统一使用 upsert 确保操作的原子性与幂等性
                add_func = partial(
                    self.collection.upsert,
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids,
                )
                await loop.run_in_executor(None, add_func)
                logger.info(
                    f"Successfully upserted {len(chunks)} chunks for document ID {doc_id}."
                )
            except Exception as e:
                logger.error(
                    f"Error upserting document ID {doc_id}: {e}", exc_info=True
                )
                raise e

    async def update_document(
        self, doc_id: int, title: str, chunks: List[str], category: str
    ):
        """更新文档 (原子级先删后加)"""
        await self.delete_document(doc_id)
        await self.add_document(doc_id, title, chunks, category)

    async def delete_document(self, doc_id: int):
        """物理粉碎特定文档的所有切片"""
        async with self._semaphore:
            try:
                loop = asyncio.get_running_loop()

                # Step 1: O(N) 搜索关联的物理切片坐标
                get_func = partial(self.collection.get, where={"doc_id": str(doc_id)})
                existing_data = await loop.run_in_executor(None, get_func)
                ids_to_delete = existing_data.get("ids", [])

                # Step 2: O(1) 精准物理抹除
                if ids_to_delete:
                    delete_func = partial(self.collection.delete, ids=ids_to_delete)
                    await loop.run_in_executor(None, delete_func)
                    logger.info(
                        f"Purged {len(ids_to_delete)} vectors for document ID {doc_id}."
                    )
                else:
                    logger.warning(
                        f"No existing vectors found for document ID {doc_id}."
                    )

            except Exception as e:
                logger.error(f"Error deleting document ID {doc_id}: {e}", exc_info=True)

    async def search(
        self, query: str, top_k: int = 5, threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """架构重构版：双轨制自适应混合检索"""
        async with self._semaphore:
            try:
                loop = asyncio.get_running_loop()

                # 提取潜在型号特征 (如 MS18, MGE05)
                model_match = re.search(r"(?=[A-Za-z]*[0-9])[A-Za-z0-9\-_/]{3,}", query)
                target_model = model_match.group(0).upper() if model_match else None

                # 扩大底层物理召回基数，防断崖式 Miss
                n_results = 15
                query_func = partial(
                    self.collection.query, query_texts=[query], n_results=n_results
                )
                results = await loop.run_in_executor(None, query_func)

                if (
                    not results
                    or not results["documents"]
                    or not results["documents"][0]
                ):
                    return []

                docs = results["documents"][0]
                metas = results["metadatas"][0]
                distances = results["distances"][0]

                exact_matches = []
                semantic_matches = []

                # O(K) 内存层双轨计算算法
                for i in range(len(docs)):
                    similarity = 1 - distances[i]
                    doc_text_upper = docs[i].upper()

                    if target_model:
                        # 轨 1：严格型号锁定 (针对参数查询)
                        if target_model in doc_text_upper:
                            exact_matches.append(
                                {
                                    "document": docs[i],
                                    "metadata": metas[i],
                                    "similarity": similarity,
                                }
                            )
                        elif similarity >= threshold:
                            # 即使型号未严格匹配，若语义足够相似，存入备用池防击穿
                            semantic_matches.append(
                                {
                                    "document": docs[i],
                                    "metadata": metas[i],
                                    "similarity": similarity,
                                }
                            )
                    else:
                        # 轨 2：纯语义宽泛召回 (针对通用问答)
                        if similarity >= threshold:
                            semantic_matches.append(
                                {
                                    "document": docs[i],
                                    "metadata": metas[i],
                                    "similarity": similarity,
                                }
                            )

                # 优先级判定与结果截断
                if exact_matches:
                    # 优先返回精确命中型号的结果
                    exact_matches.sort(key=lambda x: x["similarity"], reverse=True)
                    return exact_matches[:top_k]
                else:
                    # 降级返回语义相似度结果
                    semantic_matches.sort(key=lambda x: x["similarity"], reverse=True)
                    return semantic_matches[:top_k]

            except Exception as e:
                logger.error(f"Error executing vector search: {e}", exc_info=True)
                return []
