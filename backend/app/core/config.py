from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Union
import os
from pathlib import Path

# 获取项目的绝对根目录，锚定物理坐标，防止路径漂移
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """应用配置类，使用pydantic-settings管理配置"""

    # 应用基本配置
    PROJECT_NAME: str = "微信智能客服系统"
    API_V1_STR: str = "/api/v1"

    # 【安全修复】强制从环境变量加载，剔除硬编码，防止密码泄露
    SECRET_KEY: str = Field(..., description="JWT核心加密密钥，不可泄露")

    # 【架构修复】引入系统初始管理员密码配置，接管 .env 中的值
    ADMIN_PASSWORD: str = Field(
        default="PoclainAdmin2026!", description="系统初始管理员密码"
    )

    # 【安全修复】引入合规的 CORS 白名单列表，并支持灵活的环境变量解析
    CORS_ORIGINS: Union[str, List[str]] = Field(
        default=[
            "http://localhost:8080",
            "http://localhost:3000",
            "http://127.0.0.1:8000",
        ],
        description="允许跨域访问的前端域名白名单",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """增强解析器：允许 .env 中使用逗号分隔的字符串配置 CORS"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # 数据库配置
    DATABASE_URL: str = Field(..., description="数据库连接DSN")

    # Redis配置
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0", description="Redis连接池地址"
    )

    # 【架构修复】向量数据库配置：计算绝对路径，彻底消灭基于 CWD 的数据幽灵风险
    VECTOR_DB_PATH: str = Field(
        default=str(BASE_DIR / "vector_db"), description="ChromaDB本地持久化绝对路径"
    )

    # 微信公众号配置
    WX_APPID: str = Field(..., description="微信AppID")
    WX_APPSECRET: str = Field(..., description="微信AppSecret")
    WX_TOKEN: str = Field(..., description="微信消息校验Token")
    WX_ENCODING_AES_KEY: str = Field(..., description="微信消息加密AES Key")

    # 【同源双擎重构】阿里云百炼生态闭环配置
    DASHSCOPE_API_KEY: str = Field(..., description="阿里云百炼 API 密钥")
    PRIMARY_CHAT_MODEL: str = "deepseek-v3"  # 主引擎：阿里云托管的 DeepSeek-V3
    BACKUP_CHAT_MODEL: str = "qwen-max"  # 备引擎：阿里云最强的通义千问 Max

    # 【致命安全修复】生产环境兜底防线，默认必须关闭
    DEBUG: bool = False

    # 工作时间配置
    WORK_DAYS: str = "1,2,3,4,5"  # 周一到周五
    WORK_START_TIME: str = "09:00:00"
    WORK_END_TIME: str = "18:00:00"

    # 会话配置
    SESSION_TIMEOUT: int = 1800  # 会话超时时间（秒）
    MAX_MESSAGE_LENGTH: int = 2000  # 最大消息长度

    # 知识库配置
    KNOWLEDGE_CHUNK_SIZE: int = 500  # 知识库文档切片大小
    KNOWLEDGE_CHUNK_OVERLAP: int = 50  # 切片重叠大小
    RETRIEVAL_TOP_K: int = 3  # 检索返回的最大文档数
    RETRIEVAL_THRESHOLD: float = 0.7  # 检索相似度阈值

    # 加载策略：优先读取环境变量，其次读取.env文件
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# 创建全局配置实例
settings = Settings()
