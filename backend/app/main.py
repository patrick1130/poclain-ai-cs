import time
import logging
import os
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 导入业务组件
from .api.routes import api_router

# 🚨 架构师修正：仅导入剥离出的纯净 ws_router，彻底防备 O(N) HTTP 接口越权暴露
from .api.service import ws_router as service_ws_router
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
    """系统生命周期管理器：执行物理表结构检查与安全初始化"""
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
from app.api import backup

app.include_router(backup.router, prefix="/api")
# ==========================================
# 🚨 架构师安全加固：严格 CORS 协议装甲
# ==========================================
allow_origins = ["*"] if settings.DEBUG else settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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
    is_upload = "/upload" in request.url.path

    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["Server"] = "Poclain-Shield/1.0"
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"

        return response
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(
            f"❌ 中间件捕获严重崩溃 (Path: {request.url.path}): {e}\n{error_trace}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Internal System Error during middleware execution: {str(e)}",
                "path": request.url.path,
            },
        )


# 1. 注册 HTTP 业务路由矩阵
app.include_router(api_router, prefix=settings.API_V1_STR)

# 2. 🚨 仅挂载纯净的 WebSocket 端点，防止 HTTP 混入 /ws/ 路径被外网直接穿透
app.include_router(service_ws_router, prefix="/ws/service")


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}


@app.get("/")
async def root():
    return {"message": "Poclain Intelligent Customer Service API Ready."}


@app.exception_handler(WeChatCustomerServiceException)
async def custom_business_exception_handler(
    request: Request, exc: WeChatCustomerServiceException
):
    return JSONResponse(
        status_code=exc.status_code or 400,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()
    logger.error(f"🔥 未捕获的系统级崩溃: {exc}\n{error_trace}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal System Error - Handled by Global Guardian",
            "msg": str(exc),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
