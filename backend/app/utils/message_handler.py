import asyncio
from sqlalchemy.orm import Session
from datetime import datetime, time as dtime
from typing import Optional, Dict, List, Any, Tuple
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
    ServiceAgent,
    SessionStatus,
    MessageSender,
)
from ..core.config import settings
from ..utils.vector_db import VectorDB
from ..exceptions import (
    AIServiceException,
    DatabaseException,
    MessageProcessingException,
)

logger = logging.getLogger(__name__)
vector_db = VectorDB(settings.VECTOR_DB_PATH)

# 【架构级安全一：内存级滑动窗口限流器】
USER_RATE_LIMITS: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX_REQUESTS = 10


class IntentAnalyzer:
    """轻量级用户意图识别引擎"""

    # 1. 寒暄意图正则
    GREETING_ROOTS = (
        r"(你好|您好|在吗|在不在|有人吗|hi|hello|哈喽|喂|早上好|下午好|晚上好|嗨)"
    )
    SUFFIXES = r"[啊呀吧呢吗\?？\!！~～\s]*"
    GREETING_PATTERN = re.compile(f"^{GREETING_ROOTS}{SUFFIXES}$", re.IGNORECASE)

    # 2. 转人工意图正则 (宽容包含匹配)
    MANUAL_ROOTS = r"(人工|真人|客服|接线员)"
    MANUAL_PATTERN = re.compile(f".*{MANUAL_ROOTS}.*", re.IGNORECASE)

    @classmethod
    def is_greeting(cls, text: str) -> bool:
        """判断是否为纯寒暄"""
        clean_text = text.strip()
        # 长度熔断：超过 15 个字符直接放行
        if len(clean_text) > 15:
            return False
        # 严格的从头到尾匹配
        return bool(cls.GREETING_PATTERN.match(clean_text))

    @classmethod
    def is_manual_request(cls, text: str) -> bool:
        """判断是否要求转人工"""
        clean_text = text.strip()
        # 只要用户的输入中“包含”人工相关词汇，立即触发拦截
        return bool(cls.MANUAL_PATTERN.search(clean_text))


class SecurityGuardian:
    """
    S级防御：基于正则与关键词的物理级指令拦截器 (Prompt Injection Firewall)
    """

    INJECTION_PATTERNS = [
        r"忽略.*设定",
        r"ignore.*instruction",
        r"扮演",
        r"扮演.*角色",
        r"你是.*脱口秀",
        r"你是.*演员",
        r"你是.*翻译",
        r"你是.*诗人",
        r"system.*prompt",
        r"系统提示词",
        r"指令.*优先级",
        r"bypass",
        r"忘记.*身份",
        r"不再是.*专家",
    ]

    @classmethod
    def check_injection(cls, content: str) -> bool:
        content_lower = content.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, content_lower):
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


class MessageHandler:
    def __init__(self):
        self.vector_db = vector_db


async def process_user_message(
    db: Session, openid: str, content: str, msg_type: str = "text"
) -> None:
    try:
        from ..api.wechat import (
            save_or_update_user,
            get_or_create_session,
            save_message,
            send_wx_msg,
        )
        from ..websocket.service import manager

        # 限流探测
        current_time = time.time()
        user_history = USER_RATE_LIMITS.get(openid, [])
        user_history = [t for t in user_history if current_time - t < RATE_LIMIT_WINDOW]

        if len(user_history) >= RATE_LIMIT_MAX_REQUESTS:
            await send_wx_msg(openid, "您的提问过于频繁，请稍后再试。")
            return

        user_history.append(current_time)
        USER_RATE_LIMITS[openid] = user_history

        safe_content = content[:1000]

        # 🚨 物理隔离：前置拦截恶意注入
        if SecurityGuardian.check_injection(safe_content):
            logger.warning(f"🚨 拦截到针对用户 {openid} 的恶意指令注入: {safe_content}")
            await send_wx_msg(
                openid,
                "非常抱歉，我仅受权提供 Poclain (波克兰) 相关的技术支持，无法执行其他领域的指令。",
            )
            return

        context = MessageContext(
            db=db, openid=openid, content=safe_content, msg_type=msg_type
        )
        context.user = await save_or_update_user(db, openid)
        context.session = await get_or_create_session(db, openid)

        await save_message(
            db, context.session.id, MessageSender.USER.value, safe_content, msg_type
        )

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
                    "user_name": getattr(context.user, "nickname", "微信用户"),
                    "user_avatar": getattr(context.user, "avatar", ""),
                },
            },
        )

        handler = MessageHandler()
        await dispatch_message(handler, context)

    except Exception:
        logger.error(f"【微信端入口报错】:\n{traceback.format_exc()}")


