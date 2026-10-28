"""
endpoint.py – API endpoint definitions and handlers for postback module.

Provides comprehensive endpoint functionality including:
- Custom API endpoints
- Request/response handling
- Endpoint decorators and middleware
- API versioning support
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime
from functools import wraps
from enum import Enum

from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .services import receive_postback
from .exceptions import PostbackException
from .serializers import PostbackLogSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class EndpointType(Enum):
    """Endpoint type enumeration."""
    API = "api"
    WEBHOOK = "webhook"
    ADMIN = "admin"
    PUBLIC = "public"


class EndpointMethod(Enum):
    """HTTP method enumeration."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class EndpointResponse:
    """
    Standardized response class for API endpoints.
    
    Provides consistent response formatting with status,
    data, and metadata.
    """
    
    def __init__(self, success: bool = True, data: Any = None, message: str = None, 
                 status_code: int = 200, headers: Dict[str, str] = None):
        self.success = success
        self.data = data
        self.message = message
        self.status_code = status_code
        self.headers = headers or {}
        self.timestamp = timezone.now()
    
    def to_json_response(self) -> JsonResponse:
        """Convert to Django JsonResponse."""
        response_data = {
            'success': self.success,
            'data': self.data,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
        }
        
        response = JsonResponse(response_data, status=self.status_code)
        
        # Add headers
        for header, value in self.headers.items():
            response[header] = value
        
        return response
    
    @classmethod
    def success(cls, data: Any = None, message: str = None, headers: Dict[str, str] = None) -> 'EndpointResponse':
        """Create success response."""
        return cls(success=True, data=data, message=message, status_code=200, headers=headers)
    
    @classmethod
    def created(cls, data: Any = None, message: str = None, headers: Dict[str, str] = None) -> 'EndpointResponse':
        """Create created response."""
        return cls(success=True, data=data, message=message, status_code=201, headers=headers)
    
    @classmethod
    def error(cls, message: str, data: Any = None, status_code: int = 400, headers: Dict[str, str] = None) -> 'EndpointResponse':
        """Create error response."""
        return cls(success=False, data=data, message=message, status_code=status_code, headers=headers)
    
    @classmethod
    def not_found(cls, message: str = "Resource not found") -> 'EndpointResponse':
        """Create not found response."""
        return cls.error(message=message, status_code=404)
    
    @classmethod
    def unauthorized(cls, message: str = "Unauthorized") -> 'EndpointResponse':
        """Create unauthorized response."""
        return cls.error(message=message, status_code=401)
    
    @classmethod
    def forbidden(cls, message: str = "Forbidden") -> 'EndpointResponse':
        """Create forbidden response."""
        return cls.error(message=message, status_code=403)
    
    @classmethod
    def server_error(cls, message: str = "Internal server error") -> 'EndpointResponse':
        """Create server error response."""
        return cls.error(message=message, status_code=500)


