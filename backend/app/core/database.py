import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

logger = logging.getLogger(__name__)

try:
    # 【性能与安全修复】配置高并发连接池防崩溃机制
    # pool_pre_ping=True: 自动校验并重连失效的 MySQL 幽灵连接 (防止 Server gone away)
    # pool_size=20, max_overflow=50: 严格控制并发水位，防止流量洪峰将数据库瞬间打宕机
    # pool_recycle=1800: 每 30 分钟强制回收连接，防止 MySQL 服务端主动断开
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=50,
        pool_timeout=30,
        pool_recycle=1800,
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 【架构修复】显式定义并导出 ORM 映射基类 Base，彻底解决 ImportError 启动崩溃
    Base = declarative_base()

except Exception as e:
    logger.error(f"数据库引擎初始化失败，请检查 DATABASE_URL 配置是否正确: {e}")
    raise e


def get_db():
    """
    数据库会话依赖生成器 (FastAPI Dependency)
    确保每个 HTTP/WebSocket 请求获得独立的 Session，并在请求结束后严格、安全地将连接释放回连接池
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