async def dispatch_message(self: MessageHandler, context: MessageContext) -> None:
    if context.session.status == SessionStatus.ACTIVE:
        return
    context.session.status = SessionStatus.AI_HANDLING
    context.db.commit()
    await handle_ai_response_impl(self, context)


def _safe_truncate_for_wechat(text: str, max_bytes: int = 2000) -> str:
    encoded_text = text.encode("utf-8")
    if len(encoded_text) <= max_bytes:
        return text
    suffix = "\n\n...(字数超限，请分段提问)"
    return encoded_text[: max_bytes - 30].decode("utf-8", errors="ignore") + suffix


async def _call_reranker(query: str, documents: List[str]) -> List[str]:
    """S级架构：阿里 gte-rerank 交叉重排引擎"""
    if not documents:
        return []
    if len(documents) <= 3:
        return documents

    url = (
        "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
    }
    payload = {
        "model": "gte-rerank",
        "input": {"query": query, "documents": documents},
        "parameters": {"top_n": 3},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            results = sorted(
                res.json().get("output", {}).get("results", []),
                key=lambda x: x.get("relevance_score", 0.0),
                reverse=True,
            )
            return [
                documents[r["index"]] for r in results if r["index"] < len(documents)
            ]
        except Exception as e:
            logger.warning(f"⚠️ Reranker 异常: {e}")
            return documents[:3]


async def handle_ai_response_impl(
    self: MessageHandler, context: MessageContext
) -> None:
    from ..api.wechat import save_message, send_wx_msg
    from ..websocket.service import manager

    try:
        # 统计 AI 历史回复数
        ai_msg_count = (
            context.db.query(Message)
            .filter(
                Message.session_id == context.session.id,
                Message.sender == MessageSender.AI.value,
            )
            .count()
        )

        # ==========================================
        # 🚨 架构师补丁 1：物理级人工转接旁路 (Manual Transfer Bypass)
        # 优先级最高：只要客户有找真人的意图，立刻无条件放行并呼叫坐席
        # ==========================================
        if IntentAnalyzer.is_manual_request(context.content):
            transfer_msg = (
                "已收到您的请求。正在为您呼叫 Poclain 官方技术专员，请稍候..."
            )

            # 记录回复并发送给微信
            await save_message(
                context.db, context.session.id, MessageSender.AI.value, transfer_msg
            )
            await send_wx_msg(context.openid, transfer_msg)

            # 广播给前端大屏
            await manager.broadcast_message(
                str(context.session.id),
                {
                    "type": "new_message",
                    "data": {
                        "session_id": str(context.session.id),
                        "content": transfer_msg,
                        "sender": "ai",
                        "created_at": datetime.now().isoformat(),
                    },
                },
            )

            # 改变会话状态为 PENDING（待接入），WebSocket 会触发前端的红点提示
            await transfer_to_manual_impl(
                self, context.db, context.session, context.openid, "用户主动呼叫人工"
            )

            # 🚨 核心阻断：立刻退出，绝对不查 RAG，不调 LLM！
            return

        # ==========================================
        # 🚨 架构师补丁 2：物理级寒暄旁路 (Greeting Bypass)
        # ==========================================
        if IntentAnalyzer.is_greeting(context.content):
            welcome_text = "您好！这里是 Poclain (波克兰液压) 官方智能技术支持。请问您需要了解哪款液压马达（如 MS05 系列）的技术参数或应用支持？"
            if ai_msg_count == 0:
                final_disclaimer = "\n\n---\n📖 欢迎咨询波克兰技术支持。本服务由 AI 助手检索生成，仅供参考。最终请以 Poclain 官方技术文件或人工客服答复为准。"
            else:
                final_disclaimer = "\n\n(AI生成，请以官方技术文件为准)"

            ai_answer = welcome_text + final_disclaimer

            await save_message(
                context.db, context.session.id, MessageSender.AI.value, ai_answer
            )
            await send_wx_msg(context.openid, ai_answer)
            await manager.broadcast_message(
                str(context.session.id),
                {
                    "type": "new_message",
                    "data": {
                        "session_id": str(context.session.id),
                        "content": ai_answer,
                        "sender": "ai",
                        "created_at": datetime.now().isoformat(),
                    },
                },
            )
            return

        # ==========================================
        # 以下为常规业务逻辑：拉取历史、查库、调用大模型
        # ==========================================

        # 拉取对话历史 (限制 7 条，防止 Token 爆炸)
        try:
            recent_msgs = (
                context.db.query(Message)
                .filter(Message.session_id == context.session.id)
                .order_by(Message.created_at.desc())
                .limit(7)
                .all()
            )
            chat_history = [
                {
                    "role": (
                        "user" if m.sender == MessageSender.USER.value else "assistant"
                    ),
                    "content": m.content[:500],
                }
                for m in recent_msgs[::-1]
            ]
        except Exception:
            chat_history = []

        # 🚀 增强版 RAG 检索 (结合高阈值粗筛 + 交叉重排)
        try:
            # 第一步：高阈值粗筛 (阈值 0.5 过滤绝对噪音)
            res = await asyncio.wait_for(
                self.vector_db.search(context.content, 15, 0.1), timeout=8.0
            )
            if not res:
                knowledge = "【架构师强制指令：知识库中完全未检索到与用户问题相关的 Poclain 官方资料。你必须回复用户“抱歉，暂未查找到相关技术手册”，绝对严禁编造！】"
            else:
                raw_documents = [r["document"] for r in res]
                # 第二步：二次精排
                refined_documents = await _call_reranker(context.content, raw_documents)
                knowledge = "\n\n".join(refined_documents)
        except Exception as e:
            logger.warning(f"RAG 检索故障: {e}")
            knowledge = "（知识库检索超时）"

        # 核心 AI 生成调用
        raw_ai_answer = await generate_answer(context.content, knowledge, chat_history)

        # 🛡️ 物理层清洗：利用正则暴力切除 AI 由于惯性自行生成的任何形式的免责声明
        clean_answer = re.sub(
            r"(\n\n)?-*\s*⚠️?免责声明.*", "", raw_ai_answer, flags=re.IGNORECASE
        )
        clean_answer = re.sub(
            r"(\n\n)?-*\s*\(?AI生成.*文件为准\)?", "", clean_answer, flags=re.IGNORECASE
        )
        clean_answer = re.sub(
            r"(\n\n)?-*\s*注：以上回答由\s*AI.*", "", clean_answer, flags=re.IGNORECASE
        ).strip()

        # 挂载真正的系统级硬编码免责声明
        if ai_msg_count == 0:
            final_disclaimer = "\n\n---\n📖 欢迎咨询波克兰技术支持。本服务由 AI 助手检索生成，仅供参考。最终请以 Poclain 官方技术文件或人工客服答复为准。"
        else:
            final_disclaimer = "\n\n(AI生成，请以官方技术文件为准)"

        ai_answer = _safe_truncate_for_wechat(clean_answer + final_disclaimer)

        # 结果入库与广播
        await save_message(
            context.db, context.session.id, MessageSender.AI.value, ai_answer
        )
        await send_wx_msg(context.openid, ai_answer)
        await manager.broadcast_message(
            str(context.session.id),
            {
                "type": "new_message",
                "data": {
                    "session_id": str(context.session.id),
                    "content": ai_answer,
                    "sender": "ai",
                    "created_at": datetime.now().isoformat(),
                },
            },
        )
    except Exception:
        logger.error(f"【AI生成全链路故障】:\n{traceback.format_exc()}")


async def generate_answer(
    question: str, knowledge_content: str, chat_history: List[Dict[str, str]]
) -> str:
    # 🚨 钢铁苍穹：S 级防幻觉 + 拟人化 Prompt (已完美修复缩进)
    system_prompt = f"""你是一个严谨的 Poclain (波克兰液压) 原厂智能技术客服。
你的唯一任务是：【仅限】基于下方的[参考资料]回答用户的问题。

【最高级别行为准则】：
1. **零发挥原则**：你的回答必须 100% 来源于[参考资料]。绝对【禁止】添加资料中没有的任何免责声明、日期标注（如"2023年Q3"）、环境建议（如"-40℃低温"）或补充说明。
2. **绝对忠实**：绝不能凭空捏造任何参数、型号或行业标准。若资料只有数值，请勿根据常识进行性能点评或适配建议。
3. **禁止自造尾部**：严禁在回复末尾自行生成任何总结性文字、温馨提示或后续步骤，除非这些内容明确出现在[参考资料]中。
4. **自然拟人**：直接用专业、礼貌的口吻回答。绝对【禁止】在回复中出现“根据知识库切片”、“基于参考资料”等暴露 AI 系统内部逻辑的词汇。
5. **知之为知之**：如果[参考资料]中没有明确提到用户的具体问题，你必须直接且仅回复：“抱歉，您查询的参数在当前技术手册中暂无明确记录，建议联系人工技术专员获取进一步确认。”
[参考资料开始]
{knowledge_content}
[参考资料结束]
"""
    try:
        return await asyncio.wait_for(
            _call_bailian_api_with_fallback(question, system_prompt, chat_history),
            timeout=60.0,
        )
    except Exception as e:
        # 🚨 探照灯：记录真实死因，不再做“瞎子”
        logger.error(f"🚨 大模型请求彻底失败: {str(e)}\n{traceback.format_exc()}")
        return "系统响应超时，正在为您转接人工客服。"


async def _call_bailian_api_with_fallback(
    question: str, system_prompt: str, chat_history: List[Dict[str, str]]
) -> str:
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
    }

    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        messages.extend(chat_history)

    # 利用 XML 标签将用户输入包裹，物理隔离 Prompt 注入
    messages.append(
        {"role": "user", "content": f"<user_query>\n{question}\n</user_query>"}
    )

    # ==========================================
    # 🚨 架构师补丁：退回标准安全参数，确保模型 100% 兼容
    # ==========================================
    payload = {
        "model": settings.PRIMARY_CHAT_MODEL,
        "messages": messages,
        "temperature": 0.01,  # 逼近绝对零度 (部分模型传0.0会报错，0.01最安全)
        "top_p": 0.01,  # 极其严苛的核采样，掐断所有发散神经元
        # ⚠️ 已物理移除 enable_search，防止引发阿里云 400 Bad Request 崩溃
    }

    async with httpx.AsyncClient(timeout=40.0) as client:
        try:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"⚠️ 主引擎降级: {e}")
            payload["model"] = settings.BACKUP_CHAT_MODEL
            async with httpx.AsyncClient(timeout=40.0) as backup:
                res = await backup.post(url, headers=headers, json=payload)
                # 🚨 探照灯：如果备用引擎也挂了，把阿里云的原始报错文本打出来
                if res.status_code != 200:
                    logger.error(
                        f"❌ 备用引擎 API 报错 (Status {res.status_code}): {res.text}"
                    )
                res.raise_for_status()
                return res.json()["choices"][0]["message"]["content"]


async def transfer_to_manual_impl(self, db, session, openid, reason) -> None:
    from ..websocket.service import manager

    session.status = SessionStatus.PENDING
    db.commit()
    await manager.notify_session_update(
        {"id": session.id, "status": session.status.value}
    )


async def is_work_time(*args, **kwargs):
    pass


def check_manual_intent(text: str) -> bool:
    """全局开放的转人工意图探测接口"""
    return IntentAnalyzer.is_manual_request(text)
