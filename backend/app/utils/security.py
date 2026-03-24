from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
import secrets
import logging

from app.core.config import settings
from app.core.database import get_db
from app.models.database import ServiceAgent

logger = logging.getLogger(__name__)

# 定义 OAuth2 路由
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/service/login")


# ==========================================
# 🚨 Bcrypt 密码学引擎 (现代原生版)
# ==========================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码一致性"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"密码校验引擎故障: {e}")
        return False


def get_password_hash(password: str) -> str:
    """生成安全哈希"""
    # 物理截断：bcrypt 强制要求密码在 72 字节以内，超过部分将被忽略
    safe_password = password[:72]
    pwd_bytes = safe_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_pwd = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_pwd.decode("utf-8")


# ==========================================
# JWT 令牌引擎
# ==========================================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """签发 JWT"""
    to_encode = data.copy()

    # 🚨 架构师修正 1：强制将 sub 转换为字符串
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    # 🚨 核心修正 2：使用带时区感知的绝对 UTC 时间 (防止 CST/UTC 8小时偏差)
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        # 默认 60 分钟过期
        expire_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
        expire = now + timedelta(minutes=expire_minutes)

    # iat (签发时间) 和 exp (过期时间) 必须使用相同的时区基准
    to_encode.update({"exp": expire, "iat": now, "type": "access_token"})

    algorithm = getattr(settings, "ALGORITHM", "HS256")
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=algorithm)

    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """物理校验并解码令牌"""
    try:
        algorithm = getattr(settings, "ALGORITHM", "HS256")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[algorithm])

        # 安全加固：校验令牌类型
        if payload.get("type") != "access_token":
            logger.warning("🚫 尝试使用非法类型的 JWT 令牌")
            return None

        return payload
    except JWTError as e:
        logger.error(f"JWT 签名验证失败: {e}")
        return None


async def get_current_service(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> ServiceAgent:
    """FastAPI 依赖项：从头信息获取当前坐席"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token)
    if payload is None:
        raise credentials_exception

    service_id = payload.get("sub")
    if not service_id:
        raise credentials_exception

    service = db.query(ServiceAgent).filter(ServiceAgent.id == int(service_id)).first()
    if service is None:
        raise credentials_exception

    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account inactive",
        )

    return service


def create_default_service_agent(db: Session) -> None:
    """初始化默认管理员"""
    existing_admin = (
        db.query(ServiceAgent).filter(ServiceAgent.username == "admin").first()
    )

    if not existing_admin:
        admin_password = getattr(settings, "ADMIN_PASSWORD", "PoclainAdmin2026!")

        logger.critical("==================================================")
        logger.critical("✅ 初始化：正在创建默认坐席管理员...")
        logger.critical(f"账号: admin")
        logger.critical("请通过后台及时修改此初始密码。")
        logger.critical("==================================================")

        default_service = ServiceAgent(
            username="admin",
            name="系统管理员",
            password_hash=get_password_hash(admin_password),
            email="admin@example.com",
            phone="13800138000",
            status="offline",
            is_active=True,
            role="admin",
        )
        db.add(default_service)
        db.commit()
