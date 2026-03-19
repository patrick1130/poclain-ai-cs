import time
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 导入业务组件
from .api.routes import api_router
from .websocket.service import router as websocket_router
from .core.config import settings
from .core.database import SessionLocal, Base, engine
from .utils.security import create_default_service_agent
from .exceptions import WeChatCustomerServiceException

# 配置日志引擎
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 初始化限流器
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """系统生命周期管理器"""
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
    logger.info("🛑 系统正在执行安全关机程序...")


# 创建 FastAPI 实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ==========================================
# 🚨 架构师修正：修复致命 CORS 漏洞，严格桥接安全白名单
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # 物理阻断通配符，启用动态白名单
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 挂载限流处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_and_logging_middleware(request: Request, call_next):
    """安全响应头与性能监控中间件"""
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        # 注入安全响应头
        response.headers["Server"] = "Poclain-Shield/1.0"
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"

        logger.info(
            f"Path: {request.url.path} | Method: {request.method} | "
            f"Status: {response.status_code} | Latency: {process_time:.4f}s"
        )
        return response
    except Exception as e:
        # 发生崩溃时也要保证日志记录
        logger.error(f"中间件捕获崩溃: {e}")
        raise


# ==========================================
# 🚨 架构师路由挂载区
# ==========================================

# 1. 注册 HTTP 业务路由 (前缀通常是 /api/v1)
app.include_router(api_router, prefix=settings.API_V1_STR)

# 2. 注册 WebSocket 路由 (确保没有重复的前缀嵌套)
# 这里的 prefix="/ws/service" 配合 router.websocket("/customer/{openid}")
# 最终地址就是 ws://127.0.0.1:8000/ws/service/customer/...
app.include_router(websocket_router, prefix="/ws/service")


@app.get("/health")
@limiter.limit("5/minute")
async def health_check(request: Request):
    return {"status": "ok", "timestamp": time.time()}


@app.get("/")
async def root():
    return {"message": "Poclain Intelligent Customer Service API Ready."}


@app.exception_handler(WeChatCustomerServiceException)
async def custom_business_exception_handler(
    request: Request, exc: WeChatCustomerServiceException
):
    logger.warning(f"⚠️ 业务防线拦截 | Code: {exc.error_code} | Msg: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code or 500,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"🔥 未捕获的底层崩溃: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal System Error"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
