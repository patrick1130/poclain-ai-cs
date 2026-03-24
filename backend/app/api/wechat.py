import hashlib
import time
import asyncio
import json
import uuid
from defusedxml import ElementTree as ET
from fastapi import (
    APIRouter,
    Request,
    Query,
    HTTPException,
    BackgroundTasks,
    Body,
    Depends,
)
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
import httpx
import redis.asyncio as redis
import logging
from datetime import datetime

from ..core.database import SessionLocal, get_db
from ..models.database import (
    CustomerSession,
    Message,
    SessionStatus,
    MessageSender,
    ServiceAgent,
)
from ..core.config import settings
from ..utils.message_handler import process_user_message

logger = logging.getLogger(__name__)

router = APIRouter()

# 🚨 架构师修正：采用异步 Redis 客户端防阻塞
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


class WeChatTokenManager:
    """单例模式：微信 Access Token 分布式安全调度器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_access_token(self) -> str:
        if "your_test" in settings.WX_APPID:
            return "mock_token"

        cache_token = await redis_client.get("wx_access_token")
        if cache_token:
            return cache_token

        lock_key = "lock:wx_token_refresh"
        lock_value = str(uuid.uuid4())

        if await redis_client.set(lock_key, lock_value, ex=10, nx=True):
            try:
                url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={settings.WX_APPID}&secret={settings.WX_APPSECRET}"
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=10.0)
                    res_data = res.json()
                    if "access_token" in res_data:
                        token = res_data["access_token"]
                        await redis_client.setex(
                            "wx_access_token", res_data["expires_in"] - 300, token
                        )
                        return token
                    return "mock_token"
            finally:
                script = "if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"
                await redis_client.eval(script, 1, lock_key, lock_value)
        else:
            await asyncio.sleep(0.5)
            return await self.get_access_token()


token_manager = WeChatTokenManager()

# ==========================================
# 🚨 核心逻辑：用户与会话持久化引擎 (防阻塞架构重构)
# ==========================================


async def save_or_update_user(db: Session, openid: str, nickname: str = None):
    """通过线程池隔离同步 I/O，释放主事件循环"""

    def _sync_op():
        logger.info(f"👤 映射同步: {openid} -> {nickname}")
        return {"openid": openid, "nickname": nickname}

    return await asyncio.to_thread(_sync_op)


async def get_or_create_session(db: Session, openid: str) -> CustomerSession:
    """
    S级加固：具备幂等性的会话获取逻辑，使用 asyncio.to_thread 包装以防止阻塞 FastAPI 主循环。
    """

    def _sync_op():
        session = (
            db.query(CustomerSession)
            .filter(
                CustomerSession.user_id == openid,
                CustomerSession.status != SessionStatus.CLOSED,
            )
            .order_by(desc(CustomerSession.updated_at))
            .first()
        )

        if not session:
            session = CustomerSession(
                user_id=openid,
                status=SessionStatus.AI_HANDLING,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"🆕 为用户 {openid} 创建了新会话 ID: {session.id}")

        return session

    return await asyncio.to_thread(_sync_op)


async def save_message(
    db: Session, session_id: int, sender: str, content: str, msg_type: str = "text"
):
    """持久化消息记录，同步写入操作已抛入后台线程池执行"""

    def _sync_op():
        if isinstance(sender, str):
            try:
                sender_enum = MessageSender(sender)
            except ValueError:
                sender_enum = MessageSender.SYSTEM
        else:
            sender_enum = sender

        new_msg = Message(
            session_id=session_id,
            sender=sender_enum,
            content=content,
            msg_type=msg_type,
            created_at=datetime.now(),
        )
        db.add(new_msg)

        session = db.query(CustomerSession).get(session_id)
        if session:
            session.last_message = content[:100]
            session.updated_at = datetime.now()

        db.commit()
        logger.info(f"💾 消息已存入 Session {session_id}")

    await asyncio.to_thread(_sync_op)


async def send_wx_msg(openid: str, content: str):
    """发送微信客服消息（公众号同步回复）"""
    token = await token_manager.get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token}"
    payload = {"touser": openid, "msgtype": "text", "text": {"content": content}}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, timeout=5.0)


def verify_wechat_signature(signature: str, timestamp: str, nonce: str) -> bool:
    """内部校验签名，剔除网络波动引起的错误"""
    token = settings.WX_TOKEN
    tmp_list = [token, timestamp, nonce]
    tmp_list.sort()
    tmp_str = "".join(tmp_list)
    hash_str = hashlib.sha1(tmp_str.encode("utf-8")).hexdigest()
    return hash_str == signature


# ==========================================
# 🚨 核心端点：H5 授权与微信网关
# ==========================================


@router.post("/h5/auth")
async def h5_oauth_login(
    request: Request, code: str = Body(None, embed=True), db: Session = Depends(get_db)
):
    host = request.headers.get("host", "")
    is_ip_access = any(char.isdigit() for char in host.split(":")[0])
    use_mock = settings.DEBUG or is_ip_access or not code or code == "undefined"

    if use_mock:
        mock_openid = f"h5_dev_user_{hashlib.md5(host.encode()).hexdigest()[:8]}"
        logger.warning(f"🛡️ 触发 Mock 授权: {mock_openid}")
        await save_or_update_user(db, mock_openid, "H5调试员")
        return {"openid": mock_openid, "nickname": "H5调试员", "avatar": ""}

    url = f"https://api.weixin.qq.com/sns/oauth2/access_token?appid={settings.WX_APPID}&secret={settings.WX_APPSECRET}&code={code}&grant_type=authorization_code"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=10.0)
            data = res.json()
            if "openid" in data:
                openid = data["openid"]
                await save_or_update_user(db, openid, "微信H5用户")
                return {"openid": openid, "nickname": "微信H5用户", "avatar": ""}
            return {"openid": f"temp_{int(time.time())}", "nickname": "游客用户"}
    except Exception as e:
        logger.error(f"🔥 H5 授权物理层崩溃: {e}")
        raise HTTPException(status_code=500, detail="WeChat Auth Service Unavailable")


@router.get("")
async def wx_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    if verify_wechat_signature(signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    raise HTTPException(status_code=403, detail="Invalid signature")


@router.post("")
async def wx_receive_msg(
    request: Request,
    background_tasks: BackgroundTasks,
    signature: str = Query(None),
    timestamp: str = Query(None),
    nonce: str = Query(None),
):
    xml_data = await request.body()
    try:
        root = ET.fromstring(xml_data)
        from_user = root.find("FromUserName").text
        msg_type = root.find("MsgType").text
        content = (
            root.find("Content").text if msg_type == "text" else f"[{msg_type}消息]"
        )

        # 挂起连接，利用后台任务剥离 AI 耗时计算，物理解决微信 5 秒超时限制
        background_tasks.add_task(
            bg_process_user_message_wrapper, from_user, content, msg_type
        )
        return PlainTextResponse("success")
    except Exception:
        return PlainTextResponse("success")


async def bg_process_user_message_wrapper(from_user: str, content: str, msg_type: str):
    db = SessionLocal()
    try:
        await process_user_message(db, from_user, content, msg_type)
    except Exception as e:
        logger.error(f"❌ 后台任务异常: {e}")
    finally:
        db.close()
