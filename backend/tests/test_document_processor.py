import pytest
from unittest.mock import Mock, patch
import io
from PyPDF2 import PdfReader
import docx2txt

from app.utils.document_processor import DocumentProcessor

@pytest.fixture
def document_processor():
    """创建文档处理器实例"""
    processor = DocumentProcessor()
    return processor

def test_process_pdf_document(document_processor):
    """测试处理PDF文档"""
    # 创建模拟PDF内容
    pdf_content = """
    %PDF-1.4
    1 0 obj
    << /Type /Catalog /Pages 2 0 R >>
    endobj
    2 0 obj
    << /Type /Pages /Kids [3 0 R] /Count 1 >>
    endobj
    3 0 obj
    << /Type /Page /Parent 2 0 R /Contents 4 0 R >>
    endobj
    4 0 obj
    << /Length 44 >>
    stream
    BT
    /F1 12 Tf
    100 700 Td
    (产品介绍) Tj
    100 680 Td
    (价格: 100元) Tj
    ET
    endstream
    endobj
    xref
    0 5
    0000000000 65535 f 
    0000000010 00000 n 
    0000000050 00000 n 
    0000000090 00000 n 
    0000000130 00000 n 
    trailer
    << /Size 5 /Root 1 0 R >>
    startxref
    200
    %%EOF
    """
    
    # 模拟PDF读取
    with patch('PyPDF2.PdfReader', autospec=True) as mock_pdf_reader:
        mock_reader = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "产品介绍\n价格: 100元"
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        # 处理文档
        chunks = document_processor.process_document(
            file_content=pdf_content.encode('utf-8'),
            file_type='application/pdf'
        )
    
    # 验证结果
    assert len(chunks) > 0
    assert any("产品介绍" in chunk['content'] for chunk in chunks)
    assert any("100元" in chunk['content'] for chunk in chunks)

def test_process_text_document(document_processor):
    """测试处理纯文本文档"""
    # 模拟文本内容
    text_content = """
    产品名称：智能助手
    产品价格：100元
    产品功能：
    1. 智能问答
    2. 数据分析
    3. 自动处理
    """
    
    # 处理文档
    chunks = document_processor.process_document(
        file_content=text_content.encode('utf-8'),
        file_type='text/plain'
    )
    
    # 验证结果
    assert len(chunks) > 0
    assert any("智能助手" in chunk['content'] for chunk in chunks)
    assert any("智能问答" in chunk['content'] for chunk in chunks)

def test_process_word_document(document_processor):
    """测试处理Word文档"""
    # 模拟Word文档内容
    word_content = "产品手册\n\n第一章：产品介绍\n智能助手是一款AI产品。\n\n第二章：价格信息\n市场价格：100元/个"
    
    # 模拟docx2txt处理
    with patch('docx2txt.process', return_value=word_content):
        chunks = document_processor.process_document(
            file_content=b'mock_word_content',
            file_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    
    # 验证结果
    assert len(chunks) > 0
    assert any("产品手册" in chunk['content'] for chunk in chunks)
    assert any("100元" in chunk['content'] for chunk in chunks)

def test_process_unsupported_format(document_processor):
    """测试处理不支持的文档格式"""
    # 处理不支持的格式
    chunks = document_processor.process_document(
        file_content=b'mock_content',
        file_type='unsupported/format'
    )
    
    # 验证结果
    assert len(chunks) == 0

def test_split_text_into_chunks(document_processor):
    """测试文本分块功能"""
    # 长文本内容
    long_text = "这是一个很长的文本内容。" * 50  # 创建一个长文本
    
    # 分块
    chunks = document_processor._split_text_into_chunks(long_text)
    
    # 验证结果
    assert len(chunks) > 1  # 应该被分成多个块
    for chunk in chunks:
        assert len(chunk) <= document_processor.CHUNK_SIZE  # 每个块的大小不超过限制

def test_split_text_into_chunks_short(document_processor):
    """测试短文本分块"""
    # 短文本内容
    short_text = "这是一个短文本。"
    
    # 分块
    chunks = document_processor._split_text_into_chunks(short_text)
    
    # 验证结果
    assert len(chunks) == 1  # 短文本应该保持为一个块
    assert chunks[0] == short_text

def test_clean_text(document_processor):
    """测试文本清理功能"""
    # 包含特殊字符的文本
    dirty_text = "  产品名称：  智能助手  \n\n价格：\t100元   "
    
    # 清理文本
    cleaned_text = document_processor._clean_text(dirty_text)
    
    # 验证结果
    assert cleaned_text == "产品名称：智能助手\n价格：100元"
    assert cleaned_text.strip() == cleaned_text  # 没有前后空格