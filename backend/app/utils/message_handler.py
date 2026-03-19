import asyncio
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, List, Any
import httpx
import time
import json
import logging
import traceback
import re
from dataclasses import dataclass

from ..models.database import CustomerSession, Message, SessionStatus, MessageSender
from ..core.config import settings
from ..utils.vector_db import VectorDB

logger = logging.getLogger(__name__)
vector_db = VectorDB(settings.VECTOR_DB_PATH)

USER_RATE_LIMITS: Dict[str, List[float]] = {}


class IntentAnalyzer:
    GREETING_PATTERN = re.compile(
        r"^(你好|您好|在吗|在不在|有人吗|hi|hello|哈喽|喂)[啊呀吧呢吗\?？\!！~～\s]*$",
        re.IGNORECASE,
    )
    MANUAL_PATTERN = re.compile(r".*(人工|真人|客服|接线员).*", re.IGNORECASE)

    @classmethod
    def is_greeting(cls, text: str) -> bool:
        return len(text.strip()) <= 15 and bool(
            cls.GREETING_PATTERN.match(text.strip())
        )

    @classmethod
    def is_manual_request(cls, text: str) -> bool:
        return bool(cls.MANUAL_PATTERN.search(text.strip()))


class SecurityGuardian:
    INJECTION_PATTERNS = [
        r"忽略.*设定",
        r"扮演.*角色",
        r"system.*prompt",
        r"不再是.*专家",
    ]

    @classmethod
    def check_injection(cls, content: str) -> bool:
        for p in cls.INJECTION_PATTERNS:
            if re.search(p, content.lower()):
                return True
        return False


@dataclass
class MessageContext:
    db: Session
    openid: str
    content: str
    msg_type: str
    session: Optional[CustomerSession] = None
    user: Any = None
    is_h5_ws: bool = False  # 🚨 新增标志位


class MessageHandler:
    def __init__(self):
        self.vector_db = vector_db


async def process_user_message(
    db: Session,
    openid: str,
    content: str,
    msg_type: str = "text",
    is_h5_ws: bool = False,
) -> None:
    try:
        from ..api.wechat import (
            save_or_update_user,
            get_or_create_session,
            save_message,
            send_wx_msg,
        )
        from ..websocket.service import manager, customer_manager

        safe_content = content[:1000]

        if SecurityGuardian.check_injection(safe_content):
            warning_msg = "抱歉，我仅提供 Poclain 相关的技术支持。"
            if is_h5_ws:
                await customer_manager.send_personal_message(
                    {"type": "ai_reply", "content": warning_msg}, openid
                )
            else:
                await send_wx_msg(openid, warning_msg)
            return

        context = MessageContext(
            db=db,
            openid=openid,
            content=safe_content,
            msg_type=msg_type,
            is_h5_ws=is_h5_ws,
        )
        context.user = await save_or_update_user(db, openid)
        context.session = await get_or_create_session(db, openid)

        await save_message(
            db, context.session.id, MessageSender.USER.value, safe_content, msg_type
        )

        # 广播给大屏
        await manager.broadcast_message(
            str(context.session.id),
            {
                "type": "new_message",
                "data": {
                    "id": f"msg_user_{time.time()}",
                    "session_id": str(context.session.id),
                    "content": safe_content,
                    "sender": "user",
                    "created_at": datetime.now().isoformat(),
                },
            },
        )

        handler = MessageHandler()
        await dispatch_message(handler, context)

    except Exception:
        logger.error(f"【消息处理主入口报错】:\n{traceback.format_exc()}")
    finally:
        # 如果是 WS 独立协程启动的 db session，需要在这里关闭
        if is_h5_ws:
            db.close()


async def dispatch_message(self: MessageHandler, context: MessageContext) -> None:
    if context.session.status == SessionStatus.ACTIVE:
        return  # 人工状态，由坐席大屏直接回复，AI 闭嘴
    context.session.status = SessionStatus.AI_HANDLING
    context.db.commit()
    await handle_ai_response_impl(self, context)


