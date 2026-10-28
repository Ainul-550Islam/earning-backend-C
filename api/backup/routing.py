"""
🛣️ Backup Routing Module

This module provides comprehensive URL routing and request handling for the backup system.
It includes advanced routing patterns, middleware integration, request validation,
and response formatting to support a robust backup API architecture.

Features:
- Advanced URL routing patterns
- Request/response middleware
- API versioning support
- Rate limiting and throttling
- Request validation and sanitization
- Response formatting and caching
- Error handling and logging
- Security headers and CORS
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import path, include, re_path
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.middleware.csrf import get_token
from django.utils.deprecation import MiddlewareMixin
import json
import time

logger = logging.getLogger(__name__)


class RouteType(Enum):
    """Enumeration of route types."""
    API = "api"
    WEB = "web"
    ADMIN = "admin"
    WEBHOOK = "webhook"
    HEALTH = "health"
    METRICS = "metrics"


class HttpMethod(Enum):
    """Enumeration of HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ResponseFormat(Enum):
    """Enumeration of response formats."""
    JSON = "json"
    XML = "xml"
    HTML = "html"
    TEXT = "text"
    BINARY = "binary"


@dataclass
class RouteConfig:
    """Route configuration."""
    path: str
    handler: Callable
    methods: List[HttpMethod]
    route_type: RouteType
    name: Optional[str] = None
    middleware: List[Callable] = None
    auth_required: bool = True
    rate_limit: Optional[str] = None
    cache_timeout: Optional[int] = None
    version: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class RouteMatch:
    """Route match result."""
    route: RouteConfig
    params: Dict[str, Any]
    handler: Callable
    middleware: List[Callable]


class RouteRegistry:
    """Registry for managing routes."""
    
    def __init__(self):
        self.routes: List[RouteConfig] = []
        self.named_routes: Dict[str, RouteConfig] = {}
        self.versioned_routes: Dict[str, List[RouteConfig]] = {}
    
    def register(self, route: RouteConfig) -> None:
        """Register a route."""
        self.routes.append(route)
        
        if route.name:
            self.named_routes[route.name] = route
        
        if route.version:
            if route.version not in self.versioned_routes:
                self.versioned_routes[route.version] = []
            self.versioned_routes[route.version].append(route)
    
    def find_route(self, path: str, method: str, version: Optional[str] = None) -> Optional[RouteMatch]:
        """Find a matching route."""
        routes_to_check = self.routes
        
        if version and version in self.versioned_routes:
            routes_to_check = self.versioned_routes[version]
        
        for route in routes_to_check:
            if self._path_matches(route.path, path) and method in [m.value for m in route.methods]:
                params = self._extract_params(route.path, path)
                return RouteMatch(
                    route=route,
                    params=params,
                    handler=route.handler,
                    middleware=route.middleware or []
                )
        
        return None
    
    def _path_matches(self, route_path: str, request_path: str) -> bool:
        """Check if request path matches route pattern."""
        # Convert route path to regex pattern
        pattern = re.sub(r'<(\w+):(\w+)>', r'(?P<\2>[^/]+)', route_path)
        pattern = re.sub(r'<(\w+)>', r'(?P<\1>[^/]+)', pattern)
        pattern = f'^{pattern}$'
        
        return re.match(pattern, request_path) is not None
    
    def _extract_params(self, route_path: str, request_path: str) -> Dict[str, Any]:
        """Extract parameters from request path."""
        params = {}
        
        # Simple parameter extraction
        route_parts = route_path.strip('/').split('/')
        request_parts = request_path.strip('/').split('/')
        
        for i, route_part in enumerate(route_parts):
            if i < len(request_parts):
                # Check if this part is a parameter
                if route_part.startswith('<') and route_part.endswith('>'):
                    param_name = route_part[1:-1]
                    if ':' in param_name:
                        param_name = param_name.split(':')[1]
                    params[param_name] = request_parts[i]
        
        return params
    
    def get_routes_by_type(self, route_type: RouteType) -> List[RouteConfig]:
        """Get routes by type."""
        return [route for route in self.routes if route.route_type == route_type]
    
    def get_routes_by_version(self, version: str) -> List[RouteConfig]:
        """Get routes by version."""
        return self.versioned_routes.get(version, [])


