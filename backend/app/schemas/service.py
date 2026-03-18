"""
Poclain 智能客服系统 - 全局数据交互模型 (Schemas)
基于 Pydantic V2 规范构建，完美契合 SQLAlchemy 2.0
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# ==========================================
# 1. 坐席与认证模型
# ==========================================


class ServiceLoginRequest(BaseModel):
    username: str = Field(..., description="用户名", examples=["admin"])
    password: str = Field(..., description="密码", examples=["admin123"])


class ServiceInfo(BaseModel):
    id: int  # 【修复】对齐 DB 的 Integer 主键
    name: str
    username: str
    avatar: Optional[str] = None
    status: str
    role: Optional[str] = None

    # 【核心修复】Pydantic V2 的 ORM 模式，允许直接读取 SQLAlchemy 对象
    model_config = ConfigDict(from_attributes=True)


class ServiceLoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    service: ServiceInfo


class ServiceStatusUpdate(BaseModel):
    status: str = Field(..., description="坐席状态", examples=["online"])


# ==========================================
# 2. 微信会话 (Session) 模型
# ==========================================


class SessionListResponse(BaseModel):
    id: int
    # 🚨 就是下面这行惹的祸，把它删掉，或者加上 Optional
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    status: str
    created_at: datetime
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    service_agent_id: Optional[int] = None
    service_agent_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(BaseModel):
    id: int
    user_id: str
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    status: str
    service_agent_id: Optional[int] = None
    service_agent_name: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None
    ended_by: Optional[int] = None
    satisfaction_score: Optional[int] = None
    satisfaction_comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 3. 消息流 (Message) 模型
# ==========================================


class MessageResponse(BaseModel):
    id: int
    session_id: int
    sender: str
    content: str
    created_at: datetime
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    is_read: bool

    model_config = ConfigDict(from_attributes=True)


class MessageCreateRequest(BaseModel):
    content: str = Field(
        ..., description="消息内容", examples=["您好，Poclain 官方客服为您服务。"]
    )


class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    has_more: bool


# ==========================================
# 4. 统计与仪表盘 (Dashboard) 模型
# ==========================================


class ServiceStatistics(BaseModel):
    total_sessions: int = Field(..., description="总会话数")
    today_sessions: int = Field(..., description="今日会话数")
    avg_response_time: float = Field(..., description="平均响应时间（秒）")
    satisfaction_rate: float = Field(..., description="客户满意度（1-5分）")
    active_sessions: int = Field(..., description="正在处理的会话数")
    service_name: str = Field(..., description="当前客服姓名")
    service_status: str = Field(..., description="当前客服状态")
    last_login: Optional[datetime] = Field(None, description="最后登录时间")
