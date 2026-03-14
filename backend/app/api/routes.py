from fastapi import APIRouter

from .wechat import router as wechat_router
from .knowledge import router as knowledge_router
from .service import router as service_router

api_router = APIRouter()

# 將各個業務模塊掛載到主路由樹，並劃分 Swagger 標籤
api_router.include_router(wechat_router, prefix="/wechat", tags=["WeChat Gateway"])
api_router.include_router(
    knowledge_router, prefix="/knowledge", tags=["Knowledge Base"]
)
# 【架構修復】暴露客服系統的鑑權與管理路由
api_router.include_router(service_router, prefix="/service", tags=["Service Agent"])
