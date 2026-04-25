"""
api/ad_networks/exceptions.py
Custom exceptions for ad networks module
SaaS-ready with tenant support
"""

from django.core.exceptions import ValidationError, PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
import logging
import traceback

logger = logging.getLogger(__name__)


class AdNetworkException(APIException):
    """
    Base exception for ad networks module
    """
    default_detail = 'An ad networks error occurred'
    default_code = 'ad_network_error'
    status_code = status.HTTP_400_BAD_REQUEST
    
    def __init__(self, detail=None, code=None, status_code=None, extra_data=None):
        self.detail = detail or self.default_detail
        self.code = code or self.default_code
        self.status_code = status_code or self.status_code
        self.extra_data = extra_data or {}
        
        # Log exception
        logger.error(
            f"AdNetworkException: {self.detail} (Code: {self.code})",
            extra={
                'exception_type': self.__class__.__name__,
                'code': self.code,
                'detail': self.detail,
                'extra_data': self.extra_data,
                'traceback': traceback.format_exc()
            }
        )
        super().__init__(detail)
    
    def __str__(self):
        return f"{self.__class__.__name__}: {self.detail}"
    
    def get_full_details(self):
        """Get full exception details including extra data"""
        return {
            'error': self.code,
            'message': self.detail,
            'status_code': self.status_code,
            'extra_data': self.extra_data
        }


