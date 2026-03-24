"""
Poclain 智能客服系统 - 全局数据交互模型 (Schemas)
基于 Pydantic V2 规范构建，采用严格类型校验与 ORM 兼容配置
"""

from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# ==========================================
# 1. 坐席与认证模型
# ==========================================


class ServiceLoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class ServiceInfo(BaseModel):
    id: int
    name: str
    username: str
    avatar: Optional[str] = None
    status: str
    role: Optional[str] = None
    roles: List[str] = Field(default_factory=list)  # 🚨 兼容 Vue 权限指令

    model_config = ConfigDict(from_attributes=True)


class ServiceLoginResponse(BaseModel):
    code: int = 200
    message: str = "success"
    access_token: str
    token: str  # 🚨 冗余设计：兼容不同前端模板
    userInfo: ServiceInfo
    data: dict


# ==========================================
# 2. 微信会话 (Session) 模型
# ==========================================


class SessionListResponse(BaseModel):
    """
    S级加固：列表模型必须保持轻量且全字段可选，防止因 DB 关联查询失败导致整体 500
    """

    id: int
    user_id: str
    user_name: Optional[str] = "Poclain 客户"
    user_avatar: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_message: Optional[str] = ""

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(BaseModel):
    id: int
    user_id: str
    user_name: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 3. 消息流 (Message) 模型
# ==========================================


class MessageResponse(BaseModel):
    id: Optional[Any] = None  # 兼容临时前端生成的 ID
    session_id: Any
    sender: str
    content: str
    created_at: datetime
    is_read: bool = True

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 4. 统计与仪表盘模型 (解决 NaN 问题)
# ==========================================


class ServiceStatistics(BaseModel):
    total_sessions: int
    today_sessions: int
    pending_count: int
    active_chats: int
    satisfaction_rate: float
    system_status: str = "healthy"
