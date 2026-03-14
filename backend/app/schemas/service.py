from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

# 客服登录请求
class ServiceLoginRequest(BaseModel):
    username: str = Field(..., description="用户名", example="admin")
    password: str = Field(..., description="密码", example="admin123")

# 客服信息
class ServiceInfo(BaseModel):
    id: str
    name: str
    username: str
    avatar: Optional[str] = None
    status: str

# 客服登录响应
class ServiceLoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    service: ServiceInfo

# 会话列表响应项
class SessionListResponse(BaseModel):
    id: str
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    status: str
    created_at: str
    last_message: Optional[str] = None
    last_message_time: Optional[str] = None
    service_agent_id: Optional[str] = None
    service_agent_name: Optional[str] = None

# 会话详情响应
class SessionDetailResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    status: str
    service_agent_id: Optional[str] = None
    service_agent_name: Optional[str] = None
    created_at: str
    ended_at: Optional[str] = None
    ended_by: Optional[str] = None
    satisfaction_score: Optional[int] = None
    satisfaction_comment: Optional[str] = None

# 消息响应
class MessageResponse(BaseModel):
    id: str
    session_id: str
    sender: str
    content: str
    created_at: str
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    is_read: bool

# 消息创建请求
class MessageCreateRequest(BaseModel):
    content: str = Field(..., description="消息内容", example="您好，有什么可以帮助您的吗？")

# 消息列表响应
class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    has_more: bool

# 客服状态更新请求
class ServiceStatusUpdate(BaseModel):
    status: str = Field(..., description="状态", example="online")

# 客服统计数据
class ServiceStatistics(BaseModel):
    total_sessions: int = Field(..., description="总会话数")
    today_sessions: int = Field(..., description="今日会话数")
    avg_response_time: float = Field(..., description="平均响应时间（秒）")
    satisfaction_rate: float = Field(..., description="客户满意度（1-5分）")
    active_sessions: int = Field(..., description="正在处理的会话数")
    service_name: str = Field(..., description="客服姓名")
    service_status: str = Field(..., description="客服状态")
    last_login: Optional[str] = Field(None, description="最后登录时间")