class RequestValidator:
    """Request validation utility."""
    
    @staticmethod
    def validate_headers(request: HttpRequest) -> Dict[str, Any]:
        """Validate request headers."""
        errors = []
        warnings = []
        
        # Check required headers
        required_headers = getattr(settings, 'BACKUP_REQUIRED_HEADERS', [])
        for header in required_headers:
            if header not in request.headers:
                errors.append(f"Missing required header: {header}")
        
        # Check content type for POST/PUT requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.headers.get('Content-Type', '')
            if not content_type:
                warnings.append("Missing Content-Type header")
        
        # Check content length
        content_length = request.headers.get('Content-Length')
        if content_length:
            try:
                length = int(content_length)
                max_length = getattr(settings, 'BACKUP_MAX_REQUEST_SIZE', 100 * 1024 * 1024)  # 100MB
                if length > max_length:
                    errors.append(f"Request too large: {length} bytes (max: {max_length})")
            except ValueError:
                errors.append("Invalid Content-Length header")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    @staticmethod
    def validate_body(request: HttpRequest) -> Dict[str, Any]:
        """Validate request body."""
        errors = []
        warnings = []
        
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                # Try to parse JSON if content type indicates JSON
                content_type = request.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    if request.body:
                        json.loads(request.body)
                    else:
                        warnings.append("Empty request body with JSON content type")
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in request body: {e}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    @staticmethod
    def sanitize_input(data: Any) -> Any:
        """Sanitize input data."""
        if isinstance(data, str):
            # Basic XSS prevention
            data = re.sub(r'<script[^>]*>.*?</script>', '', data, flags=re.IGNORECASE | re.DOTALL)
            data = re.sub(r'<[^>]*>', '', data)
            data = data.strip()
        elif isinstance(data, dict):
            return {key: RequestValidator.sanitize_input(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [RequestValidator.sanitize_input(item) for item in data]
        
        return data


class ResponseFormatter:
    """Response formatting utility."""
    
    @staticmethod
    def format_response(data: Any, format_type: ResponseFormat = ResponseFormat.JSON,
                       status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> HttpResponse:
        """Format response based on format type."""
        headers = headers or {}
        
        if format_type == ResponseFormat.JSON:
            response_data = {
                'status': 'success' if 200 <= status_code < 300 else 'error',
                'data': data,
                'timestamp': timezone.now().isoformat(),
                'status_code': status_code
            }
            
            response = JsonResponse(response_data, status=status_code)
            response['Content-Type'] = 'application/json'
        
        elif format_type == ResponseFormat.XML:
            # Simple XML formatting
            xml_data = ResponseFormatter._dict_to_xml(data)
            response = HttpResponse(xml_data, content_type='application/xml', status=status_code)
        
        elif format_type == ResponseFormat.HTML:
            # Simple HTML formatting
            html_data = f"<html><body><pre>{json.dumps(data, indent=2)}</pre></body></html>"
            response = HttpResponse(html_data, content_type='text/html', status=status_code)
        
        elif format_type == ResponseFormat.TEXT:
            text_data = json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)
            response = HttpResponse(text_data, content_type='text/plain', status=status_code)
        
        elif format_type == ResponseFormat.BINARY:
            if isinstance(data, bytes):
                response = HttpResponse(data, status=status_code)
            else:
                response = HttpResponse(str(data).encode(), status=status_code)
        
        else:
            # Default to JSON
            response = JsonResponse(data, status=status_code)
        
        # Add custom headers
        for key, value in headers.items():
            response[key] = value
        
        return response
    
    @staticmethod
    def _dict_to_xml(data: Any, root: str = 'root') -> str:
        """Convert dictionary to XML."""
        if isinstance(data, dict):
            xml = f'<{root}>'
            for key, value in data.items():
                xml += ResponseFormatter._dict_to_xml(value, key)
            xml += f'</{root}>'
        elif isinstance(data, list):
            xml = ''
            for item in data:
                xml += ResponseFormatter._dict_to_xml(item, 'item')
        else:
            xml = f'<{root}>{str(data)}</{root}>'
        
        return xml


class SecurityMiddleware(MiddlewareMixin):
    """Security middleware for backup routes."""
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Process incoming request for security checks."""
        # Add security headers
        request.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Content-Security-Policy': "default-src 'self'"
        }
        
        # CSRF token for web routes
        if request.path.startswith('/web/'):
            request.csrf_token = get_token(request)
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Process response for security headers."""
        # Add security headers
        if hasattr(request, 'security_headers'):
            for header, value in request.security_headers.items():
                response[header] = value
        
        # CORS headers
        origin = request.headers.get('Origin')
        allowed_origins = getattr(settings, 'BACKUP_ALLOWED_ORIGINS', [])
        
        if origin in allowed_origins or '*' in allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
            response['Access-Control-Allow-Credentials'] = 'true'
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = getattr(settings, 'BACKUP_RATE_LIMITS', {
            'default': '100/hour',
            'api': '1000/hour',
            'upload': '10/minute'
        })
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check rate limits."""
        client_ip = self._get_client_ip(request)
        path = request.path
        method = request.method
        
        # Determine rate limit key
        rate_key = f"rate_limit:{client_ip}:{path}:{method}"
        
        # Find applicable rate limit
        rate_limit = self._find_rate_limit(path)
        
        if rate_limit and self._is_rate_limited(rate_key, rate_limit):
            return ResponseFormatter.format_response(
                {'error': 'Rate limit exceeded'},
                status_code=429
            )
        
        return None
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.headers.get('X-Forwarded-For')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.headers.get('X-Real-IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _find_rate_limit(self, path: str) -> Optional[str]:
        """Find applicable rate limit for path."""
        if '/api/upload' in path:
            return self.rate_limits.get('upload')
        elif path.startswith('/api/'):
            return self.rate_limits.get('api')
        else:
            return self.rate_limits.get('default')
    
    def _is_rate_limited(self, key: str, rate_limit: str) -> bool:
        """Check if rate limit is exceeded."""
        # Simple rate limiting implementation
        # In production, use Redis or similar
        try:
            count, period = rate_limit.split('/')
            max_requests = int(count)
            
            if period == 'minute':
                window = 60
            elif period == 'hour':
                window = 3600
            elif period == 'day':
                window = 86400
            else:
                window = 3600  # Default to hour
            
            current_time = int(time.time())
            window_start = current_time - (current_time % window)
            window_key = f"{key}:{window_start}"
            
            # This would use Redis in production
            from django.core.cache import cache
            current_count = cache.get(window_key, 0)
            
            if current_count >= max_requests:
                return True
            
            cache.set(window_key, current_count + 1, window)
            return False
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return False


class BackupRouter:
    """Main backup router with advanced routing capabilities."""
    
    def __init__(self):
        self.registry = RouteRegistry()
        self.validator = RequestValidator()
        self.formatter = ResponseFormatter()
        self._setup_default_routes()
    
    def _setup_default_routes(self) -> None:
        """Setup default routes."""
        # API routes
        self.register(RouteConfig(
            path='api/v1/backups/',
            handler=self._handle_backups_list,
            methods=[HttpMethod.GET, HttpMethod.POST],
            route_type=RouteType.API,
            name='backups_list',
            version='v1'
        ))
        
        self.register(RouteConfig(
            path='api/v1/backups/<uuid:backup_id>/',
            handler=self._handle_backup_detail,
            methods=[HttpMethod.GET, HttpMethod.PUT, HttpMethod.DELETE],
            route_type=RouteType.API,
            name='backup_detail',
            version='v1'
        ))
        
        self.register(RouteConfig(
            path='api/v1/backups/<uuid:backup_id>/restore/',
            handler=self._handle_backup_restore,
            methods=[HttpMethod.POST],
            route_type=RouteType.API,
            name='backup_restore',
            version='v1'
        ))
        
        self.register(RouteConfig(
            path='api/v1/backups/<uuid:backup_id>/verify/',
            handler=self._handle_backup_verify,
            methods=[HttpMethod.POST],
            route_type=RouteType.API,
            name='backup_verify',
            version='v1'
        ))
        
        self.register(RouteConfig(
            path='api/v1/schedules/',
            handler=self._handle_schedules_list,
            methods=[HttpMethod.GET, HttpMethod.POST],
            route_type=RouteType.API,
            name='schedules_list',
            version='v1'
        ))
        
        self.register(RouteConfig(
            path='api/v1/schedules/<uuid:schedule_id>/',
            handler=self._handle_schedule_detail,
            methods=[HttpMethod.GET, HttpMethod.PUT, HttpMethod.DELETE],
            route_type=RouteType.API,
            name='schedule_detail',
            version='v1'
        ))
        
        # Health check routes
        self.register(RouteConfig(
            path='health/',
            handler=self._handle_health_check,
            methods=[HttpMethod.GET],
            route_type=RouteType.HEALTH,
            name='health_check',
            auth_required=False
        ))
        
        self.register(RouteConfig(
            path='health/detailed/',
            handler=self._handle_detailed_health,
            methods=[HttpMethod.GET],
            route_type=RouteType.HEALTH,
            name='detailed_health',
            auth_required=False
        ))
        
        # Metrics routes
        self.register(RouteConfig(
            path='metrics/',
            handler=self._handle_metrics,
            methods=[HttpMethod.GET],
            route_type=RouteType.METRICS,
            name='metrics',
            auth_required=True
        ))
        
        # Webhook routes
        self.register(RouteConfig(
            path='webhooks/backup/',
            handler=self._handle_backup_webhook,
            methods=[HttpMethod.POST],
            route_type=RouteType.WEBHOOK,
            name='backup_webhook',
            auth_required=False
        ))
    
    def register(self, route: RouteConfig) -> None:
        """Register a route."""
        self.registry.register(route)
    
    def route(self, request: HttpRequest) -> HttpResponse:
        """Route a request to the appropriate handler."""
        start_time = time.time()
        
        try:
            # Extract version from URL or headers
            version = self._extract_version(request)
            
            # Find matching route
            match = self.registry.find_route(request.path, request.method, version)
            
            if not match:
                return self.formatter.format_response(
                    {'error': 'Route not found'},
                    status_code=404
                )
            
            # Validate request
            header_validation = self.validator.validate_headers(request)
            body_validation = self.validator.validate_body(request)
            
            if not header_validation['valid'] or not body_validation['valid']:
                errors = header_validation['errors'] + body_validation['errors']
                return self.formatter.format_response(
                    {'error': 'Validation failed', 'details': errors},
                    status_code=400
                )
            
            # Check authentication if required
            if match.route.auth_required:
                if not self._authenticate_request(request):
                    return self.formatter.format_response(
                        {'error': 'Authentication required'},
                        status_code=401
                    )
            
            # Apply middleware
            for middleware in match.middleware:
                result = middleware(request)
                if isinstance(result, HttpResponse):
                    return result
            
            # Call handler
            response = match.handler(request, **match.params)
            
            # Add processing time header
            processing_time = (time.time() - start_time) * 1000
            response['X-Processing-Time'] = f"{processing_time:.2f}ms"
            
            return response
            
        except Exception as e:
            logger.error(f"Routing error: {e}")
            return self.formatter.format_response(
                {'error': 'Internal server error'},
                status_code=500
            )
    
    def _extract_version(self, request: HttpRequest) -> Optional[str]:
        """Extract API version from request."""
        # Check URL path
        if '/api/v' in request.path:
            match = re.search(r'/api/v(\d+)/', request.path)
            if match:
                return f"v{match.group(1)}"
        
        # Check headers
        version = request.headers.get('API-Version')
        if version:
            return version
        
        # Check query parameters
        version = request.GET.get('version')
        if version:
            return version
        
        return None
    
    def _authenticate_request(self, request: HttpRequest) -> bool:
        """Authenticate request."""
        # Check for API key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return self._validate_api_key(api_key)
        
        # Check for JWT token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            return self._validate_jwt_token(token)
        
        # Check session authentication for web routes
        if request.path.startswith('/web/'):
            return request.user.is_authenticated
        
        return False
    
    def _validate_api_key(self, api_key: str) -> bool:
        """Validate API key."""
        # This would integrate with your API key management system
        valid_keys = getattr(settings, 'BACKUP_API_KEYS', [])
        return api_key in valid_keys
    
    def _validate_jwt_token(self, token: str) -> bool:
        """Validate JWT token."""
        # This would integrate with your JWT validation system
        try:
            import jwt
            secret_key = getattr(settings, 'JWT_SECRET_KEY', 'default-secret')
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return True
        except:
            return False
    
    # Route handlers
    def _handle_backups_list(self, request: HttpRequest, **kwargs) -> HttpResponse:
        """Handle backups list endpoint."""
        from .views import BackupViewSet
        
        viewset = BackupViewSet()
        if request.method == 'GET':
            return viewset.list(request)
        elif request.method == 'POST':
            return viewset.create(request)
        
        return self.formatter.format_response(
            {'error': 'Method not allowed'},
            status_code=405
        )
    
    def _handle_backup_detail(self, request: HttpRequest, backup_id: str, **kwargs) -> HttpResponse:
        """Handle backup detail endpoint."""
        from .views import BackupViewSet
        
        viewset = BackupViewSet()
        kwargs['pk'] = backup_id
        
        if request.method == 'GET':
            return viewset.retrieve(request, **kwargs)
        elif request.method == 'PUT':
            return viewset.update(request, **kwargs)
        elif request.method == 'DELETE':
            return viewset.destroy(request, **kwargs)
        
        return self.formatter.format_response(
            {'error': 'Method not allowed'},
            status_code=405
        )
    
    def _handle_backup_restore(self, request: HttpRequest, backup_id: str, **kwargs) -> HttpResponse:
        """Handle backup restore endpoint."""
        # This would integrate with your restore functionality
        return self.formatter.format_response(
            {'message': f'Restore initiated for backup {backup_id}'},
            status_code=202
        )
    
    def _handle_backup_verify(self, request: HttpRequest, backup_id: str, **kwargs) -> HttpResponse:
        """Handle backup verification endpoint."""
        # This would integrate with your verification functionality
        return self.formatter.format_response(
            {'message': f'Verification initiated for backup {backup_id}'},
            status_code=202
        )
    
    def _handle_schedules_list(self, request: HttpRequest, **kwargs) -> HttpResponse:
        """Handle schedules list endpoint."""
        from .views import BackupScheduleViewSet
        
        viewset = BackupScheduleViewSet()
        if request.method == 'GET':
            return viewset.list(request)
        elif request.method == 'POST':
            return viewset.create(request)
        
        return self.formatter.format_response(
            {'error': 'Method not allowed'},
            status_code=405
        )
    
    def _handle_schedule_detail(self, request: HttpRequest, schedule_id: str, **kwargs) -> HttpResponse:
        """Handle schedule detail endpoint."""
        from .views import BackupScheduleViewSet
        
        viewset = BackupScheduleViewSet()
        kwargs['pk'] = schedule_id
        
        if request.method == 'GET':
            return viewset.retrieve(request, **kwargs)
        elif request.method == 'PUT':
            return viewset.update(request, **kwargs)
        elif request.method == 'DELETE':
            return viewset.destroy(request, **kwargs)
        
        return self.formatter.format_response(
            {'error': 'Method not allowed'},
            status_code=405
        )
    
    def _handle_health_check(self, request: HttpRequest, **kwargs) -> HttpResponse:
        """Handle basic health check."""
        from .monitoring import get_backup_monitor
        
        monitor = get_backup_monitor()
        health_status = monitor.get_system_health()
        
        is_healthy = health_status.get('overall_status') == 'healthy'
        status_code = 200 if is_healthy else 503
        
        return self.formatter.format_response(
            {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'version': getattr(settings, 'BACKUP_VERSION', '1.0.0')
            },
            status_code=status_code
        )
    
    def _handle_detailed_health(self, request: HttpRequest, **kwargs) -> HttpResponse:
        """Handle detailed health check."""
        from .monitoring import get_backup_monitor
        
        monitor = get_backup_monitor()
        health_status = monitor.get_system_health()
        
        return self.formatter.format_response(health_status)
    
    def _handle_metrics(self, request: HttpRequest, **kwargs) -> HttpResponse:
        """Handle metrics endpoint."""
        from .analytics import get_backup_analytics
        
        analytics = get_backup_analytics()
        metrics = analytics.get_system_metrics()
        
        return self.formatter.format_response(metrics)
    
    def _handle_backup_webhook(self, request: HttpRequest, **kwargs) -> HttpResponse:
        """Handle backup webhook."""
        # Process webhook payload
        try:
            payload = json.loads(request.body)
            # Process webhook logic here
            
            return self.formatter.format_response(
                {'status': 'webhook received'},
                status_code=200
            )
        except json.JSONDecodeError:
            return self.formatter.format_response(
                {'error': 'Invalid JSON payload'},
                status_code=400
            )
    
    def get_url_patterns(self) -> List:
        """Get Django URL patterns."""
        patterns = []
        
        for route in self.registry.routes:
            django_methods = []
            for method in route.methods:
                if method == HttpMethod.GET:
                    django_methods.append(require_http_methods(["GET"]))
                elif method == HttpMethod.POST:
                    django_methods.append(require_http_methods(["POST"]))
                elif method == HttpMethod.PUT:
                    django_methods.append(require_http_methods(["PUT"]))
                elif method == HttpMethod.DELETE:
                    django_methods.append(require_http_methods(["DELETE"]))
                elif method == HttpMethod.PATCH:
                    django_methods.append(require_http_methods(["PATCH"]))
            
            # Create URL pattern
            if django_methods:
                pattern_func = csrf_exempt(django_methods[0](route.handler))
                patterns.append(path(route.path, pattern_func, name=route.name))
            else:
                patterns.append(path(route.path, route.handler, name=route.name))
        
        return patterns


# Global router instance
_backup_router: Optional[BackupRouter] = None


def get_backup_router() -> BackupRouter:
    """Get the global backup router instance."""
    global _backup_router
    if _backup_router is None:
        _backup_router = BackupRouter()
    return _backup_router


def register_route(path: str, handler: Callable, methods: List[str],
                  route_type: str = 'api', name: Optional[str] = None,
                  auth_required: bool = True, **kwargs) -> None:
    """Register a new route."""
    router = get_backup_router()
    
    # Convert method strings to enum
    method_enums = []
    for method in methods:
        try:
            method_enums.append(HttpMethod(method.upper()))
        except ValueError:
            logger.warning(f"Invalid HTTP method: {method}")
    
    # Convert route type string to enum
    try:
        route_type_enum = RouteType(route_type.lower())
    except ValueError:
        route_type_enum = RouteType.API
    
    route = RouteConfig(
        path=path,
        handler=handler,
        methods=method_enums,
        route_type=route_type_enum,
        name=name,
        auth_required=auth_required,
        **kwargs
    )
    
    router.register(route)


def backup_route(path: str, methods: List[str], **kwargs):
    """Decorator for registering backup routes."""
    def decorator(handler):
        register_route(path, handler, methods, **kwargs)
        return handler
    return decorator


def api_route(path: str, methods: List[str], **kwargs):
    """Decorator for registering API routes."""
    kwargs.setdefault('route_type', 'api')
    return backup_route(path, methods, **kwargs)


def web_route(path: str, methods: List[str], **kwargs):
    """Decorator for registering web routes."""
    kwargs.setdefault('route_type', 'web')
    return backup_route(path, methods, **kwargs)


def webhook_route(path: str, methods: List[str], **kwargs):
    """Decorator for registering webhook routes."""
    kwargs.setdefault('route_type', 'webhook')
    kwargs.setdefault('auth_required', False)
    return backup_route(path, methods, **kwargs)


# Example route registrations
@api_route('api/v1/backups/search/', ['GET'])
def search_backups(request):
    """Search backups endpoint."""
    query = request.GET.get('q', '')
    # Implement search logic
    return JsonResponse({'query': query, 'results': []})


@api_route('api/v1/backups/export/', ['POST'])
def export_backups(request):
    """Export backups endpoint."""
    # Implement export logic
    return JsonResponse({'status': 'export initiated'})


@webhook_route('webhooks/external/backup/', ['POST'])
def external_backup_webhook(request):
    """External backup webhook."""
    # Process external webhook
    return JsonResponse({'status': 'received'})


# URL patterns for Django urls.py
def get_backup_urlpatterns():
    """Get backup URL patterns for Django."""
    router = get_backup_router()
    return router.get_url_patterns()
