"""
Custom Exceptions for Offer Routing System
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class OfferRoutingException(APIException):
    """Base exception for offer routing operations."""
    
    def __init__(self, detail, code=None, status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


class RouteNotFoundError(OfferRoutingException):
    """Exception raised when a route is not found."""
    
    def __init__(self, route_id=None):
        if route_id:
            detail = f"Route with ID {route_id} not found"
        else:
            detail = "Route not found"
        super().__init__(detail, 'route_not_found', status.HTTP_404_NOT_FOUND)


class OfferNotFoundError(OfferRoutingException):
    """Exception raised when an offer is not found."""
    
    def __init__(self, offer_id=None):
        if offer_id:
            detail = f"Offer with ID {offer_id} not found"
        else:
            detail = "Offer not found"
        super().__init__(detail, 'offer_not_found', status.HTTP_404_NOT_FOUND)


class ConditionEvaluationError(OfferRoutingException):
    """Exception raised when condition evaluation fails."""
    
    def __init__(self, condition_id=None, error_message=None):
        if condition_id and error_message:
            detail = f"Condition {condition_id} evaluation failed: {error_message}"
        elif error_message:
            detail = f"Condition evaluation failed: {error_message}"
        else:
            detail = "Condition evaluation failed"
        super().__init__(detail, 'condition_evaluation_failed', status.HTTP_400_BAD_REQUEST)


class ScoringError(OfferRoutingException):
    """Exception raised during offer scoring."""
    
    def __init__(self, offer_id=None, error_message=None):
        if offer_id and error_message:
            detail = f"Offer {offer_id} scoring failed: {error_message}"
        elif error_message:
            detail = f"Offer scoring failed: {error_message}"
        else:
            detail = "Offer scoring failed"
        super().__init__(detail, 'scoring_failed', status.HTTP_400_BAD_REQUEST)


class CapExceededError(OfferRoutingException):
    """Exception raised when offer cap is exceeded."""
    
    def __init__(self, offer_id=None, cap_type=None, current_value=None, cap_value=None):
        if offer_id and cap_type:
            detail = f"Offer {offer_id} {cap_type} cap exceeded: {current_value}/{cap_value}"
        else:
            detail = "Offer cap exceeded"
        super().__init__(detail, 'cap_exceeded', status.HTTP_429_TOO_MANY_REQUESTS)


class PersonalizationError(OfferRoutingException):
    """Exception raised during personalization."""
    
    def __init__(self, algorithm=None, error_message=None):
        if algorithm and error_message:
            detail = f"Personalization ({algorithm}) failed: {error_message}"
        elif error_message:
            detail = f"Personalization failed: {error_message}"
        else:
            detail = "Personalization failed"
        super().__init__(detail, 'personalization_failed', status.HTTP_400_BAD_REQUEST)


class FallbackError(OfferRoutingException):
    """Exception raised during fallback routing."""
    
    def __init__(self, fallback_type=None, error_message=None):
        if fallback_type and error_message:
            detail = f"Fallback ({fallback_type}) failed: {error_message}"
        elif error_message:
            detail = f"Fallback failed: {error_message}"
        else:
            detail = "Fallback routing failed"
        super().__init__(detail, 'fallback_failed', status.HTTP_500_INTERNAL_SERVER_ERROR)


class ABTestError(OfferRoutingException):
    """Exception raised during A/B test operations."""
    
    def __init__(self, test_id=None, error_message=None):
        if test_id and error_message:
            detail = f"A/B test {test_id} error: {error_message}"
        elif error_message:
            detail = f"A/B test error: {error_message}"
        else:
            detail = "A/B test error"
        super().__init__(detail, 'ab_test_error', status.HTTP_400_BAD_REQUEST)


class CacheError(OfferRoutingException):
    """Exception raised during cache operations."""
    
    def __init__(self, operation=None, key=None, error_message=None):
        if operation and key:
            detail = f"Cache {operation} failed for key {key}: {error_message}"
        elif operation:
            detail = f"Cache {operation} failed: {error_message}"
        else:
            detail = "Cache operation failed"
        super().__init__(detail, 'cache_error', status.HTTP_500_INTERNAL_SERVER_ERROR)


class RoutingTimeoutError(OfferRoutingException):
    """Exception raised when routing takes too long."""
    
    def __init__(self, timeout_ms=None, operation=None):
        if timeout_ms and operation:
            detail = f"Routing {operation} timed out after {timeout_ms}ms"
        elif timeout_ms:
            detail = f"Routing timed out after {timeout_ms}ms"
        else:
            detail = "Routing timeout"
        super().__init__(detail, 'routing_timeout', status.HTTP_408_REQUEST_TIMEOUT)


class ValidationError(OfferRoutingException):
    """Exception raised for validation errors."""
    
    def __init__(self, field=None, error_message=None):
        if field and error_message:
            detail = f"Validation error for {field}: {error_message}"
        elif error_message:
            detail = f"Validation error: {error_message}"
        else:
            detail = "Validation error"
        super().__init__(detail, 'validation_error', status.HTTP_400_BAD_REQUEST)


class PermissionError(OfferRoutingException):
    """Exception raised for permission errors."""
    
    def __init__(self, action=None, resource=None):
        if action and resource:
            detail = f"Permission denied for {action} on {resource}"
        elif action:
            detail = f"Permission denied for {action}"
        else:
            detail = "Permission denied"
        super().__init__(detail, 'permission_denied', status.HTTP_403_FORBIDDEN)


class RateLimitError(OfferRoutingException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, limit=None, window=None):
        if limit and window:
            detail = f"Rate limit exceeded: {limit} requests per {window}"
        else:
            detail = "Rate limit exceeded"
        super().__init__(detail, 'rate_limit_exceeded', status.HTTP_429_TOO_MANY_REQUESTS)


class ConfigurationError(OfferRoutingException):
    """Exception raised for configuration errors."""
    
    def __init__(self, setting=None, error_message=None):
        if setting and error_message:
            detail = f"Configuration error for {setting}: {error_message}"
        elif error_message:
            detail = f"Configuration error: {error_message}"
        else:
            detail = "Configuration error"
        super().__init__(detail, 'configuration_error', status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExternalServiceError(OfferRoutingException):
    """Exception raised for external service errors."""
    
    def __init__(self, service=None, error_message=None):
        if service and error_message:
            detail = f"External service ({service}) error: {error_message}"
        elif error_message:
            detail = f"External service error: {error_message}"
        else:
            detail = "External service error"
        super().__init__(detail, 'external_service_error', status.HTTP_502_BAD_GATEWAY)


class DatabaseError(OfferRoutingException):
    """Exception raised for database errors."""
    
    def __init__(self, operation=None, error_message=None):
        if operation and error_message:
            detail = f"Database {operation} failed: {error_message}"
        elif error_message:
            detail = f"Database error: {error_message}"
        else:
            detail = "Database error"
        super().__init__(detail, 'database_error', status.HTTP_500_INTERNAL_SERVER_ERROR)


class InsufficientDataError(OfferRoutingException):
    """Exception raised when there's insufficient data for routing."""
    
    def __init__(self, data_type=None, min_required=None):
        if data_type and min_required:
            detail = f"Insufficient {data_type}: minimum {min_required} required"
        elif data_type:
            detail = f"Insufficient {data_type}"
        else:
            detail = "Insufficient data for routing"
        super().__init__(detail, 'insufficient_data', status.HTTP_400_BAD_REQUEST)


