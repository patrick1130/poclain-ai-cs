# File: backend/app/websocket/service.py

import json
import logging
import asyncio
import time
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import ServiceAgent
from app.utils.security import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


class ServiceConnectionManager:
    """
    S级加固：具备并发控制、主动探测与内存防溢出的全双工连接管理器
    """

    def __init__(self):
        # 核心映射: {service_id: Set[WebSocket]}
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # 反向索引订阅: {session_id: Set[service_id]}
        self.session_subscribers: Dict[str, Set[str]] = {}
        # 客服订阅清单: {service_id: Set[session_id]}
        self.service_subscriptions: Dict[str, Set[str]] = {}

        # 【S级参数】资源隔离阈值
        self.MAX_CONNECTIONS_PER_AGENT = 5  # 限制单人最大终端数，防止 Socket 耗尽攻击
        self.MAX_PAYLOAD_SIZE = 65536  # 64KB 报文熔断线

    async def connect(self, websocket: WebSocket, service_id: str):
        """建立连接并执行并发配额检查"""
        if service_id not in self.active_connections:
            self.active_connections[service_id] = set()
            self.service_subscriptions[service_id] = set()

        # 【S级加固】并发配额检查
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

        # 发送握手确认
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
        """物理销毁死链，执行内存真空回收"""
        if service_id in self.active_connections:
            if websocket in self.active_connections[service_id]:
                self.active_connections[service_id].remove(websocket)

            # 当最后一位终端离线，释放所有订阅内存，防止内存泄漏 (OOM)
            if not self.active_connections[service_id]:
                del self.active_connections[service_id]
                subs = self.service_subscriptions.pop(service_id, set())
                for sid in subs:
                    if sid in self.session_subscribers:
                        self.session_subscribers[sid].discard(service_id)
                        if not self.session_subscribers[sid]:
                            del self.session_subscribers[sid]
                logger.info(f"⚠️ 客服 {service_id} 彻底离线，已回收所有订阅内存。")

    async def send_personal_message(self, message: str, service_id: str):
        """定向推送：支持多端同步"""
        if service_id in self.active_connections:
            # 使用 list() 避免在迭代时因 disconnect 导致集合变更报错
            for ws in list(self.active_connections[service_id]):
                try:
                    await ws.send_text(message)
                except Exception as e:
                    logger.error(f"消息推送异常: {e}，回收死链")
                    self.disconnect(service_id, ws)

    async def broadcast_message(self, session_id: str, message: dict):
        """靶向广播：精确推送到订阅了该会话的客服终端"""
        message_text = json.dumps(message)
        subscribers = self.session_subscribers.get(session_id, set())
        for sid in list(subscribers):
            await self.send_personal_message(message_text, sid)

    async def subscribe_session(self, service_id: str, session_id: str):
        """建立 O(1) 订阅映射"""
        if service_id in self.service_subscriptions:
            self.service_subscriptions[service_id].add(session_id)
        if session_id not in self.session_subscribers:
            self.session_subscribers[session_id] = set()
        self.session_subscribers[session_id].add(service_id)

    async def notify_new_session(self, session_data: dict):
        """全局通知：新会话进入待办池"""
        msg = json.dumps({"type": "new_session", "data": session_data})
        for sid in list(self.active_connections.keys()):
            await self.send_personal_message(msg, sid)


# 初始化全局单例管理器
manager = ServiceConnectionManager()


@router.websocket("/{service_id}")
async def websocket_endpoint(
    websocket: WebSocket, service_id: str, db: Session = Depends(get_db)
):
    """
    全双工通信端点：具备 S 级安全防线的长连接控制器
    """
    # 1. 物理握手
    await websocket.accept()

    try:
        # 2. 鉴权：从查询参数提取 Token (绕过浏览器 Headers 限制)
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Unauthorized: Token Missing",
            )
            return

        # 3. 严格校验签名与身份绑定
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

        # 4. 业务状态校验：账号是否被封禁或禁用
        agent = (
            db.query(ServiceAgent)
            .filter(ServiceAgent.id == int(service_id), ServiceAgent.is_active == True)
            .first()
        )

        if not agent:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Agent Suspended"
            )
            return

        # 5. 执行连接管理与配额检查
        if not await manager.connect(websocket, service_id):
            return

        # 6. 【S级加固】长连接守护循环
        while True:
            try:
                # 核心防线：心跳熔断计时器。60秒无任何输入即强制释放，防止僵尸连接占用 TCP 端口。
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)

                # 核心防线：负载长度限制。单次报文严禁超过 64KB，阻断 Buffer Overflow 类型攻击。
                if len(data) > manager.MAX_PAYLOAD_SIZE:
                    logger.warning(
                        f"🚨 负载溢出拦截: 客服 {service_id} 发送报文过大({len(data)} bytes)"
                    )
                    break

                payload_data = json.loads(data)
                msg_type = payload_data.get("type")

                # 订阅逻辑处理
                if msg_type == "subscribe" and payload_data.get("session_id"):
                    await manager.subscribe_session(
                        service_id, str(payload_data["session_id"])
                    )

                # 双向心跳支持
                elif msg_type == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong", "timestamp": time.time()})
                    )

            except asyncio.TimeoutError:
                logger.info(f"⏳ 物理熔断：客服 {service_id} 长时间无心跳。")
                break
            except json.JSONDecodeError:
                continue

    except WebSocketDisconnect:
        manager.disconnect(service_id, websocket)
    except Exception as e:
        logger.error(f"🔥 WebSocket 异常中断 [ID: {service_id}]: {e}")
        manager.disconnect(service_id, websocket)
