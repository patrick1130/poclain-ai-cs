import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import CustomerSession, Message, SessionStatus, MessageSender
from app.utils.message_handler import MessageHandler

@pytest.fixture
def mock_db():
    """创建模拟数据库会话"""
    db = Mock(spec=Session)
    return db

@pytest.fixture
def message_handler():
    """创建消息处理器实例"""
    handler = MessageHandler()
    handler.vector_db = Mock()
    handler.document_processor = Mock()
    return handler

@pytest.mark.asyncio
async def test_handle_wechat_message_new_session(message_handler, mock_db):
    """测试处理新的微信消息并创建会话"""
    # 模拟用户信息
    user_id = "wx_user_001"
    user_name = "测试用户"
    user_avatar = "http://example.com/avatar.jpg"
    message_content = "你好，请问产品价格是多少？"
    
    # 模拟向量数据库搜索返回相关文档
    message_handler.vector_db.search.return_value = [
        {"content": "我们的产品价格是100元每个，批量购买有优惠。"}
    ]
    
    # 模拟AI模型返回回答
    with patch.object(message_handler, '_call_ai_model', return_value="我们的产品价格是100元每个，批量购买有优惠。"):
        # 处理消息
        response, need_human = await message_handler.handle_wechat_message(
            user_id=user_id,
            user_name=user_name,
            user_avatar=user_avatar,
            message_content=message_content,
            db=mock_db
        )
    
    # 验证结果
    assert need_human is False
    assert "100元" in response
    assert message_handler.vector_db.search.called
    mock_db.add.assert_called()  # 应该调用了add方法保存会话和消息

@pytest.mark.asyncio
async def test_handle_wechat_message_need_human(message_handler, mock_db):
    """测试AI无法回答时需要人工处理"""
    user_id = "wx_user_001"
    user_name = "测试用户"
    user_avatar = "http://example.com/avatar.jpg"
    message_content = "这个问题很复杂，AI无法回答"
    
    # 模拟向量数据库搜索返回空结果
    message_handler.vector_db.search.return_value = []
    
    # 处理消息
    response, need_human = await message_handler.handle_wechat_message(
        user_id=user_id,
        user_name=user_name,
        user_avatar=user_avatar,
        message_content=message_content,
        db=mock_db
    )
    
    # 验证结果
    assert need_human is True
    assert "客服人员" in response

@pytest.mark.asyncio
async def test_handle_wechat_message_existing_session(message_handler, mock_db):
    """测试处理已有会话的消息"""
    user_id = "wx_user_001"
    user_name = "测试用户"
    user_avatar = "http://example.com/avatar.jpg"
    message_content = "能详细介绍一下产品功能吗？"
    
    # 创建模拟会话
    existing_session = Mock(spec=CustomerSession)
    existing_session.id = 1
    existing_session.status = SessionStatus.AI_HANDLING
    
    # 模拟数据库查询返回已有会话
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_session
    
    # 模拟向量数据库搜索返回相关文档
    message_handler.vector_db.search.return_value = [
        {"content": "产品具有智能识别、自动处理、数据分析等功能。"}
    ]
    
    # 模拟AI模型返回回答
    with patch.object(message_handler, '_call_ai_model', return_value="产品具有智能识别、自动处理、数据分析等功能。"):
        # 处理消息
        response, need_human = await message_handler.handle_wechat_message(
            user_id=user_id,
            user_name=user_name,
            user_avatar=user_avatar,
            message_content=message_content,
            db=mock_db
        )
    
    # 验证结果
    assert need_human is False
    assert "智能识别" in response

def test_build_prompt(message_handler):
    """测试构建提示词"""
    query = "产品价格是多少？"
    conversation_history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "您好，有什么可以帮助您的？"}
    ]
    relevant_docs = [
        {"content": "产品价格：基础版100元，高级版200元"}
    ]
    
    prompt = message_handler._build_prompt(query, conversation_history, relevant_docs)
    
    # 验证提示词包含所有必要信息
    assert "产品价格" in prompt
    assert "你好" in prompt
    assert "基础版100元" in prompt
    assert "严格遵循以下规则" in prompt

def test_save_message(message_handler, mock_db):
    """测试保存消息功能"""
    session_id = 1
    sender = MessageSender.USER
    content = "测试消息内容"
    user_name = "测试用户"
    user_avatar = "http://example.com/avatar.jpg"
    
    message = message_handler._save_message(
        db=mock_db,
        session_id=session_id,
        sender=sender,
        content=content,
        user_name=user_name,
        user_avatar=user_avatar
    )
    
    # 验证消息创建
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()
    assert message.session_id == session_id
    assert message.sender == sender
    assert message.content == content
    assert message.user_name == user_name
    assert message.user_avatar == user_avatar

def test_get_or_create_session_new(message_handler, mock_db):
    """测试获取或创建新会话"""
    user_id = "wx_user_001"
    user_name = "测试用户"
    user_avatar = "http://example.com/avatar.jpg"
    
    # 模拟数据库查询返回None（没有现有会话）
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    
    session = message_handler._get_or_create_session(
        db=mock_db,
        user_id=user_id,
        user_name=user_name,
        user_avatar=user_avatar
    )
    
    # 验证创建了新会话
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    assert session.user_id == user_id
    assert session.user_name == user_name
    assert session.user_avatar == user_avatar

def test_get_or_create_session_existing(message_handler, mock_db):
    """测试获取已有会话"""
    user_id = "wx_user_001"
    user_name = "测试用户"
    user_avatar = "http://example.com/avatar.jpg"
    
    # 创建模拟现有会话
    existing_session = Mock(spec=CustomerSession)
    existing_session.user_id = user_id
    existing_session.user_name = "旧用户名"
    existing_session.user_avatar = None
    
    # 模拟数据库查询返回现有会话
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing_session
    
    session = message_handler._get_or_create_session(
        db=mock_db,
        user_id=user_id,
        user_name=user_name,
        user_avatar=user_avatar
    )
    
    # 验证返回的是现有会话，并更新了用户信息
    assert session == existing_session
    assert session.user_name == user_name
    assert session.user_avatar == user_avatar
    mock_db.commit.assert_called_once()