import json
import logging
import asyncio
import time
import redis.asyncio as redis  # 🚨 引入异步 Redis
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.models.database import ServiceAgent, CustomerSession, SessionStatus
from app.utils.security import verify_token
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# 🚨 架构师加固：分布式 Redis 广播通道
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


# ==========================================
# 管理器 1：大屏坐席 WebSocket 引擎 (分布式版)
# ==========================================
class ServiceConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.MAX_CONNECTIONS_PER_AGENT = 5
        self.MAX_PAYLOAD_SIZE = 65536
        self.pubsub_task = None

    async def _listen_redis_broadcast(self):
        """🚨 核心加固：分布式监听协程，抓取来自其他进程的消息广播"""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("poclain:service:updates")
        logger.info("📡 分布式订阅引擎已启动：监听 poclain:service:updates")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = json.loads(message["data"])
                    # 物理下发给本进程内的所有在线坐席
                    for sid in list(self.active_connections.keys()):
                        for ws in list(self.active_connections[sid]):
                            try:
                                await ws.send_text(json.dumps(data))
                            except:
                                pass
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"❌ Redis 订阅任务崩溃: {e}")

    async def connect(self, websocket: WebSocket, service_id: str):
        # 懒加载监听任务
        if not self.pubsub_task:
            self.pubsub_task = asyncio.create_task(self._listen_redis_broadcast())

        if service_id not in self.active_connections:
            self.active_connections[service_id] = set()

        if len(self.active_connections[service_id]) >= self.MAX_CONNECTIONS_PER_AGENT:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

        self.active_connections[service_id].add(websocket)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "message": "Pipeline Established.",
                }
            )
        )
        return True

    def disconnect(self, service_id: str, websocket: WebSocket):
        if service_id in self.active_connections:
            self.active_connections[service_id].discard(websocket)

    async def notify_session_update(self, session_data: dict):
        """🚨 架构师加固：不再只发给本地，而是向 Redis 频道广播"""
        msg = {"type": "session_update", "data": session_data}
        await redis_client.publish("poclain:service:updates", json.dumps(msg))

    async def broadcast_message(self, session_id: str, message: dict):
        """🚨 架构师加固：全网广播实时对话详情"""
        await redis_client.publish("poclain:service:updates", json.dumps(message))


manager = ServiceConnectionManager()


# ==========================================
# 管理器 2：H5 客户 WebSocket 引擎
# ==========================================
class CustomerConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, openid: str):
        await websocket.accept()
        if openid in self.active_connections:
            try:
                await self.active_connections[openid].close(code=4000)
            except:
                pass
        self.active_connections[openid] = websocket

    def disconnect(self, openid: str):
        self.active_connections.pop(openid, None)

    async def send_personal_message(self, message: dict, openid: str):
        if openid in self.active_connections:
            try:
                await self.active_connections[openid].send_text(json.dumps(message))
            except:
                self.disconnect(openid)


customer_manager = CustomerConnectionManager()


# ==========================================
# WebSocket 端点入口
# ==========================================
@router.websocket("/customer/{openid}")
async def customer_ws_endpoint(websocket: WebSocket, openid: str):
    await customer_manager.connect(websocket, openid)
    from app.utils.message_handler import process_user_message

    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=120.0)
            payload = json.loads(data)
            if payload.get("type") == "user_message":
                content = payload.get("content")
                # 🚨 物理隔离：启动独立 Session 处理 AI 逻辑
                asyncio.create_task(
                    process_user_message(SessionLocal(), openid, content, is_h5_ws=True)
                )
    except:
        pass
    finally:
        customer_manager.disconnect(openid)


@router.websocket("/{service_id}")
async def websocket_endpoint(websocket: WebSocket, service_id: str):
    await websocket.accept()
    try:
        token = websocket.query_params.get("token")
        payload = verify_token(token)
        if not payload or str(payload.get("sub")) != service_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if not await manager.connect(websocket, service_id):
            return
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=90.0)
            p_data = json.loads(data)
            if p_data.get("type") == "agent_message":
                sid, content = p_data.get("session_id"), p_data.get("content")
                db = SessionLocal()
                try:
                    s = (
                        db.query(CustomerSession)
                        .filter(CustomerSession.id == sid)
                        .first()
                    )
                    if s:
                        await customer_manager.send_personal_message(
                            {"type": "agent_reply", "content": content}, s.user_id
                        )
                finally:
                    db.close()
    except WebSocketDisconnect:
        raise
    except:
        pass
    finally:
        manager.disconnect(service_id, websocket)
