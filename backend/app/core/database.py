import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

# 🚨 架构师加固：配置日志引擎，捕获底层 SQL 异常轨迹
logger = logging.getLogger(__name__)


# 【架构演进】SQLAlchemy 2.0 现代声明式基类
# 替代旧版的 declarative_base() 函数，提供更完美的 Type Hint 与静态检查支持
class Base(DeclarativeBase):
    """
    S级架构基类：
    在此处预留类型映射扩展，确保 KnowledgeDoc.content 在 MySQL 中
    能被正确推导为 LONGTEXT 而非受限的 TEXT。
    """

    pass


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
        # 🚨 架构师加固：设置连接编码，确保多 Sheet 中的特殊字符（如液压符号）不乱码
        connect_args={"charset": "utf8mb4"},
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

except Exception as e:
    logger.error(f"❌ 数据库引擎初始化失败，请检查 DATABASE_URL 配置是否正确: {e}")
    raise e


def get_db():
    """
    数据库会话依赖生成器 (FastAPI Dependency)
    确保每个 HTTP/WebSocket 请求获得独立的 Session，并在请求结束后严格、安全地将连接释放回连接池。
    采用 try...finally 结构是防止连接泄露（Connection Leak）的最后一道防线。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # 🚨 架构师安全指令：强制显式关闭，将连接归还给池，防止 MySQL 线程数溢出
        db.close()
