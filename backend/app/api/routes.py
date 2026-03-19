from fastapi import APIRouter
import os
import logging

# 物理屏蔽遥测与日志噪音
os.environ["ANONYMIZED_TELEMETRY"] = "False"
logging.getLogger("onnxruntime").setLevel(logging.ERROR)

from .wechat import router as wechat_router
from .knowledge import router as knowledge_router
from .service import router as service_router

api_router = APIRouter()

# 🚨 架构师修正：去掉重复的 service 前缀，确保大屏请求路径为 /api/v1/service/...
api_router.include_router(wechat_router, prefix="/wechat", tags=["WeChat Gateway"])
api_router.include_router(
    knowledge_router, prefix="/knowledge", tags=["Knowledge Base"]
)
api_router.include_router(service_router, prefix="/service", tags=["Service Agent"])
