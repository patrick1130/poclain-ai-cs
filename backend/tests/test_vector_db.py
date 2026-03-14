import pytest
from unittest.mock import Mock, patch
import numpy as np

from app.utils.vector_db import VectorDB

@pytest.fixture
def vector_db():
    """创建向量数据库实例"""
    db = VectorDB()
    db.chroma_client = Mock()
    db.collection = Mock()
    return db

def test_init(vector_db):
    """测试向量数据库初始化"""
    # 验证初始化过程
    assert vector_db.chroma_client is not None
    assert vector_db.collection is not None

def test_add_documents(vector_db):
    """测试添加文档到向量数据库"""
    # 模拟文档数据
    documents = [
        {"content": "产品价格是100元", "metadata": {"document_id": 1, "page": 1}},
        {"content": "产品具有智能识别功能", "metadata": {"document_id": 1, "page": 2}}
    ]
    
    # 模拟嵌入模型
    with patch.object(vector_db, '_get_embedding', side_effect=[
        np.array([0.1, 0.2, 0.3]),
        np.array([0.4, 0.5, 0.6])
    ]):
        # 添加文档
        result = vector_db.add_documents(documents)
    
    # 验证结果
    assert result is True
    vector_db.collection.add.assert_called_once()
    
    # 验证调用参数
    call_args = vector_db.collection.add.call_args
    assert len(call_args[1]['documents']) == 2
    assert len(call_args[1]['embeddings']) == 2
    assert len(call_args[1]['ids']) == 2

def test_add_documents_empty(vector_db):
    """测试添加空文档列表"""
    result = vector_db.add_documents([])
    assert result is True
    vector_db.collection.add.assert_not_called()

def test_search(vector_db):
    """测试搜索相关文档"""
    # 模拟查询
    query = "产品价格"
    
    # 模拟嵌入模型返回向量
    query_embedding = np.array([0.1, 0.2, 0.3])
    with patch.object(vector_db, '_get_embedding', return_value=query_embedding):
        # 模拟搜索结果
        vector_db.collection.query.return_value = {
            'documents': [["产品价格是100元", "产品价格是200元"]],
            'metadatas': [[{"document_id": 1, "page": 1}, {"document_id": 2, "page": 3}]],
            'distances': [[0.1, 0.2]]
        }
        
        # 执行搜索
        results = vector_db.search(query, top_k=2)
    
    # 验证结果
    assert len(results) == 2
    assert results[0]['content'] == "产品价格是100元"
    assert results[0]['metadata'] == {"document_id": 1, "page": 1}
    assert results[1]['content'] == "产品价格是200元"
    
    # 验证调用
    vector_db.collection.query.assert_called_once_with(
        query_embeddings=[query_embedding.tolist()],
        n_results=2,
        include=['documents', 'metadatas', 'distances']
    )

def test_search_no_results(vector_db):
    """测试搜索无结果的情况"""
    query = "不存在的内容"
    
    with patch.object(vector_db, '_get_embedding', return_value=np.array([0.1, 0.2, 0.3])):
        vector_db.collection.query.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }
        
        results = vector_db.search(query, top_k=2)
    
    assert len(results) == 0

def test_delete_document(vector_db):
    """测试删除文档"""
    # 模拟文档ID
    document_id = 1
    
    # 模拟删除操作
    vector_db.collection.delete.return_value = True
    
    # 删除文档
    result = vector_db.delete_document(document_id)
    
    # 验证结果
    assert result is True
    vector_db.collection.delete.assert_called_once_with(
        where={"document_id": document_id}
    )

def test_get_embedding():
    """测试获取文本嵌入向量"""
    # 创建新的向量数据库实例用于测试私有方法
    db = VectorDB()
    
    # 测试简单文本
    text = "测试文本"
    embedding = db._get_embedding(text)
    
    # 验证结果
    assert isinstance(embedding, np.ndarray)
    assert len(embedding) > 0  # 确保返回了非空向量

def test_get_embedding_empty():
    """测试获取空文本的嵌入向量"""
    db = VectorDB()
    embedding = db._get_embedding("")
    
    assert isinstance(embedding, np.ndarray)
    assert len(embedding) > 0