async def handle_ai_response_impl(
    self: MessageHandler, context: MessageContext
) -> None:
    from ..api.wechat import save_message, send_wx_msg
    from ..websocket.service import manager, customer_manager

    try:
        if IntentAnalyzer.is_manual_request(context.content):
            transfer_msg = "已收到请求，正在为您呼叫人工..."
            await save_message(
                context.db, context.session.id, MessageSender.AI.value, transfer_msg
            )

            if context.is_h5_ws:
                await customer_manager.send_personal_message(
                    {"type": "ai_reply", "content": transfer_msg}, context.openid
                )
            else:
                await send_wx_msg(context.openid, transfer_msg)

            context.session.status = SessionStatus.PENDING
            context.db.commit()
            await manager.notify_session_update(
                {"id": context.session.id, "status": "pending"}
            )
            return

        if IntentAnalyzer.is_greeting(context.content):
            welcome = "您好！我是 Poclain 智能支持。请问需要了解什么型号参数？"
            await save_message(
                context.db, context.session.id, MessageSender.AI.value, welcome
            )
            if context.is_h5_ws:
                await customer_manager.send_personal_message(
                    {"type": "ai_reply", "content": welcome}, context.openid
                )
            else:
                await send_wx_msg(context.openid, welcome)
            return

        # RAG 检索
        try:
            res = await asyncio.wait_for(
                self.vector_db.search(context.content, 5, 0.1), timeout=8.0
            )
            knowledge = (
                "\n\n".join([r["document"] for r in res]) if res else "无明确资料"
            )
        except Exception:
            knowledge = ""

        chat_history = []  # 简化历史处理

        system_prompt = (
            f"你是一个 Poclain 客服。只根据资料回答:\n[资料]\n{knowledge}\n[结束]"
        )

        # 🚨 架构师核心重构：流式输出与 H5 逐字打印
        full_answer = ""

        # 针对 H5 网页：开启流式打字机模式
        if context.is_h5_ws:
            # 先给前端发一个开始标志，准备打字
            await customer_manager.send_personal_message(
                {"type": "ai_stream_start"}, context.openid
            )

            # 使用流式生成生成器
            async for chunk in _call_bailian_api_stream(
                context.content, system_prompt, chat_history
            ):
                full_answer += chunk
                # 逐字推送到手机前端
                await customer_manager.send_personal_message(
                    {"type": "ai_stream_chunk", "content": chunk}, context.openid
                )

            # 打字结束
            await customer_manager.send_personal_message(
                {"type": "ai_stream_end"}, context.openid
            )

        else:
            # 兼容老版微信公众号：一次性生成发送
            full_answer = await _call_bailian_api_sync(
                context.content, system_prompt, chat_history
            )
            await send_wx_msg(context.openid, full_answer)

        # 结果存入 MySQL 历史
        await save_message(
            context.db, context.session.id, MessageSender.AI.value, full_answer
        )

        # 广播给坐席大屏
        await manager.broadcast_message(
            str(context.session.id),
            {
                "type": "new_message",
                "data": {
                    "session_id": str(context.session.id),
                    "content": full_answer,
                    "sender": "ai",
                },
            },
        )

    except Exception:
        logger.error(f"AI 生成故障: {traceback.format_exc()}")


# ==========================================
# 🚨 架构师新增：真正的流式生成生成器 (Streaming Generator)
# ==========================================
async def _call_bailian_api_stream(
    question: str, system_prompt: str, chat_history: list
):
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"}
    payload = {
        "model": settings.PRIMARY_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "temperature": 0.01,
        "stream": True,  # 开启流式阀门
    }

    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST", url, headers=headers, json=payload, timeout=60.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        data_json = json.loads(line[6:])
                        chunk = (
                            data_json["choices"][0].get("delta", {}).get("content", "")
                        )
                        if chunk:
                            yield chunk
        except Exception as e:
            logger.error(f"流式请求失败: {e}")
            yield "系统响应超时或发生故障。"


async def _call_bailian_api_sync(
    question: str, system_prompt: str, chat_history: list
) -> str:
    # 保留旧版的阻塞调用，用于微信原生回包
    pass  # 具体逻辑同你原有的 _call_bailian_api_with_fallback
