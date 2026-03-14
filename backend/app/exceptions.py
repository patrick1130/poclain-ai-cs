"""
自定义异常类定义
"""

from typing import Optional


class WeChatCustomerServiceException(Exception):
    """微信客服系统基础异常类"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 status_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class AIServiceException(WeChatCustomerServiceException):
    """AI服务相关异常"""
    
    def __init__(self, message: str, error_code: str = "AI_SERVICE_ERROR", 
                 status_code: int = 503):
        super().__init__(message, error_code, status_code)


class DatabaseException(WeChatCustomerServiceException):
    """数据库相关异常"""
    
    def __init__(self, message: str, error_code: str = "DATABASE_ERROR", 
                 status_code: int = 500):
        super().__init__(message, error_code, status_code)


class MessageProcessingException(WeChatCustomerServiceException):
    """消息处理相关异常"""
    
    def __init__(self, message: str, error_code: str = "MESSAGE_PROCESSING_ERROR", 
                 status_code: int = 500):
        super().__init__(message, error_code, status_code)


class WeChatAPIException(WeChatCustomerServiceException):
    """微信API调用异常"""
    
    def __init__(self, message: str, error_code: str = "WECHAT_API_ERROR", 
                 status_code: int = 500, wechat_error_code: Optional[str] = None):
        self.wechat_error_code = wechat_error_code
        super().__init__(message, error_code, status_code)


class KnowledgeBaseException(WeChatCustomerServiceException):
    """知识库相关异常"""
    
    def __init__(self, message: str, error_code: str = "KNOWLEDGE_BASE_ERROR", 
                 status_code: int = 500):
        super().__init__(message, error_code, status_code)


class AuthenticationException(WeChatCustomerServiceException):
    """认证相关异常"""
    
    def __init__(self, message: str, error_code: str = "AUTHENTICATION_ERROR", 
                 status_code: int = 401):
        super().__init__(message, error_code, status_code)


class AuthorizationException(WeChatCustomerServiceException):
    """授权相关异常"""
    
    def __init__(self, message: str, error_code: str = "AUTHORIZATION_ERROR", 
                 status_code: int = 403):
        super().__init__(message, error_code, status_code)


class ValidationException(WeChatCustomerServiceException):
    """数据验证异常"""
    
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", 
                 status_code: int = 400, field_errors: Optional[dict] = None):
        self.field_errors = field_errors
        super().__init__(message, error_code, status_code)


class RateLimitException(WeChatCustomerServiceException):
    """速率限制异常"""
    
    def __init__(self, message: str = "请求过于频繁，请稍后再试", 
                 error_code: str = "RATE_LIMIT_ERROR", status_code: int = 429):
        super().__init__(message, error_code, status_code)


class NotFoundException(WeChatCustomerServiceException):
    """资源未找到异常"""
    
    def __init__(self, message: str, error_code: str = "NOT_FOUND_ERROR", 
                 status_code: int = 404):
        super().__init__(message, error_code, status_code)


class ServiceUnavailableException(WeChatCustomerServiceException):
    """服务不可用异常"""
    
    def __init__(self, message: str = "服务暂时不可用，请稍后再试", 
                 error_code: str = "SERVICE_UNAVAILABLE_ERROR", status_code: int = 503):
        super().__init__(message, error_code, status_code)