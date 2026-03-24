from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.dialects.mysql import LONGTEXT  # 🚨 架构师保留：MySQL 专属深层扩容类型
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

from app.core.database import Base

# ==========================================
# 🚨 枚举定义
# ==========================================


class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    AI_HANDLING = "ai_handling"
    CLOSED = "closed"


class MessageSender(str, enum.Enum):
    USER = "user"
    SERVICE = "service"
    AI = "ai"
    SYSTEM = "system"


# ==========================================
# 1. 坐席模型
# ==========================================


class ServiceAgent(Base):
    __tablename__ = "service_agents"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    avatar = Column(String(255))
    email = Column(String(100), unique=True)
    phone = Column(String(20))
    status = Column(String(20), default="offline", nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="agent")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True))

    sessions = relationship(
        "CustomerSession",
        back_populates="service_agent",
        lazy="selectin",
        foreign_keys="CustomerSession.service_agent_id",
    )

    messages = relationship(
        "Message", back_populates="service_agent_rel", lazy="noload"
    )


# ==========================================
# 2. 会话模型
# ==========================================


class CustomerSession(Base):
    __tablename__ = "customer_sessions"

    __table_args__ = (
        Index("ix_customer_sessions_user_status", "user_id", "status"),
        Index("ix_customer_sessions_agent_status", "service_agent_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    user_name = Column(String(100))
    user_avatar = Column(String(255))
    status = Column(
        SQLEnum(SessionStatus),
        default=SessionStatus.PENDING,
        nullable=False,
        index=True,
    )

    service_agent_id = Column(Integer, ForeignKey("service_agents.id"), index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    last_message = Column(Text)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ended_at = Column(DateTime(timezone=True))
    ended_by = Column(Integer, ForeignKey("service_agents.id"), index=True)
    satisfaction_score = Column(Integer)
    satisfaction_comment = Column(Text)

    service_agent = relationship(
        "ServiceAgent", back_populates="sessions", foreign_keys=[service_agent_id]
    )
    ender = relationship("ServiceAgent", foreign_keys=[ended_by])

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# ==========================================
# 3. 消息模型
# ==========================================


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("customer_sessions.id"), nullable=False, index=True
    )
    sender = Column(SQLEnum(MessageSender), nullable=False)
    content = Column(Text, nullable=False)

    # 🚨 架构师加固：保留业务层需要的 msg_type 字段
    msg_type = Column(String(20), default="text", nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    is_read = Column(Boolean, default=False)
    user_name = Column(String(100))
    user_avatar = Column(String(255))

    service_agent_id = Column(Integer, ForeignKey("service_agents.id"), index=True)

    session = relationship("CustomerSession", back_populates="messages")
    service_agent_rel = relationship("ServiceAgent", back_populates="messages")


# ==========================================
# 4. 知识库模型
# ==========================================


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)

    # 🚨 物理边界突破：保留强制升级为 4GB 的 LONGTEXT
    content = Column(LONGTEXT, nullable=False)

    category = Column(String(50), index=True)
    version = Column(Integer, default=1)
    create_time = Column(DateTime(timezone=True), server_default=func.now())
    update_time = Column(DateTime(timezone=True), onupdate=func.now())


# ==========================================
# 5. 系统配置与提示词寄存器模型 (解耦硬编码)
# ==========================================


class PromptConfig(Base):
    __tablename__ = "prompt_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(50), unique=True, nullable=False, index=True)
    config_value = Column(LONGTEXT, nullable=False)
    description = Column(String(200))
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