class OfferNotFoundException(AdNetworkException):
    """
    Exception raised when an offer is not found
    """
    default_detail = 'Offer not found'
    default_code = 'offer_not_found'
    status_code = status.HTTP_404_NOT_FOUND
    
    def __init__(self, offer_id=None, **kwargs):
        if offer_id:
            detail = f"Offer with ID '{offer_id}' not found"
            extra_data = {'offer_id': offer_id}
        else:
            detail = self.default_detail
            extra_data = {}
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class NetworkUnavailableException(AdNetworkException):
    """
    Exception raised when a network is unavailable
    """
    default_detail = 'Network is currently unavailable'
    default_code = 'network_unavailable'
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    def __init__(self, network_name=None, reason=None, **kwargs):
        if network_name:
            detail = f"Network '{network_name}' is currently unavailable"
            extra_data = {'network_name': network_name}
        else:
            detail = self.default_detail
            extra_data = {}
        
        if reason:
            detail += f": {reason}"
            extra_data['reason'] = reason
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class DailyLimitExceededException(AdNetworkException):
    """
    Exception raised when daily limit is exceeded
    """
    default_detail = 'Daily limit has been exceeded'
    default_code = 'daily_limit_exceeded'
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    
    def __init__(self, limit_type=None, current_count=None, limit=None, reset_time=None, **kwargs):
        if limit_type and limit:
            detail = f"Daily {limit_type} limit of {limit} has been exceeded"
            extra_data = {
                'limit_type': limit_type,
                'current_count': current_count,
                'limit': limit,
                'reset_time': reset_time
            }
        else:
            detail = self.default_detail
            extra_data = {}
        
        if current_count is not None:
            detail += f" (current: {current_count})"
            extra_data['current_count'] = current_count
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class FraudDetectedException(AdNetworkException):
    """
    Exception raised when fraud is detected
    """
    default_detail = 'Fraudulent activity detected'
    default_code = 'fraud_detected'
    status_code = status.HTTP_403_FORBIDDEN
    
    def __init__(self, fraud_type=None, fraud_score=None, details=None, **kwargs):
        if fraud_type:
            detail = f"Fraud detected: {fraud_type}"
            extra_data = {
                'fraud_type': fraud_type,
                'fraud_score': fraud_score,
                'details': details
            }
        else:
            detail = self.default_detail
            extra_data = {}
        
        if fraud_score is not None:
            detail += f" (score: {fraud_score})"
            extra_data['fraud_score'] = fraud_score
        
        if details:
            extra_data['details'] = details
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class ConversionAlreadyExistsException(AdNetworkException):
    """
    Exception raised when conversion already exists
    """
    default_detail = 'Conversion already exists'
    default_code = 'conversion_already_exists'
    status_code = status.HTTP_409_CONFLICT
    
    def __init__(self, conversion_id=None, user_id=None, offer_id=None, **kwargs):
        detail = self.default_detail
        extra_data = {}
        
        if conversion_id:
            detail = f"Conversion with ID '{conversion_id}' already exists"
            extra_data['conversion_id'] = conversion_id
        
        if user_id and offer_id:
            detail = f"Conversion already exists for user {user_id} on offer {offer_id}"
            extra_data.update({
                'user_id': user_id,
                'offer_id': offer_id
            })
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class InsufficientFundsException(AdNetworkException):
    """
    Exception raised when insufficient funds for payout
    """
    default_detail = 'Insufficient funds for payout'
    default_code = 'insufficient_funds'
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    
    def __init__(self, required_amount=None, available_amount=None, currency='USD', **kwargs):
        if required_amount and available_amount:
            detail = f"Insufficient funds: required {required_amount} {currency}, available {available_amount} {currency}"
            extra_data = {
                'required_amount': str(required_amount),
                'available_amount': str(available_amount),
                'currency': currency
            }
        else:
            detail = self.default_detail
            extra_data = {}
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class OfferExpiredException(AdNetworkException):
    """
    Exception raised when offer has expired
    """
    default_detail = 'Offer has expired'
    default_code = 'offer_expired'
    status_code = status.HTTP_410_GONE
    
    def __init__(self, offer_id=None, expiry_date=None, **kwargs):
        if offer_id:
            detail = f"Offer '{offer_id}' has expired"
            extra_data = {'offer_id': offer_id}
        else:
            detail = self.default_detail
            extra_data = {}
        
        if expiry_date:
            extra_data['expiry_date'] = expiry_date.isoformat() if hasattr(expiry_date, 'isoformat') else str(expiry_date)
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class NetworkConfigurationException(AdNetworkException):
    """
    Exception raised when network configuration is invalid
    """
    default_detail = 'Network configuration is invalid'
    default_code = 'network_configuration_error'
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def __init__(self, network_name=None, config_field=None, **kwargs):
        if network_name and config_field:
            detail = f"Invalid configuration for network '{network_name}': {config_field}"
            extra_data = {
                'network_name': network_name,
                'config_field': config_field
            }
        else:
            detail = self.default_detail
            extra_data = {}
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class APIRateLimitExceededException(AdNetworkException):
    """
    Exception raised when API rate limit is exceeded
    """
    default_detail = 'API rate limit exceeded'
    default_code = 'api_rate_limit_exceeded'
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    
    def __init__(self, limit=None, window_minutes=None, reset_time=None, **kwargs):
        if limit and window_minutes:
            detail = f"API rate limit exceeded: {limit} requests per {window_minutes} minutes"
            extra_data = {
                'limit': limit,
                'window_minutes': window_minutes,
                'reset_time': reset_time
            }
        else:
            detail = self.default_detail
            extra_data = {}
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class InvalidPostbackException(AdNetworkException):
    """
    Exception raised when postback data is invalid
    """
    default_detail = 'Invalid postback data'
    default_code = 'invalid_postback'
    status_code = status.HTTP_400_BAD_REQUEST
    
    def __init__(self, missing_fields=None, invalid_fields=None, **kwargs):
        detail = self.default_detail
        extra_data = {}
        
        if missing_fields:
            detail += f": Missing fields: {', '.join(missing_fields)}"
            extra_data['missing_fields'] = missing_fields
        
        if invalid_fields:
            detail += f": Invalid fields: {', '.join(invalid_fields)}"
            extra_data['invalid_fields'] = invalid_fields
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class TenantLimitExceededException(AdNetworkException):
    """
    Exception raised when tenant limit is exceeded
    """
    default_detail = 'Tenant limit has been exceeded'
    default_code = 'tenant_limit_exceeded'
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    
    def __init__(self, limit_type=None, current_usage=None, limit=None, **kwargs):
        if limit_type and limit:
            detail = f"Tenant {limit_type} limit of {limit} has been exceeded"
            extra_data = {
                'limit_type': limit_type,
                'current_usage': current_usage,
                'limit': limit
            }
        else:
            detail = self.default_detail
            extra_data = {}
        
        if current_usage is not None:
            detail += f" (current: {current_usage})"
            extra_data['current_usage'] = current_usage
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class UserVerificationRequiredException(AdNetworkException):
    """
    Exception raised when user verification is required
    """
    default_detail = 'User verification required'
    default_code = 'user_verification_required'
    status_code = status.HTTP_403_FORBIDDEN
    
    def __init__(self, verification_type=None, **kwargs):
        if verification_type:
            detail = f"User verification required: {verification_type}"
            extra_data = {'verification_type': verification_type}
        else:
            detail = self.default_detail
            extra_data = {}
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


class GeoRestrictionException(AdNetworkException):
    """
    Exception raised when user is geo-restricted
    """
    default_detail = 'Access restricted by geographic location'
    default_code = 'geo_restricted'
    status_code = status.HTTP_403_FORBIDDEN
    
    def __init__(self, user_country=None, allowed_countries=None, **kwargs):
        if user_country:
            detail = f"Access from country '{user_country}' is not allowed"
            extra_data = {
                'user_country': user_country,
                'allowed_countries': allowed_countries or []
            }
        else:
            detail = self.default_detail
            extra_data = {}
        
        super().__init__(
            detail=detail,
            extra_data=extra_data,
            **kwargs
        )


