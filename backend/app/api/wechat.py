import hashlib
import time
import asyncio
import json
from defusedxml import ElementTree as ET
from fastapi import APIRouter, Request, Query, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import httpx
import redis
import logging
from datetime import datetime

from ..core.config import settings
from ..core.database import SessionLocal
from ..models.database import CustomerSession, Message, SessionStatus, MessageSender
from ..utils.message_handler import process_user_message

logger = logging.getLogger(__name__)
router = APIRouter()

redis_client = redis.from_url(settings.REDIS_URL)


class WeChatTokenManager:
    """
    单例模式：微信 Access Token 生产级安全调度器
    """

    _instance = None
    _lock = asyncio.Lock()
    _last_fetch_time = 0.0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_access_token(self) -> str:
        if "your_test" in settings.WX_APPID:
            logger.warning("⚠️ 检测到当前处于测试占位配置，跳过微信官方 Token 请求")
            return "mock_token"

        cache_token = redis_client.get("wx_access_token")
        if cache_token:
            return cache_token.decode("utf-8")

        async with self._lock:
            cache_token = redis_client.get("wx_access_token")
            if cache_token:
                logger.info("🔐 协程在锁内复用了其他协程刚拉取的 Token")
                return cache_token.decode("utf-8")

            now = time.time()
            if now - self._last_fetch_time < 60:
                logger.error("🛡️ 触发 60 秒绝对冷却防线！拒绝异常并发重试。")
                return "mock_token"

            today_str = datetime.now().strftime("%Y%m%d")
            quota_key = f"wx_token_daily_quota_{today_str}"
            current_count = int(redis_client.get(quota_key) or 0)

            if current_count >= 50:
                logger.critical(
                    f"🚨 触发每日硬性配额防线！今日已请求 {current_count} 次，强行物理熔断！"
                )
                return "mock_token"

            logger.info("🌐 正在向微信官方网关发起真实的 Token 获取请求...")
            url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={settings.WX_APPID}&secret={settings.WX_APPSECRET}"

            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=5.0)
                    res_data = res.json()

                    if "access_token" in res_data:
                        access_token = res_data["access_token"]
                        redis_client.setex(
                            "wx_access_token",
                            res_data["expires_in"] - 300,
                            access_token,
                        )
                        self._last_fetch_time = time.time()
                        redis_client.incr(quota_key)
                        redis_client.expire(quota_key, 86400)

                        logger.info(
                            f"✅ 成功获取微信官方 Token (今日累计消耗配额: {current_count + 1}/50)"
                        )
                        return access_token
                    else:
                        logger.error(f"❌ 微信官方返回异常报文: {res_data}")
                        self._last_fetch_time = time.time()
                        return "mock_token"
            except Exception as e:
                logger.error(f"🔌 请求微信 Token 发生网络异常: {e}")
                self._last_fetch_time = time.time()
                return "mock_token"


token_manager = WeChatTokenManager()


def verify_wechat_signature(signature: str, timestamp: str, nonce: str) -> bool:
    """【S级架构防线】抽离独立的 SHA1 签名校验器，用于拦截公网伪造请求"""
    if not signature or not timestamp or not nonce:
        return False
    tmp_list = sorted([settings.WX_TOKEN, timestamp, nonce])
    tmp_str = "".join(tmp_list).encode("utf-8")
    tmp_sign = hashlib.sha1(tmp_str).hexdigest()
    return tmp_sign == signature


@router.get("")
async def wx_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    if verify_wechat_signature(signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    else:
        logger.warning(f"🚨 [GET] 拦截到非法的微信签名校验请求")
        raise HTTPException(status_code=403, detail="Invalid signature")


@router.post("")
async def wx_receive_msg(
    request: Request,
    background_tasks: BackgroundTasks,
    signature: str = Query(None),
    timestamp: str = Query(None),
    nonce: str = Query(None),
):
    """
    接收微信用户发送的消息 - 物理坐标：/api/v1/wechat
    """
    # 【核心安全修复】强制拦截未经签名的 POST 报文，彻底封死直接对公网暴露的后门
    if not verify_wechat_signature(signature, timestamp, nonce):
        logger.critical("🚨 [POST] 遭受恶意伪造的 XML 注入攻击！签名不符，已物理切断。")
        raise HTTPException(status_code=403, detail="Forbidden: Signature Tampered")

    xml_data = await request.body()
    try:
        root = ET.fromstring(xml_data)
        from_user = root.find("FromUserName").text
        msg_type = root.find("MsgType").text

        if msg_type == "text":
            content = root.find("Content").text
        elif msg_type == "event":
            event_type = root.find("Event").text
            content = (
                "[用户关注]" if event_type == "subscribe" else f"[事件: {event_type}]"
            )
        else:
            content = f"[{msg_type}消息]"

        logger.info(f"📥 收到真实微信消息: 来自={from_user}, 内容={content}")

        background_tasks.add_task(
            bg_process_user_message_wrapper, from_user, content, msg_type
        )
        return PlainTextResponse("success")
    except Exception as e:
        logger.error(f"解析微信报文失败: {e}")
        return PlainTextResponse("success")


async def bg_process_user_message_wrapper(from_user: str, content: str, msg_type: str):
    db = SessionLocal()
    try:
        await process_user_message(db, from_user, content, msg_type)
    except Exception as e:
        logger.error(f"❌ 后台处理逻辑报错: {e}")
    finally:
        db.close()


async def send_wx_msg(openid: str, content: str) -> None:
    access_token = await token_manager.get_access_token()

    if access_token == "mock_token":
        logger.warning(
            f"🚫 [防御降级] Token 引擎处于锁定或演示状态，跳过发送: {content}"
        )
        return

    url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={access_token}"
    req_data = {"touser": openid, "msgtype": "text", "text": {"content": content}}

    payload = json.dumps(req_data, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, content=payload, headers=headers, timeout=5.0)
            res_data = res.json()
            if res_data.get("errcode") == 0:
                logger.info("📤 客服消息已成功投递至微信官方网关 (UTF-8强制封包)")
            else:
                logger.error(f"⚠️ 微信官方拒绝投递客服消息: {res_data}")
    except Exception as e:
        logger.error(f"向微信网关发送网络请求失败: {e}")


async def save_or_update_user(
    db: Session, openid: str, nickname: str = None, avatar: str = None
):
    return None


async def get_or_create_session(db: Session, openid: str):
    session = (
        db.query(CustomerSession)
        .filter(
            CustomerSession.user_id == openid,
            CustomerSession.status.in_(
                [SessionStatus.PENDING, SessionStatus.ACTIVE, SessionStatus.AI_HANDLING]
            ),
        )
        .order_by(CustomerSession.created_at.desc())
        .first()
    )
    if not session:
        session = CustomerSession(user_id=openid, status=SessionStatus.AI_HANDLING)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


async def save_message(
    db: Session, session_id: int, sender_type: str, content: str, msg_type: str = "text"
):
    sender_enum = MessageSender(sender_type)
    message = Message(
        session_id=session_id,
        sender=sender_enum,
        content=content,
        is_read=False if sender_enum == MessageSender.USER else True,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
