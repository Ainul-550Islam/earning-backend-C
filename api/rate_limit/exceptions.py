"""
Rate Limit Exceptions

Custom exceptions for the rate limiting module.
"""

from django.utils.translation import gettext_lazy as _


class RateLimitException(Exception):
    """Base exception for rate limiting errors."""
    
    def __init__(self, message=None, code=None, details=None):
        self.message = message or _("Rate limit error occurred")
        self.code = code or "RATE_LIMIT_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class RateLimitExceededException(RateLimitException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message=None, limit_type=None, limit_value=None, 
                 reset_time=None, retry_after=None, details=None):
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.reset_time = reset_time
        self.retry_after = retry_after
        
        if not message:
            if limit_type and limit_value:
                message = _("Rate limit exceeded for %(limit_type)s. "
                          "Maximum %(limit_value)d requests allowed.") % {
                    'limit_type': limit_type,
                    'limit_value': limit_value
                }
            else:
                message = _("Rate limit exceeded")
        
        if not details:
            details = {
                'limit_type': limit_type,
                'limit_value': limit_value,
                'reset_time': reset_time,
                'retry_after': retry_after
            }
        
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details=details
        )


class InvalidRateLimitConfig(RateLimitException):
    """Exception raised for invalid rate limit configuration."""
    
    def __init__(self, message=None, config_field=None, config_value=None, 
                 validation_error=None, details=None):
        self.config_field = config_field
        self.config_value = config_value
        self.validation_error = validation_error
        
        if not message:
            if config_field and validation_error:
                message = _("Invalid rate limit configuration for field "
                          "'%(field)s': %(error)s") % {
                    'field': config_field,
                    'error': validation_error
                }
            elif config_field:
                message = _("Invalid rate limit configuration for field: %(field)s") % {
                    'field': config_field
                }
            else:
                message = _("Invalid rate limit configuration")
        
        if not details:
            details = {
                'config_field': config_field,
                'config_value': config_value,
                'validation_error': validation_error
            }
        
        super().__init__(
            message=message,
            code="INVALID_RATE_LIMIT_CONFIG",
            details=details
        )


class RateLimitServiceUnavailable(RateLimitException):
    """Exception raised when rate limiting service is unavailable."""
    
    def __init__(self, message=None, service_name=None, error_details=None, details=None):
        self.service_name = service_name
        self.error_details = error_details
        
        if not message:
            if service_name:
                message = _("Rate limiting service '%(service)s' is unavailable") % {
                    'service': service_name
                }
            else:
                message = _("Rate limiting service is unavailable")
        
        if not details:
            details = {
                'service_name': service_name,
                'error_details': error_details
            }
        
        super().__init__(
            message=message,
            code="RATE_LIMIT_SERVICE_UNAVAILABLE",
            details=details
        )


class IPBlockedException(RateLimitException):
    """Exception raised when IP address is blocked."""
    
    def __init__(self, message=None, ip_address=None, block_reason=None, 
                 block_type=None, expires_at=None, details=None):
        self.ip_address = ip_address
        self.block_reason = block_reason
        self.block_type = block_type
        self.expires_at = expires_at
        
        if not message:
            if ip_address and block_reason:
                message = _("IP address %(ip)s is blocked due to: %(reason)s") % {
                    'ip': ip_address,
                    'reason': block_reason
                }
            elif ip_address:
                message = _("IP address %(ip)s is blocked") % {'ip': ip_address}
            else:
                message = _("IP address is blocked")
        
        if not details:
            details = {
                'ip_address': ip_address,
                'block_reason': block_reason,
                'block_type': block_type,
                'expires_at': expires_at
            }
        
        super().__init__(
            message=message,
            code="IP_BLOCKED",
            details=details
        )


class UserRateLimitException(RateLimitException):
    """Exception raised for user-specific rate limit issues."""
    
    def __init__(self, message=None, user_id=None, user_email=None, 
                 limit_type=None, current_usage=None, limit_value=None, details=None):
        self.user_id = user_id
        self.user_email = user_email
        self.limit_type = limit_type
        self.current_usage = current_usage
        self.limit_value = limit_value
        
        if not message:
            if user_email and limit_type:
                message = _("User %(email)s has exceeded %(limit_type)s limit") % {
                    'email': user_email,
                    'limit_type': limit_type
                }
            elif user_id and limit_type:
                message = _("User %(user_id)s has exceeded %(limit_type)s limit") % {
                    'user_id': user_id,
                    'limit_type': limit_type
                }
            else:
                message = _("User rate limit exceeded")
        
        if not details:
            details = {
                'user_id': user_id,
                'user_email': user_email,
                'limit_type': limit_type,
                'current_usage': current_usage,
                'limit_value': limit_value
            }
        
        super().__init__(
            message=message,
            code="USER_RATE_LIMIT_EXCEEDED",
            details=details
        )


