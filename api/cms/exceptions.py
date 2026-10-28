# cms/exceptions.py
"""
Custom Exceptions & Error Handling System

Comprehensive error handling with:
- Custom exception classes for different error types
- Custom exception handler for DRF
- Error serialization and logging
- User-friendly error messages
- Error tracking and reporting
- Graceful degradation

Exception Hierarchy:
- CMSBaseException (base for all CMS exceptions)
  ├─ ValidationException (data validation errors)
  ├─ AuthenticationException (auth errors)
  ├─ PermissionException (permission errors)
  ├─ ResourceNotFoundException (resource not found)
  ├─ ConflictException (conflict/duplicate)
  ├─ RateLimitException (rate limiting)
  ├─ IntegrationException (external service errors)
  └─ InternalServerException (server errors)
"""

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
import logging
import traceback
from typing import Dict, Any, Optional, Tuple
from django.core.mail import mail_admins
from django.conf import settings
import json

logger = logging.getLogger('cms.exceptions')


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM EXCEPTION CLASSES
# ─────────────────────────────────────────────────────────────────────────────

class CMSBaseException(APIException):
    """
    Base exception for all CMS-specific exceptions
    
    Attributes:
        status_code: HTTP status code
        default_detail: Default error message
        default_code: Error code for frontend
    """
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "An error occurred"
    default_code = "error"
    
    def __init__(self, detail: str = None, code: str = None, 
                 extra_info: Dict[str, Any] = None):
        """
        Initialize exception
        
        Args:
            detail: Human-readable error message
            code: Machine-readable error code
            extra_info: Additional context info for logging
        """
        super().__init__(detail=detail, code=code)
        self.extra_info = extra_info or {}
        self.log_exception()
    
    def log_exception(self):
        """Log exception details"""
        logger.error(
            f"{self.__class__.__name__}: {self.detail}",
            extra={
                'status_code': self.status_code,
                'code': self.detail.code if hasattr(self.detail, 'code') else self.default_code,
                'extra_info': self.extra_info,
            }
        )


class ValidationException(CMSBaseException):
    """
    Raised when input validation fails
    
    Used for:
    - Invalid data format
    - Missing required fields
    - Business rule violations
    """
    
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Validation failed"
    default_code = "validation_error"


class AuthenticationException(CMSBaseException):
    """
    Raised when authentication fails
    
    Used for:
    - Invalid credentials
    - Expired tokens
    - Missing authentication
    """
    
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentication failed"
    default_code = "authentication_error"


class PermissionException(CMSBaseException):
    """
    Raised when user lacks required permissions
    
    Used for:
    - Unauthorized access attempts
    - Insufficient privileges
    - Role-based restrictions
    """
    
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action"
    default_code = "permission_error"


class ResourceNotFoundException(CMSBaseException):
    """
    Raised when requested resource not found
    
    Used for:
    - Non-existent objects
    - Deleted resources
    - Invalid IDs
    """
    
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found"
    default_code = "not_found"


class ConflictException(CMSBaseException):
    """
    Raised when request conflicts with current state
    
    Used for:
    - Duplicate entries
    - Version conflicts
    - State conflicts
    """
    
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Request conflicts with current state"
    default_code = "conflict"


class RateLimitException(CMSBaseException):
    """
    Raised when rate limit exceeded
    
    Used for:
    - Too many requests
    - Quota exceeded
    - Throttling
    """
    
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Rate limit exceeded"
    default_code = "rate_limit_exceeded"


class IntegrationException(CMSBaseException):
    """
    Raised when external service fails
    
    Used for:
    - Payment gateway errors
    - Email service failures
    - Third-party API errors
    """
    
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "External service error"
    default_code = "integration_error"


class InternalServerException(CMSBaseException):
    """
    Raised for unexpected server errors
    
    Used for:
    - Unhandled exceptions
    - Database errors
    - System failures
    """
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Internal server error"
    default_code = "internal_error"


# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS-SPECIFIC EXCEPTIONS
# ─────────────────────────────────────────────────────────────────────────────

class InsufficientBalanceException(ValidationException):
    """User doesn't have enough balance to perform action"""
    
    default_detail = "Insufficient balance"
    default_code = "insufficient_balance"


class WithdrawalLimitExceededException(ValidationException):
    """Withdrawal exceeds daily/monthly limits"""
    
    default_detail = "Withdrawal limit exceeded"
    default_code = "withdrawal_limit_exceeded"


class FraudDetectedException(PermissionException):
    """Fraudulent activity detected"""
    
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Suspicious activity detected. Please contact support."
    default_code = "fraud_detected"