class RoutingEngineError(OfferRoutingException):
    """Exception raised by the routing engine."""
    
    def __init__(self, error_message=None, error_code=None):
        if error_message:
            detail = f"Routing engine error: {error_message}"
        else:
            detail = "Routing engine error"
        super().__init__(detail, error_code or 'routing_engine_error', status.HTTP_500_INTERNAL_SERVER_ERROR)


class TargetingError(OfferRoutingException):
    """Exception raised during targeting operations."""
    
    def __init__(self, targeting_type=None, error_message=None):
        if targeting_type and error_message:
            detail = f"Targeting ({targeting_type}) error: {error_message}"
        elif error_message:
            detail = f"Targeting error: {error_message}"
        else:
            detail = "Targeting error"
        super().__init__(detail, 'targeting_error', status.HTTP_400_BAD_REQUEST)


class AnalyticsError(OfferRoutingException):
    """Exception raised during analytics operations."""
    
    def __init__(self, metric=None, error_message=None):
        if metric and error_message:
            detail = f"Analytics ({metric}) error: {error_message}"
        elif error_message:
            detail = f"Analytics error: {error_message}"
        else:
            detail = "Analytics error"
        super().__init__(detail, 'analytics_error', status.HTTP_500_INTERNAL_SERVER_ERROR)


class PerformanceError(OfferRoutingException):
    """Exception raised for performance issues."""
    
    def __init__(self, operation=None, threshold_ms=None, actual_ms=None):
        if operation and threshold_ms and actual_ms:
            detail = f"Performance issue: {operation} took {actual_ms}ms (threshold: {threshold_ms}ms)"
        elif operation:
            detail = f"Performance issue: {operation}"
        else:
            detail = "Performance issue"
        super().__init__(detail, 'performance_issue', status.HTTP_500_INTERNAL_SERVER_ERROR)


# Custom exception handler for DRF
def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.
    """
    from rest_framework.views import exception_handler
    from rest_framework.response import Response
    
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        return response
    
    # Handle custom exceptions
    if isinstance(exc, OfferRoutingException):
        return Response({
            'success': False,
            'error': exc.detail,
            'code': exc.code,
            'status_code': exc.status_code
        }, status=exc.status_code)
    
    # Handle other exceptions
    return Response({
        'success': False,
        'error': str(exc),
        'code': 'internal_server_error',
        'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
