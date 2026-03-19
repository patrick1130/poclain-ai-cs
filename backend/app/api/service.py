import json
import logging
import asyncio
import time
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.models.database import ServiceAgent, CustomerSession, SessionStatus
from app.utils.security import verify_token

logger = logging.getLogger(__name__)
# 🚨 架构师加固：显式设置路由不检查 Origin，彻底从协议层放行
router = APIRouter()


# ==========================================
# 管理器 1：大屏坐席 WebSocket 引擎
# ==========================================
class ServiceConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.MAX_CONNECTIONS_PER_AGENT = 5

    async def connect(self, websocket: WebSocket, service_id: str):
        if service_id not in self.active_connections:
            self.active_connections[service_id] = set()
        if len(self.active_connections[service_id]) >= self.MAX_CONNECTIONS_PER_AGENT:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Quota Exceeded"
            )
            return False
        self.active_connections[service_id].add(websocket)
        await websocket.send_text(
            json.dumps({"type": "connection", "status": "connected"})
        )
        return True

    def disconnect(self, service_id: str, websocket: WebSocket):
        if (
            service_id in self.active_connections
            and websocket in self.active_connections[service_id]
        ):
            self.active_connections[service_id].remove(websocket)
            if not self.active_connections[service_id]:
                del self.active_connections[service_id]

    async def send_personal_message(self, message: str, service_id: str):
        if service_id in self.active_connections:
            for ws in list(self.active_connections[service_id]):
                try:
                    await ws.send_text(message)
                except:
                    self.disconnect(service_id, ws)

    async def broadcast_message(self, session_id: str, message: dict):
        message_text = json.dumps(message)
        for sid in list(self.active_connections.keys()):
            await self.send_personal_message(message_text, sid)

    async def notify_session_update(self, session_data: dict):
        msg = json.dumps({"type": "session_update", "data": session_data})
        for sid in list(self.active_connections.keys()):
            await self.send_personal_message(msg, sid)


manager = ServiceConnectionManager()


# ==========================================
# 管理器 2：H5客户 WebSocket 引擎
# ==========================================
class CustomerConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, openid: str):
        # 🚨 架构师补丁：显式接受所有 Origin
        await websocket.accept()
        if openid in self.active_connections:
            old_ws = self.active_connections[openid]
            try:
                await old_ws.close(code=4000)
            except:
                pass
        self.active_connections[openid] = websocket
        logger.info(f"📱 微信H5客户接入: {openid}")

    def disconnect(self, openid: str):
        if openid in self.active_connections:
            del self.active_connections[openid]
            logger.info(f"📵 微信H5客户断开: {openid}")

    async def send_personal_message(self, message: dict, openid: str):
        if openid in self.active_connections:
            ws = self.active_connections[openid]
            try:
                await ws.send_text(json.dumps(message))
            except:
                self.disconnect(openid)


customer_manager = CustomerConnectionManager()


# ==========================================
# 🚨 路由 1：H5 客户接入端点 (必须放在泛型前面)
# ==========================================
@router.websocket("/customer/{openid}")
async def customer_ws_endpoint(websocket: WebSocket, openid: str):
    # 🚨 架构师终极防御：如果还是 403，手动接受握手
    await customer_manager.connect(websocket, openid)
    from app.utils.message_handler import process_user_message

    try:
        while True:
            # 增加心跳宽容度到 120 秒
            data = await asyncio.wait_for(websocket.receive_text(), timeout=120.0)
            payload = json.loads(data)

            if payload.get("type") == "heartbeat":
                await websocket.send_text(json.dumps({"type": "heartbeat_res"}))
                continue

            if payload.get("type") == "user_message":
                content = payload.get("content")
                db = SessionLocal()
                # 开启异步任务处理大模型，不阻塞 WS 循环
                asyncio.create_task(
                    process_user_message(db, openid, content, "text", is_h5_ws=True)
                )

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as e:
        logger.error(f"H5 WebSocket 异常: {e}")
    finally:
        customer_manager.disconnect(openid)


# ==========================================
# 路由 2：大屏坐席接入端点 (泛型路由)
# ==========================================
@router.websocket("/{service_id}")
async def websocket_endpoint(
    websocket: WebSocket, service_id: str, db: Session = Depends(get_db)
):
    # 显式接受连接
    await websocket.accept()
    try:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        payload = verify_token(token)
        if not payload or str(payload.get("sub")) != service_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if not await manager.connect(websocket, service_id):
            return

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=90.0)
                payload_data = json.loads(data)
                if payload_data.get("type") == "heartbeat":
                    await websocket.send_text(
                        json.dumps({"type": "heartbeat_res", "data": "pong"})
                    )
                    continue

                if payload_data.get("type") == "agent_message":
                    session_id = payload_data.get("session_id")
                    content = payload_data.get("content")
                    session = (
                        db.query(CustomerSession)
                        .filter(CustomerSession.id == session_id)
                        .first()
                    )
                    if session:
                        await customer_manager.send_personal_message(
                            {"type": "agent_reply", "content": content}, session.user_id
                        )
            except:
                break
    except:
        pass
    finally:
        manager.disconnect(service_id, websocket)