class InvalidOfferException(ValidationException):
    """Offer is invalid or not available"""
    
    default_detail = "This offer is not available"
    default_code = "invalid_offer"


class DuplicateSubmissionException(ConflictException):
    """User already submitted/completed this"""
    
    default_detail = "You have already completed this"
    default_code = "duplicate_submission"


class AccountNotOldEnoughException(ValidationException):
    """Account age requirements not met"""
    
    default_detail = "Your account must be older to perform this action"
    default_code = "account_not_old_enough"


class PaymentFailedException(IntegrationException):
    """Payment processing failed"""
    
    default_detail = "Payment processing failed. Please try again."
    default_code = "payment_failed"


class EmailSendFailedException(IntegrationException):
    """Email sending failed"""
    
    default_detail = "Failed to send email"
    default_code = "email_failed"


# ─────────────────────────────────────────────────────────────────────────────
# ERROR SERIALIZER
# ─────────────────────────────────────────────────────────────────────────────

class ErrorDetail:
    """
    Structured error detail for responses
    
    Provides consistent error format across API
    """
    
    def __init__(self, message: str, code: str = None, 
                 field: str = None, status_code: int = 500,
                 request_id: str = None):
        """
        Initialize error detail
        
        Args:
            message: Human-readable error message
            code: Machine-readable error code
            field: Field name if field-specific error
            status_code: HTTP status code
            request_id: Request ID for tracking
        """
        self.message = message
        self.code = code
        self.field = field
        self.status_code = status_code
        self.request_id = request_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'error': {
                'message': self.message,
                'code': self.code,
                'field': self.field,
            },
            'status_code': self.status_code,
            'request_id': self.request_id,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM EXCEPTION HANDLER
# ─────────────────────────────────────────────────────────────────────────────

def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF
    
    Handles:
    - Standard DRF exceptions
    - Custom CMS exceptions
    - Unexpected exceptions
    - Error logging and reporting
    
    Usage in settings.py:
        REST_FRAMEWORK = {
            'EXCEPTION_HANDLER': 'cms.exceptions.custom_exception_handler'
        }
    """
    
    # Get request and view for context
    request = context.get('request')
    view = context.get('view')
    
    # Generate request ID for tracking
    request_id = getattr(request, 'id', 'unknown') if request else 'unknown'
    
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)
    
    # Handle our custom exceptions
    if isinstance(exc, CMSBaseException):
        return handle_cms_exception(exc, response, request_id)
    
    # Handle standard DRF exceptions
    elif response is not None:
        return handle_drf_exception(exc, response, request_id, request)
    
    # Handle unexpected exceptions
    else:
        return handle_unexpected_exception(exc, request_id, request)


def handle_cms_exception(exc: CMSBaseException, response: Response, 
                        request_id: str) -> Response:
    """Handle CMS-specific exceptions"""
    
    # Build error detail
    error_detail = ErrorDetail(
        message=str(exc.detail),
        code=getattr(exc, 'default_code', 'error'),
        status_code=exc.status_code,
        request_id=request_id,
    )
    
    # Format response
    response_data = {
        'success': False,
        'error': error_detail.to_dict()['error'],
        'request_id': request_id,
    }
    
    response = Response(response_data, status=exc.status_code)
    
    # Log the exception
    log_exception(exc, request_id, context='cms_exception')
    
    return response


def handle_drf_exception(exc: Exception, response: Response, 
                        request_id: str, request) -> Response:
    """Handle standard DRF exceptions"""
    
    # Extract error details
    status_code = response.status_code
    error_data = response.data
    
    # Format error message
    if isinstance(error_data, dict):
        if 'detail' in error_data:
            message = str(error_data['detail'])
        else:
            # Multiple field errors
            message = "Validation failed"
    else:
        message = str(error_data)
    
    # Build response
    response_data = {
        'success': False,
        'error': {
            'message': message,
            'code': 'validation_error' if status_code == 400 else 'error',
            'details': error_data if isinstance(error_data, dict) else None,
        },
        'request_id': request_id,
    }
    
    response = Response(response_data, status=status_code)
    
    # Log
    log_exception(exc, request_id, context='drf_exception')
    
    return response


def handle_unexpected_exception(exc: Exception, request_id: str,
                               request) -> Response:
    """Handle unexpected exceptions"""
    
    # Log full traceback
    logger.error(
        f"Unexpected exception: {exc.__class__.__name__}: {str(exc)}",
        extra={
            'request_id': request_id,
            'traceback': traceback.format_exc(),
            'exception_type': exc.__class__.__name__,
        }
    )
    
    # Send alert to admins
    send_exception_alert(exc, request_id, request)
    
    # Return generic error message (don't expose details)
    response_data = {
        'success': False,
        'error': {
            'message': 'An unexpected error occurred',
            'code': 'internal_error',
        },
        'request_id': request_id,
    }
    
    return Response(
        response_data,
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


# ─────────────────────────────────────────────────────────────────────────────
# ERROR LOGGING & REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def log_exception(exc: Exception, request_id: str, context: str = 'unknown'):
    """
    Log exception with context
    
    Args:
        exc: Exception instance
        request_id: Unique request identifier
        context: Context where exception occurred
    """
    
    log_data = {
        'request_id': request_id,
        'context': context,
        'exception_type': exc.__class__.__name__,
        'message': str(exc),
    }
    
    # Add extra info if CMS exception
    if isinstance(exc, CMSBaseException):
        log_data['extra_info'] = exc.extra_info
    
    logger.error(
        f"Exception in {context}: {exc.__class__.__name__}",
        extra=log_data
    )


def send_exception_alert(exc: Exception, request_id: str, request=None):
    """
    Send alert email to admins on critical errors
    
    Args:
        exc: Exception instance
        request_id: Request identifier
        request: HTTP request object
    """
    
    if not getattr(settings, 'SEND_ERROR_ALERTS', True):
        return
    
    try:
        # Build email content
        subject = f"[CMS Error] {exc.__class__.__name__}"
        message = f"""
