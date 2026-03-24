import os
import logging
from fastapi import APIRouter

# 物理屏蔽遥测与日志噪音
os.environ["ANONYMIZED_TELEMETRY"] = "False"
logging.getLogger("onnxruntime").setLevel(logging.ERROR)

# 🚨 架构师修正：从子模块导入具体的 router 实例
from .wechat import router as wechat_router
from .knowledge import router as knowledge_router
from .service import router as service_router

api_router = APIRouter()

# 🚨 统一前缀分发，确保路径为 /api/v1/wechat, /api/v1/knowledge, /api/v1/service
api_router.include_router(wechat_router, prefix="/wechat", tags=["WeChat Gateway"])
api_router.include_router(
    knowledge_router, prefix="/knowledge", tags=["Knowledge Base"]
)
api_router.include_router(service_router, prefix="/service", tags=["Service Agent"])
