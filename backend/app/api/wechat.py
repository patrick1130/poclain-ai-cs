import hashlib
import time
import asyncio
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

# Redis连接
redis_client = redis.from_url(settings.REDIS_URL)


# ==========================================
# 【核心修复】三重绝对防御 Token 调度器
# ==========================================
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
        # 如果是测试账号，直接阻断，防止抛出异常中断本地业务流
        if "your_test" in settings.WX_APPID:
            logger.warning("⚠️ 检测到当前处于测试占位配置，跳过微信官方 Token 请求")
            return "mock_token"

        # 第一层检查 (无锁极速读取，应对 99.9% 的常规流量)
        cache_token = redis_client.get("wx_access_token")
        if cache_token:
            return cache_token.decode("utf-8")

        # 发现 Token 过期或缺失，进入防御阵地
        async with self._lock:
            # 双重检查锁定 (Double-Checked Locking)：防止排队等待的协程在锁释放后重复请求
            cache_token = redis_client.get("wx_access_token")
            if cache_token:
                logger.info("🔐 协程在锁内复用了其他协程刚拉取的 Token")
                return cache_token.decode("utf-8")

            # 防线一：绝对冷却时间 (60秒内严禁重复发起网络 I/O)
            now = time.time()
            if now - self._last_fetch_time < 60:
                logger.error("🛡️ 触发 60 秒绝对冷却防线！拒绝异常并发重试。")
                return "mock_token"

            # 防线二：分布式每日硬性配额锁 (每日上限 50 次)
            today_str = datetime.now().strftime("%Y%m%d")
            quota_key = f"wx_token_daily_quota_{today_str}"
            current_count = int(redis_client.get(quota_key) or 0)

            if current_count >= 50:
                logger.critical(
                    f"🚨 触发每日硬性配额防线！今日已请求 {current_count} 次，强行物理熔断！"
                )
                return "mock_token"

            # 突破所有防线，执行真实的向外网关请求
            logger.info("🌐 正在向微信官方网关发起真实的 Token 获取请求...")
            url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={settings.WX_APPID}&secret={settings.WX_APPSECRET}"

            try:
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=5.0)
                    res_data = res.json()

                    if "access_token" in res_data:
                        access_token = res_data["access_token"]
                        # 提前 5 分钟 (300秒) 过期，留出平滑续期的灰度时间
                        redis_client.setex(
                            "wx_access_token",
                            res_data["expires_in"] - 300,
                            access_token,
                        )
                        # 更新冷却时间和计步器
                        self._last_fetch_time = time.time()
                        redis_client.incr(quota_key)
                        redis_client.expire(quota_key, 86400)  # 确保存活一天即可

                        logger.info(
                            f"✅ 成功获取微信官方 Token (今日累计消耗配额: {current_count + 1}/50)"
                        )
                        return access_token
                    else:
                        logger.error(f"❌ 微信官方返回异常报文: {res_data}")
                        # 即使失败也必须更新冷却时间，防止循环报错
                        self._last_fetch_time = time.time()
                        return "mock_token"
            except Exception as e:
                logger.error(f"🔌 请求微信 Token 发生网络异常: {e}")
                self._last_fetch_time = time.time()
                return "mock_token"


# 初始化全局单例调度器
token_manager = WeChatTokenManager()


@router.get("")
async def wx_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """
    处理微信公众号开发者配置的服务器 URL 验证
    """
    tmp_list = sorted([settings.WX_TOKEN, timestamp, nonce])
    tmp_str = "".join(tmp_list).encode("utf-8")
    tmp_sign = hashlib.sha1(tmp_str).hexdigest()
    if tmp_sign == signature:
        return PlainTextResponse(echostr)
    else:
        raise HTTPException(status_code=403, detail="Invalid signature")


@router.post("")
async def wx_receive_msg(request: Request, background_tasks: BackgroundTasks):
    """
    接收微信用户发送的消息 - 物理坐标：/api/v1/wechat
    """
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

        # 极其重要：把所有重负载查询、AI推理和人工路由剥离到后台微任务
        # 主线程立即向腾讯服务器返回 success，彻底掐断 5 秒超时炸弹
        background_tasks.add_task(
            bg_process_user_message_wrapper, from_user, content, msg_type
        )
        return PlainTextResponse("success")
    except Exception as e:
        logger.error(f"解析微信报文失败: {e}")
        return PlainTextResponse("success")


async def bg_process_user_message_wrapper(from_user: str, content: str, msg_type: str):
    """
    剥离出来的后台异步执行器
    """
    db = SessionLocal()
    try:
        await process_user_message(db, from_user, content, msg_type)
    except Exception as e:
        logger.error(f"❌ 后台处理逻辑报错: {e}")
    finally:
        db.close()


async def send_wx_msg(openid: str, content: str) -> None:
    """
    向真实微信网关发送客服消息
    """
    # 启用具备三重防御的单例获取 Token
    access_token = await token_manager.get_access_token()

    if access_token == "mock_token":
        logger.warning(
            f"🚫 [防御降级] Token 引擎处于锁定或演示状态，跳过发送: {content}"
        )
        return

    url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={access_token}"
    req_data = {"touser": openid, "msgtype": "text", "text": {"content": content}}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=req_data, timeout=5.0)
            res_data = res.json()
            if res_data.get("errcode") == 0:
                logger.info("📤 客服消息已成功投递至微信官方网关")
            else:
                logger.error(f"⚠️ 微信官方拒绝投递客服消息: {res_data}")
    except Exception as e:
        logger.error(f"向微信网关发送网络请求失败: {e}")


# ==========================================
# 存根函数 (保持不变)
# ==========================================


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
