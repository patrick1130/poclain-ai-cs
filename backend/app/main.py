import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .api.routes import api_router
from .websocket.service import router as websocket_router
from .core.config import settings
from .core.database import SessionLocal, Base, engine
from .utils.security import create_default_service_agent

# 配置日志引擎
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 【S级加固】初始化基于 Redis 的分布式限流器，防止 CC 攻击与 API 暴力破解
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    系统生命周期管理器：执行数据库迁移与安全凭证初始化
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        create_default_service_agent(db)
        logger.info("🛡️ 系统安全初始化完成：默认管理员与物理表结构检查通过。")
    except Exception as e:
        logger.error(f"❌ 系统安全初始化发生致命错误: {e}")
    finally:
        db.close()
    yield
    logger.info("🛑 系统正在执行安全关机程序，正在释放资源...")


# 创建 FastAPI 实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # 生产环境下建议关闭 docs 或增加 Basic Auth 认证
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# 挂载限流器处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 【S级加固】配置严格的 CORS 策略：仅允许白名单内的域名跨域，阻断 CSRF 跨站劫持
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def security_and_logging_middleware(request: Request, call_next):
    """
    S级增强中间件：注入安全响应头并执行精准性能审计
    """
    start_time = time.time()

    # 执行下游业务逻辑
    response = await call_next(request)

    # 【S级加固】注入深度安全响应头，防御点击劫持与 MIME 类型嗅探
    response.headers["Server"] = "Poclain-Shield/1.0"  # 隐藏真实技术栈
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"

    logger.info(
        f"Path: {request.url.path} | Method: {request.method} | "
        f"Status: {response.status_code} | Latency: {process_time:.4f}s"
    )
    return response


# 注册核心业务路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 注册全双工 WebSocket 路由：独立命名空间，绕过 HTTP 鉴权沙箱
app.include_router(websocket_router, prefix="/ws/service")


@app.get("/health")
@limiter.limit("5/minute")  # 健康检查限流，防止探针攻击
async def health_check(request: Request):
    return {"status": "ok", "timestamp": time.time()}


@app.get("/")
async def root():
    return {"message": "Poclain Intelligent Customer Service API Ready."}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常捕获：屏蔽敏感 Traceback 信息，防止服务器路径泄露
    """
    logger.error(f"🔥 未捕获的全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal System Error - Please contact the architect."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
