import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import Optional, Any, AsyncGenerator, List, Dict
import httpx
import time
import json
import logging
import traceback
import re
from dataclasses import dataclass

from ..models.database import (
    CustomerSession,
    Message,
    SessionStatus,
    MessageSender,
    PromptConfig,
)
from ..core.config import settings
from ..utils.vector_db import VectorDB

logger = logging.getLogger(__name__)
vector_db = VectorDB(settings.VECTOR_DB_PATH)


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
        r"忽略.*(设定|限制|前提|指令|规则|历史)",
        r"(扮演|作为|你是|变成).*(角色|演员|专家|黑客|人|bot)",
        r"(脱口秀|吐槽|段子|笑话|黑料|缺点|垃圾)",
        r"(system.*prompt|系统.*提示词|内部.*设定)",
        r"不再是.*(波克兰|专家|客服)",
    ]

    @classmethod
    def check_injection(cls, content: str) -> bool:
        clean_content = re.sub(r"[\s\.\-\_\,\!！\?？]", "", content.lower())
        for p in cls.INJECTION_PATTERNS:
            clean_pattern = p.replace(" ", "")
            if re.search(clean_pattern, clean_content):
                logger.warning(f"🛡️ 触发 WAF 熔断: 探测到越狱攻击意图 -> {p}")
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
    is_h5_ws: bool = False


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
        from ..api.service import manager

        safe_content = content[:1000]

        if SecurityGuardian.check_injection(safe_content):
            warning = "抱歉，作为一个专业的波克兰客户服务助手，我无法执行该指令。如果您有关于波克兰产品的问题，欢迎随时提问！"
            if is_h5_ws:
                await manager.broadcast_to_customer(
                    openid, {"type": "ai_reply", "content": warning}
                )
            else:
                await send_wx_msg(openid, warning)
            return

        user = await save_or_update_user(db, openid)
        session = await get_or_create_session(db, openid)

        await save_message(
            db, session.id, MessageSender.USER.value, safe_content, msg_type
        )

        await manager.broadcast_to_agents(
            {
                "type": "session_update",
                "data": {
                    "id": session.id,
                    "user_id": openid,
                    "last_message": safe_content,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": (
                        session.status.value
                        if hasattr(session.status, "value")
                        else str(session.status)
                    ),
                },
            }
        )
        await manager.broadcast_to_agents(
            {
                "type": "new_message",
                "data": {
                    "id": f"msg_u_{time.time()}",
                    "session_id": str(session.id),
                    "content": safe_content,
                    "sender": "user",
                    "created_at": datetime.now().isoformat(),
                    "user_name": session.user_name or "微信访客",
                },
            }
        )

        if session.status == SessionStatus.ACTIVE:
            logger.info(
                f"🤫 会话 {session.id} 处于人工接管状态，消息已送达坐席，AI 静默。"
            )
            return

        context = MessageContext(
            db=db,
            openid=openid,
            content=safe_content,
            msg_type=msg_type,
            is_h5_ws=is_h5_ws,
            session=session,
            user=user,
        )
        await dispatch_message(context)

    except Exception:
        logger.error(f"🔥 链路崩溃: {traceback.format_exc()}")
    finally:
        db.close()


async def dispatch_message(context: MessageContext) -> None:
    context.session.status = SessionStatus.AI_HANDLING
    context.db.commit()
    await handle_ai_response_impl(context)


