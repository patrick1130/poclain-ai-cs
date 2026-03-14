import pytest
from unittest.mock import Mock
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """模拟环境变量"""
    monkeypatch.setenv('DOUBAO_API_KEY', 'mock_api_key')
    monkeypatch.setenv('DOUBAO_API_SECRET', 'mock_api_secret')
    monkeypatch.setenv('CHROMA_DB_PATH', ':memory:')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('WECHAT_APPID', 'mock_appid')
    monkeypatch.setenv('WECHAT_APPSECRET', 'mock_appsecret')
    monkeypatch.setenv('WECHAT_TOKEN', 'mock_token')
    monkeypatch.setenv('WECHAT_ENCODING_AES_KEY', 'mock_encoding_aes_key')

@pytest.fixture
def mock_settings():
    """模拟应用设置"""
    from app.core.config import settings
    settings.doubao_api_key = 'mock_api_key'
    settings.doubao_api_secret = 'mock_api_secret'
    settings.chroma_db_path = ':memory:'
    return settings

def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line("markers", "asyncio: mark test as asyncio")
    config.addinivalue_line("markers", "slow: mark test as slow")