# ==================== EXCEPTION HANDLERS ====================

def handle_ad_network_exception(exc, context=None):
    """
    Custom exception handler for ad networks exceptions
    """
    if isinstance(exc, AdNetworkException):
        response_data = {
            'error': exc.code,
            'message': exc.detail,
            'status_code': exc.status_code
        }
        
        # Add extra data if available
        if exc.extra_data:
            response_data.update(exc.extra_data)
        
        # Add context if provided
        if context:
            response_data['context'] = context
        
        logger.warning(
            f"AdNetworkException handled: {exc.detail}",
            extra={
                'exception_type': exc.__class__.__name__,
                'code': exc.code,
                'detail': exc.detail,
                'extra_data': exc.extra_data,
                'context': context
            }
        )
        
        return response_data
    
    # For other exceptions, return standard error
    return {
        'error': 'internal_error',
        'message': 'An internal error occurred',
        'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
    }


def log_exception(exc, request=None, user=None):
    """
    Log exception with context information
    """
    logger.error(
        f"Exception in ad networks: {str(exc)}",
        extra={
            'exception_type': exc.__class__.__name__,
            'exception_message': str(exc),
            'request_path': request.path if request else None,
            'request_method': request.method if request else None,
            'user_id': user.id if user else None,
            'user_email': user.email if user else None,
            'tenant_id': getattr(request, 'tenant_id', None) if request else None,
            'traceback': traceback.format_exc()
        }
    )


# ==================== EXCEPTION MIDDLEWARE ====================

class AdNetworkExceptionMiddleware:
    """
    Middleware to handle ad networks exceptions
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Process ad networks exceptions
        """
        from django.http import JsonResponse
        from rest_framework.response import Response
        
        if isinstance(exception, AdNetworkException):
            # Create error response
            error_data = handle_ad_network_exception(
                exception,
                context={
                    'request_path': request.path,
                    'request_method': request.method,
                    'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None
                }
            )
            
            # Log the exception
            log_exception(
                exception,
                request=request,
                user=getattr(request, 'user', None) if hasattr(request, 'user') else None
            )
            
            # Return JSON response
            if hasattr(request, 'accepted_renderer') or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
                return Response(
                    error_data,
                    status=exception.status_code,
                    content_type='application/json'
                )
            else:
                return JsonResponse(
                    error_data,
                    status=exception.status_code
                )
        
        # Let Django handle other exceptions
        return None


# ==================== CUSTOM VALIDATION ERRORS ====================

class AdNetworkValidationError(ValidationError):
    """
    Custom validation error for ad networks
    """
    
    def __init__(self, message, code=None, field=None):
        self.message = message
        self.code = code or 'validation_error'
        self.field = field
        
        # Create Django validation error format
        super().__init__(message)
    
    def to_dict(self):
        """Convert to dictionary format"""
        error_dict = {
            'message': self.message,
            'code': self.code
        }
        
        if self.field:
            error_dict['field'] = self.field
        
        return error_dict


class PayoutValidationError(AdNetworkValidationError):
    """
    Validation error for payout amounts
    """
    
    def __init__(self, message, amount=None, currency=None, **kwargs):
        self.amount = amount
        self.currency = currency
        
        if amount and currency:
            full_message = f"Payout validation error: {message} (amount: {amount} {currency})"
        else:
            full_message = f"Payout validation error: {message}"
        
        super().__init__(
            full_message,
            code='payout_validation_error',
            **kwargs
        )


class URLValidationError(AdNetworkValidationError):
    """
    Validation error for URLs
    """
    
    def __init__(self, message, url=None, **kwargs):
        self.url = url
        
        if url:
            full_message = f"URL validation error: {message} (URL: {url})"
        else:
            full_message = f"URL validation error: {message}"
        
        super().__init__(
            full_message,
            code='url_validation_error',
            **kwargs
        )


class ConversionValidationError(AdNetworkValidationError):
    """
    Validation error for conversion data
    """
    
    def __init__(self, message, field=None, conversion_id=None, **kwargs):
        self.conversion_id = conversion_id
        
        if conversion_id:
            full_message = f"Conversion validation error: {message} (conversion_id: {conversion_id})"
        else:
            full_message = f"Conversion validation error: {message}"
        
        super().__init__(
            full_message,
            code='conversion_validation_error',
            field=field,
            **kwargs
        )
