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
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class ServiceAgent(Base):
    """
    客服人员表
    """

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

    # 【核心修复】废除 lazy="dynamic"，改用性能优异的 selectin，彻底消除 N+1 全表扫描风险
    sessions = relationship(
        "CustomerSession",
        back_populates="service_agent",
        lazy="selectin",
        foreign_keys="[CustomerSession.service_agent_id]",
    )

    messages = relationship(
        "Message", back_populates="service_agent_rel", lazy="noload"
    )


class SessionStatus(str, enum.Enum):
    """
    会话状态枚举
    """

    PENDING = "pending"
    ACTIVE = "active"
    AI_HANDLING = "ai_handling"
    CLOSED = "closed"


class MessageSender(str, enum.Enum):
    """
    消息发送者枚举
    """

    USER = "user"
    SERVICE = "service"
    AI = "ai"
    SYSTEM = "system"


class CustomerSession(Base):
    """
    客户会话表
    """

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
    ended_at = Column(DateTime(timezone=True))
    ended_by = Column(Integer, ForeignKey("service_agents.id"), index=True)
    satisfaction_score = Column(Integer)
    satisfaction_comment = Column(Text)

    service_agent = relationship(
        "ServiceAgent", back_populates="sessions", foreign_keys=[service_agent_id]
    )
    ender = relationship("ServiceAgent", foreign_keys=[ended_by])

    # 【核心修复】废除 lazy="dynamic"，替换为现代化急加载策略，防止关联查询导致的连接池干涸
    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Message(Base):
    """
    消息表
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("customer_sessions.id"), nullable=False, index=True
    )
    sender = Column(SQLEnum(MessageSender), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    is_read = Column(Boolean, default=False)
    user_name = Column(String(100))
    user_avatar = Column(String(255))

    service_agent_id = Column(Integer, ForeignKey("service_agents.id"), index=True)

    session = relationship("CustomerSession", back_populates="messages")
    service_agent_rel = relationship("ServiceAgent", back_populates="messages")


class KnowledgeDoc(Base):
    """
    知识库文档表
    """

    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    category = Column(String(50), index=True)
    version = Column(Integer, default=1)
    create_time = Column(DateTime(timezone=True), server_default=func.now())
    update_time = Column(DateTime(timezone=True), onupdate=func.now())
