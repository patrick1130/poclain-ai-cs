import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.models.database import KnowledgeDocument, DocumentStatus
from app.utils.knowledge_manager import KnowledgeManager

@pytest.fixture
def mock_db():
    """创建模拟数据库会话"""
    db = Mock(spec=Session)
    return db

@pytest.fixture
def knowledge_manager():
    """创建知识库管理器实例"""
    manager = KnowledgeManager()
    manager.vector_db = Mock()
    manager.document_processor = Mock()
    return manager

def test_add_document(knowledge_manager, mock_db):
    """测试添加文档到知识库"""
    # 模拟文档数据
    file_name = "产品手册.pdf"
    file_content = "产品介绍内容"
    file_size = 1024
    file_type = "application/pdf"
    
    # 模拟文档处理器返回处理后的内容
    processed_chunks = [
        {"content": "产品名称：智能助手", "metadata": {"page": 1}},
        {"content": "产品价格：100元", "metadata": {"page": 2}}
    ]
    knowledge_manager.document_processor.process_document.return_value = processed_chunks
    
    # 模拟向量数据库添加文档
    knowledge_manager.vector_db.add_documents.return_value = True
    
    # 添加文档
    document_id = knowledge_manager.add_document(
        file_name=file_name,
        file_content=file_content,
        file_size=file_size,
        file_type=file_type,
        db=mock_db
    )
    
    # 验证结果
    assert document_id is not None
    knowledge_manager.document_processor.process_document.assert_called_once_with(
        file_content=file_content,
        file_type=file_type
    )
    knowledge_manager.vector_db.add_documents.assert_called_once_with(processed_chunks)
    
    # 验证数据库操作
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

def test_add_document_processing_error(knowledge_manager, mock_db):
    """测试文档处理失败的情况"""
    # 模拟文档处理器抛出异常
    knowledge_manager.document_processor.process_document.side_effect = Exception("处理失败")
    
    # 添加文档
    document_id = knowledge_manager.add_document(
        file_name="错误文档.pdf",
        file_content="内容",
        file_size=1024,
        file_type="application/pdf",
        db=mock_db
    )
    
    # 验证结果
    assert document_id is None
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

def test_get_document(knowledge_manager, mock_db):
    """测试获取文档信息"""
    # 模拟文档ID
    document_id = 1
    
    # 模拟数据库查询返回文档
    mock_document = Mock(spec=KnowledgeDocument)
    mock_document.id = document_id
    mock_document.file_name = "产品手册.pdf"
    mock_document.status = DocumentStatus.PROCESSED
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_document
    
    # 获取文档
    document = knowledge_manager.get_document(document_id, db=mock_db)
    
    # 验证结果
    assert document == mock_document
    mock_db.query.assert_called_once()

def test_get_all_documents(knowledge_manager, mock_db):
    """测试获取所有文档"""
    # 模拟文档列表
    mock_documents = [
        Mock(spec=KnowledgeDocument, id=1, file_name="文档1.pdf"),
        Mock(spec=KnowledgeDocument, id=2, file_name="文档2.pdf")
    ]
    
    mock_db.query.return_value.all.return_value = mock_documents
    
    # 获取所有文档
    documents = knowledge_manager.get_all_documents(db=mock_db)
    
    # 验证结果
    assert len(documents) == 2
    assert documents == mock_documents
    mock_db.query.assert_called_once()

def test_delete_document(knowledge_manager, mock_db):
    """测试删除文档"""
    # 模拟文档ID
    document_id = 1
    
    # 模拟数据库查询返回文档
    mock_document = Mock(spec=KnowledgeDocument)
    mock_document.id = document_id
    mock_document.status = DocumentStatus.PROCESSED
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_document
    
    # 模拟向量数据库删除文档
    knowledge_manager.vector_db.delete_document.return_value = True
    
    # 删除文档
    success = knowledge_manager.delete_document(document_id, db=mock_db)
    
    # 验证结果
    assert success is True
    knowledge_manager.vector_db.delete_document.assert_called_once_with(document_id)
    mock_db.delete.assert_called_once_with(mock_document)
    mock_db.commit.assert_called_once()

def test_delete_document_not_found(knowledge_manager, mock_db):
    """测试删除不存在的文档"""
    # 模拟数据库查询返回None
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    # 删除文档
    success = knowledge_manager.delete_document(1, db=mock_db)
    
    # 验证结果
    assert success is False
    knowledge_manager.vector_db.delete_document.assert_not_called()
    mock_db.delete.assert_not_called()

def test_update_document_status(knowledge_manager, mock_db):
    """测试更新文档状态"""
    # 模拟文档ID和状态
    document_id = 1
    new_status = DocumentStatus.PROCESSING
    
    # 模拟数据库查询返回文档
    mock_document = Mock(spec=KnowledgeDocument)
    mock_document.id = document_id
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_document
    
    # 更新状态
    success = knowledge_manager.update_document_status(
        document_id=document_id,
        status=new_status,
        db=mock_db
    )
    
    # 验证结果
    assert success is True
    assert mock_document.status == new_status
    mock_db.commit.assert_called_once()

def test_search_documents(knowledge_manager, mock_db):
    """测试搜索文档"""
    # 模拟搜索查询
    query = "产品价格"
    
    # 模拟向量数据库搜索返回结果
    search_results = [
        {"content": "产品价格：100元", "metadata": {"document_id": 1, "page": 2}},
        {"content": "促销价格：80元", "metadata": {"document_id": 2, "page": 5}}
    ]
    knowledge_manager.vector_db.search.return_value = search_results
    
    # 搜索文档
    results = knowledge_manager.search_documents(query, top_k=2, db=mock_db)
    
    # 验证结果
    assert len(results) == 2
    assert results == search_results
    knowledge_manager.vector_db.search.assert_called_once_with(query, top_k=2)