async def handle_ai_response_impl(context: MessageContext) -> None:
    from ..api.wechat import send_wx_msg
    from ..api.service import manager

    try:
        # 🚨 时间感知与 OOO 拦截网关 (完全保留)
        if IntentAnalyzer.is_manual_request(context.content):
            now = datetime.now()
            is_working_hours = now.weekday() < 5 and 9 <= now.hour < 18

            if is_working_hours:
                msg = "收到，正在为您接入波克兰人工技术支持，请稍候..."
            else:
                ooo_config = (
                    context.db.query(PromptConfig)
                    .filter(PromptConfig.config_key == "ooo_msg")
                    .first()
                )
                if ooo_config and ooo_config.config_value.strip():
                    msg = ooo_config.config_value
                else:
                    msg = "您好！感谢您联系波克兰。我们的客服工作时间为周一至周五 9:00-18:00，当前为非工作时间，人工客服暂不在线。请点击 <a href='https://wj.qq.com/' target='_blank'>【填写表单】</a> 留下您的需求，我们会在工作时间内给您回复。感谢支持！"

            await _finalize_ai_reply(context, msg, is_manual=True, is_streamed=False)
            return

        # 🚨 寒暄识别 (完全保留)
        if IntentAnalyzer.is_greeting(context.content):
            greeting_config = (
                context.db.query(PromptConfig)
                .filter(PromptConfig.config_key == "greeting_msg")
                .first()
            )
            if greeting_config and greeting_config.config_value.strip():
                welcome = greeting_config.config_value
            else:
                welcome = "您好！我是波克兰(Poclain)官方智能助手。请问今天有什么我可以帮您？您可以直接向我咨询产品选型、技术参数、或售后维修事宜。"

            await _finalize_ai_reply(context, welcome, is_streamed=False)
            return

        # 🚨 提取上下文历史 (完全保留)
        raw_history = (
            context.db.query(Message)
            .filter(
                Message.session_id == context.session.id,
                Message.sender.in_([MessageSender.USER, MessageSender.AI]),
            )
            .order_by(desc(Message.created_at))
            .limit(7)
            .all()
        )

        raw_history.reverse()

        chat_history = []
        for msg in raw_history:
            if msg.content == context.content and msg.sender == MessageSender.USER:
                continue
            role = "user" if msg.sender == MessageSender.USER else "assistant"
            chat_history.append({"role": role, "content": msg.content})

        # 🚨 调用重构后的高精度向量检索引擎
        knowledge = ""
        try:
            # 配合重构后的 vector_db.search (阈值自适应)
            res = await asyncio.wait_for(
                vector_db.search(context.content, top_k=5, threshold=0.05), timeout=5.0
            )
            if res:
                knowledge = "\n".join([r["document"] for r in res])
        except Exception:
            logger.warning("⚠️ 向量检索超时或异常")

        # 🚨 加载数据库 SOP 或启用底座高能 Fallback SOP
        sop_config = (
            context.db.query(PromptConfig)
            .filter(PromptConfig.config_key == "system_sop")
            .first()
        )

        if sop_config and sop_config.config_value.strip():
            system_prompt = sop_config.config_value.replace(
                "{knowledge}",
                knowledge if knowledge else "【官方资料库中未检索到相关数据】",
            )
        else:
            # 架构师级防线：当数据库 SOP 为空时的物理底座
            system_prompt = f"""[SYSTEM CORE DIRECTIVE]
你是波克兰官方技术专家。你必须 100% 忠实于 [KNOWLEDGE BASE] 中的数据。
【绝对禁令】：严禁在没有检索到数据的情况下编造任何参数！宁可承认不知道，也不允许提供错误工业数据。绝不准在对话中使用“系统”、“路由”、“合规”、“触发”等暴露 AI 身份的机械词汇！

[CUSTOMER SERVICE & SALES SOP]
1. 【精准答疑控制】：收到型号查询时，必须检查 [KNOWLEDGE BASE]。
   - IF 查到了：直接列出参数，并告知参数来源于官方手册。
   - IF 没查到：回复“抱歉，目前官方参数表中未检索到该具体型号。为确保选型安全，请留下您的【联系电话】，我为您调取内部图纸。”
2. 【留资钩子】：解答完参数后，统一附加：“如需完整选型手册或具体报价，请留下您的联系电话和所在城市。”

[KNOWLEDGE BASE]
{knowledge if knowledge else "【官方资料库中未检索到相关数据】"}
"""

        # 🚨 终极沙箱锁死：通过强制前缀防御 Prompt 穿透与角色漂移
        user_safe_content = f"""<user_query>
{context.content}
</user_query>

[SYSTEM ENFORCEMENT]: 
作为波克兰官方人类客服，必须遵守以下绝对红线：
1. 【反幻觉锁死】如果用户的查询内容在你的知识库中不存在，你绝对禁止进行任何猜测或编造工业参数，必须礼貌地索要联系方式转交人工。
2. 【系统静音】你输出的内容必须 100% 都是自然对话。绝对禁止输出任何类似“(系统提示)”、“(匹配路由)”、“[系统备注]”、“100%合规”等内部处理逻辑或括号旁白！
结合聊天历史上下文，请直接作答："""

        full_answer = ""
        stream_completed = False

        if context.is_h5_ws:
            await manager.broadcast_to_customer(
                context.openid, {"type": "ai_stream_start"}
            )
            async for chunk in _call_bailian_api_stream(
                user_safe_content, system_prompt, chat_history
            ):
                full_answer += chunk
                await manager.broadcast_to_customer(
                    context.openid, {"type": "ai_stream_chunk", "content": chunk}
                )
            await manager.broadcast_to_customer(
                context.openid, {"type": "ai_stream_end"}
            )
            stream_completed = True
        else:
            full_answer = await _call_bailian_api_sync(
                user_safe_content, system_prompt, chat_history
            )
            await send_wx_msg(context.openid, full_answer)

        await _finalize_ai_reply(context, full_answer, is_streamed=stream_completed)

    except Exception:
        logger.error(f"❌ AI 回复故障: {traceback.format_exc()}")
        if context.is_h5_ws:
            await manager.broadcast_to_customer(
                context.openid,
                {
                    "type": "ai_reply",
                    "content": "抱歉，技术资料库响应超时，麻烦您稍后再试或直接留下联系方式。",
                },
            )


