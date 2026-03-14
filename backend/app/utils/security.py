from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
import secrets

from app.core.config import settings
from app.core.database import get_db
from app.models.database import ServiceAgent

# 密碼加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2密碼Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/service/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    # 設置默認超時時間
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # 如果 settings 中沒有配置，提供默認 60 分鐘以防報錯
        expire_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
        expire = datetime.utcnow() + timedelta(minutes=expire_minutes)

    # 【安全加固】強制寫入 token 類型，防止與 Refresh/Reset Token 混淆
    to_encode.update({"exp": expire, "type": "access_token"})

    algorithm = getattr(settings, "ALGORITHM", "HS256")
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=algorithm)

    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        algorithm = getattr(settings, "ALGORITHM", "HS256")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[algorithm])

        # 【安全加固】校驗 Token 類型
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
    # 【安全加固】嚴格類型校驗，防止數據庫注入或類型報錯
    if not service_id or not str(service_id).isdigit():
        raise credentials_exception

    service = db.query(ServiceAgent).filter(ServiceAgent.id == int(service_id)).first()
    if service is None:
        raise credentials_exception

    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # 改為更符合語義的 403
            detail="Inactive service agent",
        )

    return service


def create_default_service_agent(db: Session) -> None:
    """
    創建默認客服帳號（安全初始化版）
    """
    existing_admin = (
        db.query(ServiceAgent).filter(ServiceAgent.username == "admin").first()
    )

    if not existing_admin:
        # 【核心修復】從環境變量讀取管理員密碼，若未配置，則生成隨機強密碼並打印
        # 絕對不允許在源代碼中留下 admin123 這樣的弱密碼！
        admin_password = os.getenv("INIT_ADMIN_PASSWORD")
        if not admin_password:
            admin_password = secrets.token_urlsafe(12)
            print(f"==================================================")
            print(f"⚠️ 警告: 未檢測到初始密碼配置，已生成隨機管理員密碼")
            print(f"用戶名: admin | 密碼: {admin_password}")
            print(f"請妥善保管並盡快登錄系統修改！")
            print(f"==================================================")

        default_service = ServiceAgent(
            username="admin",
            name="系統管理員",
            password_hash=get_password_hash(admin_password),
            email="admin@example.com",
            phone="13800138000",
            status="offline",
            is_active=True,
            role="admin",
        )
        db.add(default_service)
        db.commit()
