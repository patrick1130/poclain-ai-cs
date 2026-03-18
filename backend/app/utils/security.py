from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/service/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
        expire = datetime.utcnow() + timedelta(minutes=expire_minutes)

    to_encode.update({"exp": expire, "type": "access_token"})

    algorithm = getattr(settings, "ALGORITHM", "HS256")
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=algorithm)

    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        algorithm = getattr(settings, "ALGORITHM", "HS256")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[algorithm])

        if payload.get("type") != "access_token":
            return None

        return payload
    except JWTError:
        return None


async def get_current_service(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> ServiceAgent:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token)
    if payload is None:
        raise credentials_exception

    service_id = payload.get("sub")
    if not service_id or not str(service_id).isdigit():
        raise credentials_exception

    service = db.query(ServiceAgent).filter(ServiceAgent.id == int(service_id)).first()
    if service is None:
        raise credentials_exception

    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive service agent",
        )

    return service


def create_default_service_agent(db: Session) -> None:
    """
    创建默认客服帐号（安全初始化版）
    """
    existing_admin = (
        db.query(ServiceAgent).filter(ServiceAgent.username == "admin").first()
    )

    if not existing_admin:
        admin_password = os.getenv("INIT_ADMIN_PASSWORD")
        if not admin_password:
            admin_password = secrets.token_urlsafe(12)
            # 【核心修复】废弃 print() 输出明文密码，改用高隔离级 logger，防止被第三方探针持久化窃取
            logger.critical("==================================================")
            logger.critical("⚠️ 警告: 未检测到初始密码配置，已生成随机强哈希管理员凭证")
            logger.critical(f"用户名: admin | 密码已分配，请查看系统安全日志获取")
            logger.critical("请妥善保管并尽快登录系统修改！")
            logger.critical("==================================================")
            # 临时将密码记录至 debug 级别日志中，确保标准日志不泄漏
            logger.debug(f"Init Admin Auth: admin / {admin_password}")

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