class AbuseDetectionException(RateLimitException):
    """Exception raised during abuse detection operations."""
    
    def __init__(self, message=None, detection_type=None, ip_address=None, 
                 user_id=None, pattern=None, details=None):
        self.detection_type = detection_type
        self.ip_address = ip_address
        self.user_id = user_id
        self.pattern = pattern
        
        if not message:
            if detection_type and pattern:
                message = _("Abuse detection failed for %(type)s: %(pattern)s") % {
                    'type': detection_type,
                    'pattern': pattern
                }
            elif detection_type:
                message = _("Abuse detection failed for %(type)s") % {'type': detection_type}
            else:
                message = _("Abuse detection operation failed")
        
        if not details:
            details = {
                'detection_type': detection_type,
                'ip_address': ip_address,
                'user_id': user_id,
                'pattern': pattern
            }
        
        super().__init__(
            message=message,
            code="ABUSE_DETECTION_ERROR",
            details=details
        )


class RateLimitCacheException(RateLimitException):
    """Exception raised during cache operations."""
    
    def __init__(self, message=None, cache_operation=None, cache_key=None, 
                 cache_backend=None, details=None):
        self.cache_operation = cache_operation
        self.cache_key = cache_key
        self.cache_backend = cache_backend
        
        if not message:
            if cache_operation and cache_key:
                message = _("Cache operation '%(operation)s' failed for key '%(key)s'") % {
                    'operation': cache_operation,
                    'key': cache_key
                }
            elif cache_operation:
                message = _("Cache operation '%(operation)s' failed") % {
                    'operation': cache_operation
                }
            else:
                message = _("Rate limit cache operation failed")
        
        if not details:
            details = {
                'cache_operation': cache_operation,
                'cache_key': cache_key,
                'cache_backend': cache_backend
            }
        
        super().__init__(
            message=message,
            code="RATE_LIMIT_CACHE_ERROR",
            details=details
        )


class RateLimitConfigurationError(RateLimitException):
    """Exception raised for general configuration errors."""
    
    def __init__(self, message=None, config_id=None, config_name=None, 
                 error_type=None, details=None):
        self.config_id = config_id
        self.config_name = config_name
        self.error_type = error_type
        
        if not message:
            if config_name and error_type:
                message = _("Configuration error for '%(config)s': %(error)s") % {
                    'config': config_name,
                    'error': error_type
                }
            elif config_name:
                message = _("Configuration error for '%(config)s'") % {'config': config_name}
            else:
                message = _("Rate limit configuration error")
        
        if not details:
            details = {
                'config_id': config_id,
                'config_name': config_name,
                'error_type': error_type
            }
        
        super().__init__(
            message=message,
            code="RATE_LIMIT_CONFIGURATION_ERROR",
            details=details
        )


# Exception hierarchy for easy testing and handling
RATE_LIMIT_EXCEPTIONS = [
    RateLimitException,
    RateLimitExceededException,
    InvalidRateLimitConfig,
    RateLimitServiceUnavailable,
    IPBlockedException,
    UserRateLimitException,
    AbuseDetectionException,
    RateLimitCacheException,
    RateLimitConfigurationError,
]


def is_rate_limit_exception(exception):
    """
    Check if an exception is a rate limit exception.
    
    Args:
        exception: Exception to check
        
    Returns:
        bool: True if it's a rate limit exception
    """
    return isinstance(exception, tuple(RATE_LIMIT_EXCEPTIONS))


def get_exception_code(exception):
    """
    Get the error code from a rate limit exception.
    
    Args:
        exception: Exception to get code from
        
    Returns:
        str: Error code or None
    """
    if is_rate_limit_exception(exception):
        return getattr(exception, 'code', None)
    return None


def get_exception_details(exception):
    """
    Get the details from a rate limit exception.
    
    Args:
        exception: Exception to get details from
        
    Returns:
        dict: Exception details or empty dict
    """
    if is_rate_limit_exception(exception):
        return getattr(exception, 'details', {})
    return {}


class ComplianceError(RateLimitException):
    """Raised when a compliance rule is violated."""
    def __init__(self, message='Compliance rule violated', rule=None, details=None):
        self.rule = rule
        self.details = details or {}
        super().__init__(message)

class RetentionPolicyError(ComplianceError):
    """Raised when data retention policy is violated."""
    pass

class ConsentError(ComplianceError):
    """Raised when user consent is missing or invalid."""
    pass

class AuditLogError(ComplianceError):
    """Raised when audit logging fails."""
    pass
