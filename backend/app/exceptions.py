"""
Poclain 智能客服系统 - 全局自定义异常类定义
"""

from typing import Optional


class WeChatCustomerServiceException(Exception):
    """系统基础异常基类"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class AIServiceException(WeChatCustomerServiceException):
    """AI大模型推理与生成异常 (涵盖 DashScope 超时、降级失败)"""

    def __init__(
        self, message: str, error_code: str = "AI_SERVICE_ERROR", status_code: int = 503
    ):
        super().__init__(message, error_code, status_code)


class DatabaseException(WeChatCustomerServiceException):
    """关系型数据库相关异常 (MySQL/SQLAlchemy)"""

    def __init__(
        self, message: str, error_code: str = "DATABASE_ERROR", status_code: int = 500
    ):
        super().__init__(message, error_code, status_code)


class MessageProcessingException(WeChatCustomerServiceException):
    """微信消息体解析与处理异常"""

    def __init__(
        self,
        message: str,
        error_code: str = "MESSAGE_PROCESSING_ERROR",
        status_code: int = 500,
    ):
        super().__init__(message, error_code, status_code)


class WeChatAPIException(WeChatCustomerServiceException):
    """微信公众平台 API 调用异常 (包含 Token 失效、主动推送失败)"""

    def __init__(
        self,
        message: str,
        error_code: str = "WECHAT_API_ERROR",
        status_code: int = 500,
        wechat_error_code: Optional[str] = None,
    ):
        self.wechat_error_code = wechat_error_code
        super().__init__(message, error_code, status_code)


class KnowledgeBaseException(WeChatCustomerServiceException):
    """RAG 向量知识库异常 (涵盖 ChromaDB 检索失败、Rerank 引擎宕机)"""

    def __init__(
        self,
        message: str,
        error_code: str = "KNOWLEDGE_BASE_ERROR",
        status_code: int = 500,
    ):
        super().__init__(message, error_code, status_code)


class AuthenticationException(WeChatCustomerServiceException):
    """JWT 坐席身份认证异常"""

    def __init__(
        self,
        message: str,
        error_code: str = "AUTHENTICATION_ERROR",
        status_code: int = 401,
    ):
        super().__init__(message, error_code, status_code)


class AuthorizationException(WeChatCustomerServiceException):
    """坐席权限越权异常"""

    def __init__(
        self,
        message: str,
        error_code: str = "AUTHORIZATION_ERROR",
        status_code: int = 403,
    ):
        super().__init__(message, error_code, status_code)


class ValidationException(WeChatCustomerServiceException):
    """Pydantic 数据入参验证异常"""

    def __init__(
        self,
        message: str,
        error_code: str = "VALIDATION_ERROR",
        status_code: int = 400,
        field_errors: Optional[dict] = None,
    ):
        self.field_errors = field_errors
        super().__init__(message, error_code, status_code)


class RateLimitException(WeChatCustomerServiceException):
    """CC 防护与滑动窗口限流拦截异常"""

    def __init__(
        self,
        message: str = "您的请求过于频繁，触发系统安全限流，请稍后再试",
        error_code: str = "RATE_LIMIT_ERROR",
        status_code: int = 429,
    ):
        super().__init__(message, error_code, status_code)


class NotFoundException(WeChatCustomerServiceException):
    """数据库或业务资源未找到异常"""

    def __init__(
        self, message: str, error_code: str = "NOT_FOUND_ERROR", status_code: int = 404
    ):
        super().__init__(message, error_code, status_code)


class ServiceUnavailableException(WeChatCustomerServiceException):
    """全局服务不可用或维护中异常"""

    def __init__(
        self,
        message: str = "系统架构调整中，服务暂时不可用",
        error_code: str = "SERVICE_UNAVAILABLE_ERROR",
        status_code: int = 503,
    ):
        super().__init__(message, error_code, status_code)


# ==========================================
# 🚨 架构师补丁：S级防御体系专属异常
# ==========================================


class PromptInjectionException(WeChatCustomerServiceException):
    """
    物理隔离异常：当 SecurityGuardian 检测到 '忽略设定'、'脱口秀' 等越权指令时触发
    返回 403 Forbidden，直接阻断 LLM 算力消耗
    """

    def __init__(
        self,
        message: str = "检测到非法的系统级指令注入尝试，连接已强制阻断",
        error_code: str = "PROMPT_INJECTION_DETECTED",
        status_code: int = 403,
    ):
        super().__init__(message, error_code, status_code)


class ContextOverflowException(WeChatCustomerServiceException):
    """
    Token 保护异常：当 RAG 召回片段 (Top K) 加历史记忆导致上下文超过大模型限制时触发
    返回 413 Payload Too Large
    """

    def __init__(
        self,
        message: str = "用户提问涉及的知识手册过长，导致 AI 引擎上下文超载",
        error_code: str = "CONTEXT_OVERFLOW_ERROR",
        status_code: int = 413,
    ):
        super().__init__(message, error_code, status_code)