Request ID: {request_id}
Exception: {exc.__class__.__name__}
Message: {str(exc)}

Traceback:
{traceback.format_exc()}

Request Info:
- Method: {request.method if request else 'Unknown'}
- Path: {request.path if request else 'Unknown'}
- User: {request.user if request else 'Unknown'}
"""
        
        mail_admins(subject, message, fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send exception alert: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ERROR RESPONSE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def error_response(message: str, code: str = 'error', 
                  status_code: int = 400,
                  field: str = None, 
                  extra: Dict[str, Any] = None) -> Response:
    """
    Helper to create standardized error response
    
    Args:
        message: Error message
        code: Error code
        status_code: HTTP status code
        field: Field name if field-specific
        extra: Additional error info
        
    Returns:
        DRF Response object
    """
    
    error_data = {
        'success': False,
        'error': {
            'message': message,
            'code': code,
        }
    }
    
    if field:
        error_data['error']['field'] = field
    
    if extra:
        error_data['error'].update(extra)
    
    return Response(error_data, status=status_code)


def validation_error_response(errors: Dict[str, str]) -> Response:
    """
    Create validation error response
    
    Args:
        errors: Dictionary of field -> error message
        
    Returns:
        DRF Response object
    """
    
    return Response({
        'success': False,
        'error': {
            'message': 'Validation failed',
            'code': 'validation_error',
            'fields': errors,
        }
    }, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT MANAGERS FOR ERROR HANDLING
# ─────────────────────────────────────────────────────────────────────────────

class ErrorContext:
    """
    Context manager for handling errors gracefully
    
    Usage:
        with ErrorContext('withdraw_funds'):
            # code that might raise exceptions
            pass
    """
    
    def __init__(self, operation: str, request_id: str = None):
        """
        Initialize error context
        
        Args:
            operation: Operation name for logging
            request_id: Request ID for tracking
        """
        self.operation = operation
        self.request_id = request_id or 'unknown'
        self.exception = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Handle exception"""
        
        if exc_type is None:
            return False
        
        # Log the error
        self.exception = exc_val
        log_exception(
            exc_val,
            self.request_id,
            context=f'operation:{self.operation}'
        )
        
        # Don't suppress the exception
        return False


# Export public API
__all__ = [
    # Base exceptions
    'CMSBaseException',
    'ValidationException',
    'AuthenticationException',
    'PermissionException',
    'ResourceNotFoundException',
    'ConflictException',
    'RateLimitException',
    'IntegrationException',
    'InternalServerException',
    
    # Business exceptions
    'InsufficientBalanceException',
    'WithdrawalLimitExceededException',
    'FraudDetectedException',
    'InvalidOfferException',
    'DuplicateSubmissionException',
    'AccountNotOldEnoughException',
    'PaymentFailedException',
    'EmailSendFailedException',
    
    # Utilities
    'ErrorDetail',
    'custom_exception_handler',
    'error_response',
    'validation_error_response',
    'ErrorContext',
]