class EndpointDecorator:
    """
    Decorator class for endpoint functionality.
    
    Provides common decorators for authentication,
    validation, logging, and performance monitoring.
    """
    
    @staticmethod
    def require_authentication():
        """Decorator to require user authentication."""
        def decorator(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                if not request.user.is_authenticated:
                    return EndpointResponse.unauthorized().to_json_response()
                return func(request, *args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def require_staff():
        """Decorator to require staff permissions."""
        def decorator(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                if not request.user.is_authenticated or not request.user.is_staff:
                    return EndpointResponse.forbidden().to_json_response()
                return func(request, *args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def log_endpoint(endpoint_name: str = None):
        """Decorator to log endpoint calls."""
        def decorator(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                name = endpoint_name or f"{func.__module__}.{func.__name__}"
                start_time = timezone.now()
                
                logger.info(f"Endpoint called: {name} - {request.method} {request.path}")
                
                try:
                    result = func(request, *args, **kwargs)
                    
                    execution_time = (timezone.now() - start_time).total_seconds()
                    logger.info(f"Endpoint completed: {name} in {execution_time:.3f}s")
                    
                    return result
                    
                except Exception as e:
                    execution_time = (timezone.now() - start_time).total_seconds()
                    logger.error(f"Endpoint failed: {name} in {execution_time:.3f}s - {str(e)}")
                    raise
            
            return wrapper
        return decorator
    
    @staticmethod
    def rate_limit(rate: str = "100/hour"):
        """Decorator for rate limiting."""
        def decorator(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                # Simple rate limiting implementation
                client_ip = request.META.get('REMOTE_ADDR', 'unknown')
                cache_key = f"rate_limit_{client_ip}_{func.__name__}"
                
                current_count = cache.get(cache_key, 0)
                
                if current_count >= 100:  # Simple limit
                    return EndpointResponse.error(
                        message="Rate limit exceeded",
                        status_code=429
                    ).to_json_response()
                
                # Increment counter
                cache.set(cache_key, current_count + 1, timeout=3600)  # 1 hour
                
                return func(request, *args, **kwargs)
            
            return wrapper
        return decorator
    
    @staticmethod
    def validate_content_type(allowed_types: List[str] = None):
        """Decorator to validate content type."""
        def decorator(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                allowed = allowed_types or ['application/json']
                content_type = request.content_type
                
                if content_type not in allowed:
                    return EndpointResponse.error(
                        message=f"Content type {content_type} not allowed",
                        status_code=415
                    ).to_json_response()
                
                return func(request, *args, **kwargs)
            
            return wrapper
        return decorator


class BaseEndpoint:
    """
    Base class for API endpoints.
    
    Provides common functionality for endpoint handling
    including request parsing, validation, and response formatting.
    """
    
    def __init__(self, endpoint_type: EndpointType = EndpointType.API):
        self.endpoint_type = endpoint_type
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def parse_request_data(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Parse request data based on content type.
        
        Args:
            request: HTTP request
            
        Returns:
            Parsed request data
        """
        try:
            if request.content_type == 'application/json':
                return request.json() if hasattr(request, 'json') else {}
            elif request.content_type == 'application/x-www-form-urlencoded':
                return dict(request.POST)
            elif request.content_type == 'multipart/form-data':
                data = dict(request.POST)
                data['files'] = dict(request.FILES)
                return data
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Error parsing request data: {str(e)}")
            return {}
    
    def validate_request_data(self, data: Dict[str, Any], schema: Dict[str, Any] = None) -> bool:
        """
        Validate request data against schema.
        
        Args:
            data: Request data to validate
            schema: Validation schema
            
        Returns:
            True if data is valid
        """
        if not schema:
            return True
        
        # Simple validation implementation
        required_fields = schema.get('required', [])
        
        for field in required_fields:
            if field not in data or data[field] is None:
                return False
        
        return True
    
    def handle_request(self, request: HttpRequest, **kwargs) -> EndpointResponse:
        """
        Handle incoming request.
        
        Args:
            request: HTTP request
            **kwargs: Additional keyword arguments
            
        Returns:
            Endpoint response
        """
        try:
            # Parse request data
            data = self.parse_request_data(request)
            
            # Validate request
            if not self.validate_request_data(data):
                return EndpointResponse.error("Invalid request data")
            
            # Process request based on method
            if request.method == 'GET':
                return self.handle_get(request, data, **kwargs)
            elif request.method == 'POST':
                return self.handle_post(request, data, **kwargs)
            elif request.method == 'PUT':
                return self.handle_put(request, data, **kwargs)
            elif request.method == 'DELETE':
                return self.handle_delete(request, data, **kwargs)
            else:
                return EndpointResponse.error(f"Method {request.method} not allowed", status_code=405)
        
        except PostbackException as e:
            self.logger.error(f"Postback exception in endpoint: {str(e)}")
            return EndpointResponse.error(str(e), status_code=400)
        except Exception as e:
            self.logger.error(f"Unexpected error in endpoint: {str(e)}")
            return EndpointResponse.server_error()
    
    def handle_get(self, request: HttpRequest, data: Dict[str, Any], **kwargs) -> EndpointResponse:
        """Handle GET request."""
        return EndpointResponse.error("GET method not implemented")
    
    def handle_post(self, request: HttpRequest, data: Dict[str, Any], **kwargs) -> EndpointResponse:
        """Handle POST request."""
        return EndpointResponse.error("POST method not implemented")
    
    def handle_put(self, request: HttpRequest, data: Dict[str, Any], **kwargs) -> EndpointResponse:
        """Handle PUT request."""
        return EndpointResponse.error("PUT method not implemented")
    
    def handle_delete(self, request: HttpRequest, data: Dict[str, Any], **kwargs) -> EndpointResponse:
        """Handle DELETE request."""
        return EndpointResponse.error("DELETE method not implemented")


class PostbackEndpoint(BaseEndpoint):
    """
    Endpoint for handling postback requests.
    
    Provides specialized functionality for receiving,
    processing, and responding to postback data.
    """
    
    def __init__(self):
        super().__init__(EndpointType.WEBHOOK)
    
    def handle_post(self, request: HttpRequest, data: Dict[str, Any], **kwargs) -> EndpointResponse:
        """
        Handle postback POST request.
        
        Args:
            request: HTTP request
            data: Request data
            **kwargs: Additional arguments
            
        Returns:
            Endpoint response
        """
        try:
            # Extract postback data
            network_key = data.get('network_key')
            lead_id = data.get('lead_id')
            
            if not network_key or not lead_id:
                return EndpointResponse.error("Missing required fields: network_key, lead_id")
            
            # Get network configuration
            try:
                network_config = NetworkPostbackConfig.objects.get(network_key=network_key, is_active=True)
            except NetworkPostbackConfig.DoesNotExist:
                return EndpointResponse.error(f"Network {network_key} not found or inactive")
            
            # Process postback
            result = receive_postback(data, network_config)
            
            if result.get('success'):
                return EndpointResponse.success(
                    data={
                        'postback_id': result.get('postback_id'),
                        'status': result.get('status'),
                        'payout': result.get('payout'),
                        'message': result.get('message', 'Postback processed successfully')
                    }
                )
            else:
                return EndpointResponse.error(
                    message=result.get('error', 'Postback processing failed'),
                    status_code=400
                )
        
        except Exception as e:
            self.logger.error(f"Error processing postback: {str(e)}")
            return EndpointResponse.server_error()


class AnalyticsEndpoint(BaseEndpoint):
    """
    Endpoint for handling analytics requests.
    
    Provides functionality for retrieving analytics data,
    generating reports, and metrics calculation.
    """
    
    def __init__(self):
        super().__init__(EndpointType.API)
    
    def handle_get(self, request: HttpRequest, data: Dict[str, Any], **kwargs) -> EndpointResponse:
        """
        Handle analytics GET request.
        
        Args:
            request: HTTP request
            data: Request data
            **kwargs: Additional arguments
            
        Returns:
            Endpoint response
        """
        try:
            # Get query parameters
            network_key = request.GET.get('network_key')
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            
            # Build queryset
            queryset = PostbackInsight.objects.all()
            
            if network_key:
                queryset = queryset.filter(network__network_key=network_key)
            
            if date_from:
                try:
                    date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00')).date()
                    queryset = queryset.filter(date__gte=date_from)
                except ValueError:
                    pass
            
            if date_to:
                try:
                    date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00')).date()
                    queryset = queryset.filter(date__lte=date_to)
                except ValueError:
                    pass
            
            # Serialize data
            insights = queryset.order_by('-date')
            data = []
            
            for insight in insights:
                data.append({
                    'date': insight.date.isoformat(),
                    'network_key': insight.network.network_key,
                    'received_count': insight.received_count,
                    'rewarded_count': insight.rewarded_count,
                    'rejected_count': insight.rejected_count,
                    'health_score': float(insight.health_score),
                    'total_payout': float(insight.total_payout),
                    'anomaly_detected': insight.anomaly_detected,
                })
            
            return EndpointResponse.success(data=data)
        
        except Exception as e:
            self.logger.error(f"Error retrieving analytics: {str(e)}")
            return EndpointResponse.server_error()


class HealthEndpoint(BaseEndpoint):
    """
    Endpoint for health checks.
    
    Provides system health information and status.
    """
    
    def __init__(self):
        super().__init__(EndpointType.PUBLIC)
    
    def handle_get(self, request: HttpRequest, data: Dict[str, Any], **kwargs) -> EndpointResponse:
        """
        Handle health check GET request.
        
        Args:
            request: HTTP request
            data: Request data
            **kwargs: Additional arguments
            
        Returns:
            Endpoint response
        """
        try:
            # Check system health
            health_data = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'version': '1.0.0',
                'checks': {
                    'database': self._check_database(),
                    'cache': self._check_cache(),
                    'services': self._check_services(),
                }
            }
            
            # Determine overall health
            all_healthy = all(check['status'] == 'healthy' for check in health_data['checks'].values())
            health_data['status'] = 'healthy' if all_healthy else 'unhealthy'
            
            status_code = 200 if all_healthy else 503
            
            return EndpointResponse.success(data=health_data, status_code=status_code)
        
        except Exception as e:
            self.logger.error(f"Error in health check: {str(e)}")
            return EndpointResponse.server_error()
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return {'status': 'healthy', 'message': 'Database connection successful'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': f'Database error: {str(e)}'}
    
    def _check_cache(self) -> Dict[str, Any]:
        """Check cache connectivity."""
        try:
            cache.set('health_check', 'ok', timeout=10)
            cache_value = cache.get('health_check')
            
            if cache_value == 'ok':
                return {'status': 'healthy', 'message': 'Cache connection successful'}
            else:
                return {'status': 'unhealthy', 'message': 'Cache connection failed'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': f'Cache error: {str(e)}'}
    
    def _check_services(self) -> Dict[str, Any]:
        """Check external services."""
        try:
            # Check if postback services are available
            from .services import receive_postback
            
            return {'status': 'healthy', 'message': 'Services available'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': f'Services error: {str(e)}'}


# Endpoint instances
postback_endpoint = PostbackEndpoint()
analytics_endpoint = AnalyticsEndpoint()
health_endpoint = HealthEndpoint()


# Django view functions
@csrf_exempt
@require_http_methods(["POST"])
@EndpointDecorator.log_endpoint("postback_webhook")
@EndpointDecorator.validate_content_type(['application/json', 'application/x-www-form-urlencoded'])
def postback_webhook(request: HttpRequest) -> JsonResponse:
    """
    Postback webhook endpoint.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    return postback_endpoint.handle_request(request).to_json_response()


@require_http_methods(["GET"])
@EndpointDecorator.require_authentication()
@EndpointDecorator.log_endpoint("analytics_api")
def analytics_api(request: HttpRequest) -> JsonResponse:
    """
    Analytics API endpoint.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    return analytics_endpoint.handle_request(request).to_json_response()


@require_http_methods(["GET"])
@EndpointDecorator.log_endpoint("health_check")
def health_check(request: HttpRequest) -> JsonResponse:
    """
    Health check endpoint.
    
    Args:
        request: HTTP request
        
    Returns:
        JSON response
    """
    return health_endpoint.handle_request(request).to_json_response()


# Endpoint utilities
def create_endpoint_response(success: bool, data: Any = None, message: str = None, 
                          status_code: int = 200) -> JsonResponse:
    """
    Create standardized endpoint response.
    
    Args:
        success: Success flag
        data: Response data
        message: Response message
        status_code: HTTP status code
        
    Returns:
        JSON response
    """
    response = EndpointResponse(success=success, data=data, message=message, status_code=status_code)
    return response.to_json_response()


def handle_endpoint_error(error: Exception, endpoint_name: str = None) -> JsonResponse:
    """
    Handle endpoint errors consistently.
    
    Args:
        error: Exception that occurred
        endpoint_name: Name of the endpoint
        
    Returns:
        JSON response
    """
    logger.error(f"Error in endpoint {endpoint_name or 'unknown'}: {str(error)}")
    
    if isinstance(error, PostbackException):
        return EndpointResponse.error(str(error), status_code=400).to_json_response()
    else:
        return EndpointResponse.server_error().to_json_response()


# Endpoint registration
def register_endpoint(url_pattern: str, view_func: Callable, name: str = None):
    """
    Register an endpoint for URL routing.
    
    Args:
        url_pattern: URL pattern
        view_func: View function
        name: URL name
    """
    # This would typically be used in urls.py
    # Example: path('webhook/', postback_webhook, name='postback_webhook')
    pass


# Endpoint middleware
class EndpointMiddleware:
    """
    Middleware for endpoint processing.
    
    Provides common middleware functionality for all endpoints
    including logging, authentication, and request validation.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process request before view
        self._process_request(request)
        
        # Get response from view
        response = self.get_response(request)
        
        # Process response after view
        self._process_response(request, response)
        
        return response
    
    def _process_request(self, request):
        """Process incoming request."""
        # Add request timestamp
        request.endpoint_start_time = timezone.now()
        
        # Log request
        logger.info(f"Request: {request.method} {request.path}")
    
    def _process_response(self, request, response):
        """Process outgoing response."""
        # Calculate execution time
        if hasattr(request, 'endpoint_start_time'):
            execution_time = (timezone.now() - request.endpoint_start_time).total_seconds()
            response['X-Execution-Time'] = str(execution_time)
        
        # Log response
        logger.info(f"Response: {response.status_code} for {request.method} {request.path}")
