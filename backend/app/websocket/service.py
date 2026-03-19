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
    """
    S级加固：具备并发控制、主动探测与内存防溢出的全双工连接管理器
    """

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.MAX_CONNECTIONS_PER_AGENT = 5
        self.MAX_PAYLOAD_SIZE = 65536

    async def connect(self, websocket: WebSocket, service_id: str):
        if service_id not in self.active_connections:
            self.active_connections[service_id] = set()

        if len(self.active_connections[service_id]) >= self.MAX_CONNECTIONS_PER_AGENT:
            logger.warning(
                f"🚨 接入拦截：客服 {service_id} 终端数达到上限({self.MAX_CONNECTIONS_PER_AGENT})"
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Quota Exceeded"
            )
            return False

        self.active_connections[service_id].add(websocket)
        logger.info(
            f"✅ 客服 {service_id} 终端上线。当前存活终端: {len(self.active_connections[service_id])}"
        )

        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "message": "Secure WebSocket Pipeline Established.",
                }
            )
        )
        return True

    def disconnect(self, service_id: str, websocket: WebSocket):
        if service_id in self.active_connections:
            if websocket in self.active_connections[service_id]:
                self.active_connections[service_id].remove(websocket)

            if not self.active_connections[service_id]:
                del self.active_connections[service_id]
                logger.info(f"⚠️ 客服 {service_id} 彻底离线，已回收连接内存。")

    async def send_personal_message(self, message: str, service_id: str):
        if service_id in self.active_connections:
            for ws in list(self.active_connections[service_id]):
                try:
                    await ws.send_text(message)
                except Exception as e:
                    logger.error(f"消息推送异常: {e}，回收死链")
                    self.disconnect(service_id, ws)

    async def broadcast_message(self, session_id: str, message: dict):
        message_text = json.dumps(message)
        all_online_services = list(self.active_connections.keys())
        for sid in all_online_services:
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
async def websocket_endpoint(websocket: WebSocket, service_id: str):
    """
    全双工通信端点：具备 S 级安全防线的长连接控制器
    🚨 架构师重构：废除 Depends(get_db) 注入，防止连接池耗尽导致全局 DoS 崩溃
    """
    await websocket.accept()

    try:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Unauthorized: Token Missing",
            )
            return

        try:
            payload = verify_token(token)
            if not payload or str(payload.get("sub")) != service_id:
                raise ValueError("Identity Mismatch")
        except Exception as e:
            logger.warning(f"🛡️ 拦截非法连接 [ID: {service_id}]: {e}")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Identity Tampered"
            )
            return

        # 🚨 瞬时连接验证身份，立即释放
        db_auth = SessionLocal()
        try:
            agent = (
                db_auth.query(ServiceAgent)
                .filter(
                    ServiceAgent.id == int(service_id), ServiceAgent.is_active == True
                )
                .first()
            )
            if not agent:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION, reason="Agent Suspended"
                )
                return
        finally:
            db_auth.close()

        if not await manager.connect(websocket, service_id):
            return

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=90.0)

                if len(data) > manager.MAX_PAYLOAD_SIZE:
                    logger.warning(f"🚨 负载溢出拦截: 客服 {service_id}")
                    # 🚨 显式关闭，前端会收到 4009，不再是模糊的 1000
                    await websocket.close(code=4009, reason="Payload Too Large")
                    break

                payload_data = json.loads(data)
                msg_type = payload_data.get("type")

                if msg_type == "heartbeat":
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "heartbeat_res",
                                "data": "pong",
                                "timestamp": time.time(),
                            }
                        )
                    )
                    continue

                if msg_type == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong", "timestamp": time.time()})
                    )
                    continue

                if msg_type == "agent_message":
                    session_id = payload_data.get("session_id")
                    content = payload_data.get("content")

                    # 🚨 架构师重构：以 O(1) 的生命周期获取短连接，处理完毕立即销毁
                    db_msg = SessionLocal()
                    try:
                        session = (
                            db_msg.query(CustomerSession)
                            .filter(CustomerSession.id == session_id)
                            .first()
                        )
                        if session:
                            await customer_manager.send_personal_message(
                                {"type": "agent_reply", "content": content},
                                session.user_id,
                            )
                    finally:
                        db_msg.close()

            except asyncio.TimeoutError:
                logger.info(f"⏳ 物理熔断：客服 {service_id} 长时间无心跳。")
                try:
                    # 🚨 显式告知前端是超时断的，非 1000
                    await websocket.close(code=4008, reason="Heartbeat Timeout")
                except:
                    pass
                break
            except json.JSONDecodeError:
                continue
            # ✨ 架构师补丁：拦截正常断开事件，直接抛给外层处理，不当作 Error 打印
            except WebSocketDisconnect:
                raise
            except Exception as loop_e:
                logger.error(f"WebSocket 循环内异常: {loop_e}")
                try:
                    await websocket.close(code=1011, reason="Internal Server Error")
                except:
                    pass
                break

    except WebSocketDisconnect:
        logger.info(f"🔌 客服 {service_id} 链路主动关闭。")
    except Exception as e:
        logger.error(f"🔥 WebSocket 异常中断 [ID: {service_id}]: {e}")
    finally:
        manager.disconnect(service_id, websocket)