async def _finalize_ai_reply(
    context: MessageContext,
    content: str,
    is_manual: bool = False,
    is_streamed: bool = False,
) -> None:
    from ..api.wechat import save_message
    from ..api.service import manager

    await save_message(context.db, context.session.id, MessageSender.AI.value, content)

    if is_manual:
        context.session.status = SessionStatus.PENDING
        context.db.commit()

    msg_obj = {
        "id": f"msg_ai_{time.time()}",
        "sender": "ai",
        "content": content,
        "created_at": datetime.now().isoformat(),
        "session_id": str(context.session.id),
    }
    await manager.broadcast_to_agents({"type": "new_message", "data": msg_obj})
    await manager.broadcast_to_agents(
        {
            "type": "session_update",
            "data": {
                "id": context.session.id,
                "last_message": content[:50],
                "status": context.session.status.value,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
    )

    if context.is_h5_ws and not is_streamed:
        await manager.broadcast_to_customer(
            context.openid, {"type": "ai_reply", "content": content}
        )


async def _call_bailian_api_stream(
    question: str, system_prompt: str, chat_history: List[Dict[str, str]]
) -> AsyncGenerator[str, None]:
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    payload = {
        "model": settings.PRIMARY_CHAT_MODEL,
        "messages": messages,
        # 🚨 架构师微调：降低温度至 0.1，彻底扼杀大模型的发散性发散与幻觉
        "temperature": 0.1,
        "stream": True,
    }
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST", url, headers=headers, json=payload, timeout=60.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            chunk = (
                                data["choices"][0].get("delta", {}).get("content", "")
                            )
                            if chunk:
                                yield chunk
                        except:
                            continue
        except Exception:
            yield "【系统】资料库引擎响应暂时中断，请重试。"


async def _call_bailian_api_sync(
    question: str, system_prompt: str, chat_history: List[Dict[str, str]]
) -> str:
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": question})

    payload = {
        "model": settings.PRIMARY_CHAT_MODEL,
        "messages": messages,
        # 🚨 架构师微调：降低温度至 0.1
        "temperature": 0.1,
    }
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(url, headers=headers, json=payload, timeout=30.0)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        except Exception:
            return "资料库响应超时，请尝试人工介入。"
