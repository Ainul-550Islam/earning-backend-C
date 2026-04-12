"""
API Endpoints URLs

This module defines URL patterns for API endpoint management with
enterprise-grade security, performance optimization, and comprehensive functionality
following industry standards from Postman, Swagger, and API Gateway.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from django.conf import settings
from django.urls.exceptions import NoReverseMatch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
import time
import logging

from .views import (
    APIEndpointViewSet,
    RESTEndpointViewSet,
    GraphQLEndpointViewSet,
    WebSocketEndpointViewSet,
    APIDocumentationViewSet,
    APIVersioningViewSet,
    APIAuthenticationViewSet,
    APIRateLimitingViewSet
)

# Create router for API endpoints with optimized routing
router = DefaultRouter()
router.register(r'endpoints', APIEndpointViewSet, basename='api-endpoint')
router.register(r'rest', RESTEndpointViewSet, basename='rest-endpoint')
router.register(r'graphql', GraphQLEndpointViewSet, basename='graphql-endpoint')
router.register(r'websocket', WebSocketEndpointViewSet, basename='websocket-endpoint')
router.register(r'documentation', APIDocumentationViewSet, basename='api-documentation')
router.register(r'versions', APIVersioningViewSet, basename='api-version')
router.register(r'authentication', APIAuthenticationViewSet, basename='api-authentication')
router.register(r'rate-limiting', APIRateLimitingViewSet, basename='api-rate-limiting')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # API Endpoint URLs
    path('endpoints/create/', APIEndpointViewSet.as_view({'post': 'create'}), name='api-endpoints-create'),
    path('endpoints/<uuid:pk>/update/', APIEndpointViewSet.as_view({'put': 'update'}), name='api-endpoints-update'),
    path('endpoints/<uuid:pk>/deploy/', APIEndpointViewSet.as_view({'post': 'deploy'}), name='api-endpoints-deploy'),
    path('endpoints/<uuid:pk>/metrics/', APIEndpointViewSet.as_view({'get': 'metrics'}), name='api-endpoints-metrics'),
    path('endpoints/<uuid:pk>/logs/', APIEndpointViewSet.as_view({'get': 'logs'}), name='api-endpoints-logs'),
    path('endpoints/list/', APIEndpointViewSet.as_view({'get': 'list'}), name='api-endpoints-list'),
    path('endpoints/test/', APIEndpointViewSet.as_view({'post': 'test'}), name='api-endpoints-test'),
    
    # REST Endpoint URLs
    path('rest/create/', RESTEndpointViewSet.as_view({'post': 'create'}), name='rest-endpoints-create'),
    path('rest/<uuid:pk>/update/', RESTEndpointViewSet.as_view({'put': 'update'}), name='rest-endpoints-update'),
    path('rest/<uuid:pk>/configure/', RESTEndpointViewSet.as_view({'post': 'configure'}), name='rest-endpoints-configure'),
    path('rest/<uuid:pk>/test/', RESTEndpointViewSet.as_view({'post': 'test'}), name='rest-endpoints-test'),
    
    # GraphQL Endpoint URLs
    path('graphql/create/', GraphQLEndpointViewSet.as_view({'post': 'create'}), name='graphql-endpoints-create'),
    path('graphql/<uuid:pk>/update/', GraphQLEndpointViewSet.as_view({'put': 'update'}), name='graphql-endpoints-update'),
    path('graphql/<uuid:pk>/schema/', GraphQLEndpointViewSet.as_view({'get': 'schema'}), name='graphql-endpoints-schema'),
    path('graphql/<uuid:pk>/playground/', GraphQLEndpointViewSet.as_view({'get': 'playground'}), name='graphql-endpoints-playground'),
    
    # WebSocket Endpoint URLs
    path('websocket/create/', WebSocketEndpointViewSet.as_view({'post': 'create'}), name='websocket-endpoints-create'),
    path('websocket/<uuid:pk>/update/', WebSocketEndpointViewSet.as_view({'put': 'update'}), name='websocket-endpoints-update'),
    path('websocket/<uuid:pk>/connections/', WebSocketEndpointViewSet.as_view({'get': 'connections'}), name='websocket-endpoints-connections'),
    path('websocket/<uuid:pk>/monitor/', WebSocketEndpointViewSet.as_view({'get': 'monitor'}), name='websocket-endpoints-monitor'),
    
    # API Documentation URLs
    path('documentation/generate/', APIDocumentationViewSet.as_view({'post': 'generate'}), name='api-documentation-generate'),
    path('documentation/<uuid:pk>/view/', APIDocumentationViewSet.as_view({'get': 'view'}), name='api-documentation-view'),
    path('documentation/<uuid:pk>/update/', APIDocumentationViewSet.as_view({'put': 'update'}), name='api-documentation-update'),
    path('documentation/<uuid:pk>/publish/', APIDocumentationViewSet.as_view({'post': 'publish'}), name='api-documentation-publish'),
    
    # API Versioning URLs
    path('versions/create/', APIVersioningViewSet.as_view({'post': 'create'}), name='api-versions-create'),
    path('versions/<uuid:pk>/activate/', APIVersioningViewSet.as_view({'post': 'activate'}), name='api-versions-activate'),
    path('versions/<uuid:pk>/deprecate/', APIVersioningViewSet.as_view({'post': 'deprecate'}), name='api-versions-deprecate'),
    path('versions/list/', APIVersioningViewSet.as_view({'get': 'list'}), name='api-versions-list'),
    
    # API Authentication URLs
    path('authentication/create-api-key/', APIAuthenticationViewSet.as_view({'post': 'create_api_key'}), name='api-authentication-create-api-key'),
    path('authentication/<uuid:pk>/revoke/', APIAuthenticationViewSet.as_view({'post': 'revoke'}), name='api-authentication-revoke'),
    path('authentication/<uuid:pk>/regenerate/', APIAuthenticationViewSet.as_view({'post': 'regenerate'}), name='api-authentication-regenerate'),
    path('authentication/list/', APIAuthenticationViewSet.as_view({'get': 'list'}), name='api-authentication-list'),
    
    # API Rate Limiting URLs
    path('rate-limiting/create/', APIRateLimitingViewSet.as_view({'post': 'create'}), name='api-rate-limiting-create'),
    path('rate-limiting/<uuid:pk>/update/', APIRateLimitingViewSet.as_view({'put': 'update'}), name='api-rate-limiting-update'),
    path('rate-limiting/<uuid:pk>/status/', APIRateLimitingViewSet.as_view({'get': 'status'}), name='api-rate-limiting-status'),
    path('rate-limiting/<uuid:pk>/reset/', APIRateLimitingViewSet.as_view({'post': 'reset'}), name='api-rate-limiting-reset'),
    
    # Real-time endpoints
    path('real-time/metrics/', APIEndpointViewSet.as_view({'get': 'real_time_metrics'}), name='real-time-metrics'),
    path('real-time/connections/', WebSocketEndpointViewSet.as_view({'get': 'real_time_connections'}), name='real-time-connections'),
    path('real-time/requests/', APIEndpointViewSet.as_view({'get': 'real_time_requests'}), name='real-time-requests'),
    
    # Configuration endpoints
    path('config/supported-methods/', APIEndpointViewSet.as_view({'get': 'supported_methods'}), name='config-supported-methods'),
    path('config/supported-formats/', APIEndpointViewSet.as_view({'get': 'supported_formats'}), name='config-supported-formats'),
    path('config/specified-protocols/', WebSocketEndpointViewSet.as_view({'get': 'supported_protocols'}), name='config-supported-protocols'),
    
    # Monitoring endpoints
    path('monitoring/health/', APIEndpointViewSet.as_view({'get': 'health_check'}), name='monitoring-health'),
    path('monitoring/performance/', APIEndpointViewSet.as_view({'get': 'performance_metrics'}), name='monitoring-performance'),
    path('monitoring/errors/', APIEndpointViewSet.as_view({'get': 'error_logs'}), name='monitoring-errors'),
    path('monitoring/alerts/', APIEndpointViewSet.as_view({'get': 'alerts'}), name='monitoring-alerts'),
    
    # Export endpoints
    path('export/endpoints/', APIEndpointViewSet.as_view({'post': 'export_endpoints'}), name='export-endpoints'),
    path('export/metrics/', APIEndpointViewSet.as_view({'post': 'export_metrics'}), name='export-metrics'),
    path('export/logs/', APIEndpointViewSet.as_view({'post': 'export_logs'}), name='export-logs'),
    path('export/documentation/', APIDocumentationViewSet.as_view({'post': 'export_documentation'}), name='export-documentation'),
    
    # Interactive endpoints
    path('interactive/playground/', GraphQLEndpointViewSet.as_view({'get': 'playground'}), name='interactive-playground'),
    path('interactive/tester/', APIEndpointViewSet.as_view({'get': 'tester'}), name='interactive-tester'),
    path('interactive/explorer/', APIEndpointViewSet.as_view({'get': 'explorer'}), name='interactive-explorer'),
]

# Export router for inclusion in main URLs
api_endpoints_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        path('debug/performance/', APIEndpointsURLConfig.debug_performance_view, name='api-endpoints-debug-performance'),
        path('debug/websockets/', APIEndpointsURLConfig.debug_websockets_view, name='api-endpoints-debug-websockets'),
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('api_endpoints_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'api_endpoints': 7,
            'rest_endpoints': 4,
            'graphql_endpoints': 4,
            'websocket_endpoints': 4,
            'documentation': 4,
            'versions': 4,
            'authentication': 4,
            'rate_limiting': 4,
            'real_time': 3,
            'config': 3,
            'monitoring': 4,
            'export': 4,
            'interactive': 3
        },
        'version': '1.0.0'
    }, timeout=3600)
except Exception:
    # Cache failure should not break URL configuration
    pass

# Security: Add URL validation middleware
class APIEndpointsURLValidator:
    """URL validator for API endpoints with security checks."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, request):
        """Validate URLs with comprehensive security checks."""
        try:
            start_time = time.time()
            
            # Security: Validate request path
            path = request.path_info
            
            # Check for suspicious patterns
            suspicious_patterns = [
                '../',  # Directory traversal
                '<script',  # Script injection
                'javascript:',  # JavaScript protocol
                'data:',  # Data protocol
                'file://',  # File protocol
                'ftp://',  # FTP protocol
                'php://',  # PHP wrapper
                'expect://',  # Expect wrapper
            ]
            
            for pattern in suspicious_patterns:
                if pattern in path.lower():
                    self.logger.warning(f"Suspicious URL pattern detected: {pattern} in {path}")
                    from django.http import HttpResponseBadRequest
                    return HttpResponseBadRequest("Invalid request path")
            
            # Security: Validate HTTP method
            allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
            if request.method not in allowed_methods:
                self.logger.warning(f"Invalid HTTP method: {request.method}")
                from django.http import HttpResponseNotAllowed
                return HttpResponseNotAllowed(allowed_methods)
            
            # Security: Rate limiting check
            if not self._check_rate_limit(request):
                self.logger.warning(f"Rate limit exceeded for IP: {self._get_client_ip(request)}")
                from django.http import HttpResponseTooManyRequests
                return HttpResponseTooManyRequests("Rate limit exceeded")
            
            # Security: Check for suspicious headers
            suspicious_headers = [
                'X-Forwarded-For',
                'X-Real-IP',
                'X-Originating-IP',
                'X-Cluster-Client-IP',
                'X-Remote-IP',
                'X-Remote-Addr'
            ]
            
            for header in suspicious_headers:
                if header in request.META:
                    header_value = request.META[header]
                    if self._is_suspicious_header_value(header_value):
                        self.logger.warning(f"Suspicious header detected: {header}={header_value}")
            
            # Process request
            response = self.get_response(request)
            
            # Performance: Log request time
            processing_time = time.time() - start_time
            response['X-Processing-Time'] = str(processing_time)
            
            # Security: Add security headers
            self._add_security_headers(response)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in URL validation: {str(e)}")
            # Security: Don't expose internal errors
            from django.http import HttpResponseServerError
            return HttpResponseServerError("Request validation failed")
    
    def _check_rate_limit(self, request) -> bool:
        """Check if request exceeds rate limits."""
        try:
            client_ip = self._get_client_ip(request)
            cache_key = f"api_endpoints_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 200 requests per minute for API endpoints
            if current_count >= 200:
                return False
            
            # Increment counter
            cache.set(cache_key, current_count + 1, timeout=60)  # 1 minute
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {str(e)}")
            return True  # Allow request on error
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address with security considerations."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        return ip
    
    def _is_suspicious_header_value(self, value: str) -> bool:
        """Check if header value is suspicious."""
        suspicious_patterns = [
            '../',  # Directory traversal
            '<script',  # Script injection
            'javascript:',  # JavaScript protocol
            'data:',  # Data protocol
        ]
        
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in suspicious_patterns)
    
    def _add_security_headers(self, response) -> None:
        """Add security headers to response."""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Content-Security-Policy'] = "default-src 'self'"
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Add API endpoints specific headers
        response['X-API-Endpoints-Version'] = '1.0.0'
        response['X-API-Endpoints-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 200 - cache.get(f"api_endpoints_rate_limit_{self._get_client_ip(None)}", 0)))


# Performance: Add response compression
class APIEndpointsResponseCompression:
    """Response compression for better performance."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Apply response compression."""
        response = self.get_response(request)
        
        # Compress JSON responses
        if (hasattr(response, 'content') and 
            len(response.content) > 1024 and  # Only compress larger responses
            'application/json' in response.get('Content-Type', '')):
            
            # Add compression headers
            response['Content-Encoding'] = 'gzip'
            response['Vary'] = 'Accept-Encoding'
        
        return response


# Security: Add CSRF protection
class APIEndpointsCSRFProtection:
    """CSRF protection for API endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Apply CSRF protection."""
        # Skip CSRF for safe methods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return self.get_response(request)
        
        # Skip CSRF for API endpoints that use token authentication
        if 'api/endpoints' in request.path:
            return self.get_response(request)
        
        # Apply CSRF protection for unsafe methods
        from django.middleware.csrf import CsrfViewMiddleware
        csrf_middleware = CsrfViewMiddleware(self.get_response)
        return csrf_middleware(request)


# Performance: Add caching headers
class APIEndpointsCachingHeaders:
    """Caching headers for API endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Add caching headers."""
        response = self.get_response(request)
        
        # Add caching headers for GET requests
        if request.method == 'GET':
            path = request.path
            
            # Cache for different durations based on endpoint
            if 'documentation' in path:
                response['Cache-Control'] = 'public, max-age=3600'  # 1 hour
            elif 'config' in path:
                response['Cache-Control'] = 'public, max-age=1800'  # 30 minutes
            elif 'monitoring' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'real-time' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            else:
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
        else:
            # No caching for POST/PUT/DELETE requests
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


# Performance: Database query optimization hints
class APIEndpointsDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'api_endpoint_created_at_idx',
                'api_endpoint_path_idx',
                'api_endpoint_method_idx',
                'api_endpoint_version_idx',
                'rest_endpoint_created_at_idx',
                'graphql_endpoint_created_at_idx',
                'websocket_endpoint_created_at_idx',
                'api_documentation_created_at_idx',
                'api_version_created_at_idx',
                'api_authentication_created_at_idx',
                'api_rate_limit_created_at_idx'
            ],
            'prefetch_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'select_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'annotate_fields': [
                'endpoint_type', 'method', 'version', 'status',
                'created_at', 'updated_at'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class APIEndpointsRateLimitConfig:
    """Rate limiting configuration for API endpoints."""
    
    RATE_LIMITS = {
        'api_endpoints_create': '50/hour',
        'api_endpoints_update': '100/hour',
        'api_endpoints_deploy': '20/hour',
        'api_endpoints_test': '200/hour',
        'rest_endpoints_create': '50/hour',
        'graphql_endpoints_create': '50/hour',
        'websocket_endpoints_create': '50/hour',
        'documentation_generate': '100/hour',
        'versions_create': '20/hour',
        'authentication_create_api_key': '100/hour',
        'rate_limiting_create': '50/hour',
        'real_time_metrics': '1000/hour',
        'config_supported_methods': '1000/hour',
        'monitoring_health': '1000/hour',
        'export_endpoints': '50/hour',
        'interactive_playground': '500/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '100/hour')


# Performance: API versioning
class APIEndpointsAPIVersioning:
    """API versioning for API endpoints."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/api-endpoints/{base_url.lstrip('/')}"
    
    @classmethod
    def get_version_from_request(cls, request) -> str:
        """Extract API version from request."""
        # Extract from URL path
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[1] == 'api':
            return path_parts[2]  # api/v1/...
        
        # Extract from headers
        return request.META.get('HTTP_API_VERSION', cls.CURRENT_VERSION)


# Security: Input validation patterns
class APIEndpointsInputValidation:
    """Input validation patterns for API endpoints."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'endpoint_type': r'^(rest|graphql|websocket|webhook)$',
        'method': r'^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$',
        'version': r'^v\d+(\.\d+)*$',
        'status': r'^(active|inactive|deprecated|maintenance)$',
        'response_format': r'^(json|xml|yaml|csv|text)$',
        'protocol': r'^(ws|wss)$',
        'message_format': r'^(json|xml|text|binary)$',
        'documentation_format': r'^(openapi|swagger|raml|api_blueprint)$',
        'auth_method': r'^(none|bearer|basic|api_key|oauth2|jwt)$',
        'permission': r'^(read|write|delete|admin|campaigns|analytics|billing|users|integrations|webhooks)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'http_status': r'^[1-5]\d{2}$',
    }
    
    @classmethod
    def validate_input(cls, input_type: str, value: str) -> bool:
        """Validate input against allowed patterns."""
        import re
        pattern = cls.PATTERNS.get(input_type)
        if not pattern:
            return False
        
        return bool(re.match(pattern, value))
    
    @classmethod
    def sanitize_input(cls, input_type: str, value: str) -> str:
        """Sanitize input value."""
        import re
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\'&]', '', value)
        
        # Apply type-specific sanitization
        if input_type in ['endpoint_type', 'method', 'status', 'response_format']:
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'version':
            # Normalize version format
            sanitized = re.sub(r'[^v0-9\.]', '', sanitized)
        
        return sanitized


# Performance: Response optimization
class APIEndpointsResponseOptimizer:
    """Response optimization for API endpoints."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'endpoints' in request_path:
            # Add API endpoints specific headers
            response['X-API-Endpoints-Cache'] = 'hit'
            response['X-API-Endpoints-Generated'] = str(time.time())
        elif 'rest' in request_path:
            # Add REST specific headers
            response['X-REST-Cache'] = 'hit'
            response['X-REST-Generated'] = str(time.time())
        elif 'graphql' in request_path:
            # Add GraphQL specific headers
            response['X-GraphQL-Cache'] = 'hit'
            response['X-GraphQL-Generated'] = str(time.time())
        elif 'websocket' in request_path:
            # Add WebSocket specific headers
            response['X-WebSocket-Cache'] = 'hit'
            response['X-WebSocket-Generated'] = str(time.time())
        elif 'documentation' in request_path:
            # Add documentation specific headers
            response['X-Documentation-Cache'] = 'hit'
            response['X-Documentation-Generated'] = str(time.time())
        elif 'authentication' in request_path:
            # Add authentication specific headers
            response['X-Authentication-Cache'] = 'hit'
            response['X-Authentication-Generated'] = str(time.time())
        elif 'rate-limiting' in request_path:
            # Add rate limiting specific headers
            response['X-RateLimiting-Cache'] = 'hit'
            response['X-RateLimiting-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class APIEndpointsAuditConfig:
    """Audit logging configuration for API endpoints."""
    
    AUDIT_EVENTS = [
        'endpoint_created',
        'endpoint_updated',
        'endpoint_deployed',
        'endpoint_tested',
        'rest_endpoint_created',
        'graphql_endpoint_created',
        'websocket_endpoint_created',
        'documentation_generated',
        'version_created',
        'api_key_created',
        'api_key_revoked',
        'rate_limit_created',
        'authentication_attempt',
        'rate_limit_exceeded',
        'endpoint_accessed',
    ]
    
    SENSITIVE_FIELDS = [
        'api_key',
        'handler',
        'request_validation',
        'response_serialization',
        'schema',
        'resolvers',
        'subscriptions',
        'authentication',
        'rate_limit',
        'settings',
        'request_body',
        'response_body',
        'headers',
        'query_params',
    ]
    
    @classmethod
    def should_audit(cls, event_type: str) -> bool:
        """Check if event should be audited."""
        return event_type in cls.AUDIT_EVENTS
    
    @classmethod
    def sanitize_for_audit(cls, data: dict) -> dict:
        """Sanitize data for audit logging."""
        sanitized = data.copy()
        
        for field in cls.SENSITIVE_FIELDS:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
        
        return sanitized


# Performance: Database connection pooling
class APIEndpointsDatabaseConfig:
    """Database configuration for API endpoints."""
    
    @staticmethod
    def get_connection_config():
        """Get optimized database connection configuration."""
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': settings.DATABASES['default']['NAME'],
            'USER': settings.DATABASES['default']['USER'],
            'PASSWORD': settings.DATABASES['default']['PASSWORD'],
            'HOST': settings.DATABASES['default']['HOST'],
            'PORT': settings.DATABASES['default']['PORT'],
            'OPTIONS': {
                'MAX_CONNS': 200,  # Increased for API endpoints
                'MIN_CONNS': 40,   # Increased for API endpoints
                'MAX_CONNS_PER_QUERY': 50,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class APIEndpointsCORSConfig:
    """CORS configuration for API endpoints."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://api.example.com',
        'https://docs.example.com',
        'https://playground.example.com',
    ]
    
    ALLOWED_METHODS = [
        'GET',
        'POST',
        'PUT',
        'PATCH',
        'DELETE',
        'OPTIONS',
        'HEAD',
    ]
    
    ALLOWED_HEADERS = [
        'Content-Type',
        'Authorization',
        'X-API-Version',
        'X-Request-ID',
        'X-Client-IP',
        'X-User-Agent',
        'X-Endpoint-ID',
        'X-GraphQL-Query',
        'X-WebSocket-Protocol',
        'X-Webhook-Signature',
        'X-Rate-Limit-Limit',
        'X-Rate-Limit-Remaining',
        'X-Rate-Limit-Reset',
    ]
    
    EXPOSED_HEADERS = [
        'X-API-Endpoints-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-API-Endpoints-Cache',
        'X-REST-Cache',
        'X-GraphQL-Cache',
        'X-WebSocket-Cache',
        'X-Documentation-Cache',
        'X-Authentication-Cache',
        'X-RateLimiting-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class APIEndpointsCacheConfig:
    """Caching configuration for API endpoints."""
    
    CACHE_KEYS = {
        'endpoint_data': 'endpoint_data_{endpoint_id}',
        'endpoint_metrics': 'endpoint_metrics_{endpoint_id}',
        'endpoint_logs': 'endpoint_logs_{endpoint_id}',
        'rest_config': 'rest_config_{endpoint_id}',
        'graphql_schema': 'graphql_schema_{endpoint_id}',
        'websocket_connections': 'websocket_connections_{endpoint_id}',
        'documentation_data': 'documentation_data_{doc_id}',
        'version_data': 'version_data_{version_id}',
        'api_key_data': 'api_key_data_{key_id}',
        'rate_limit_data': 'rate_limit_data_{limit_id}',
        'test_results': 'test_results_{test_id}',
        'deployment_status': 'deployment_status_{deployment_id}',
    }
    
    CACHE_TIMEOUTS = {
        'endpoint_data': 1800,      # 30 minutes
        'endpoint_metrics': 60,       # 1 minute
        'endpoint_logs': 300,        # 5 minutes
        'rest_config': 1800,        # 30 minutes
        'graphql_schema': 3600,      # 1 hour
        'websocket_connections': 30,   # 30 seconds
        'documentation_data': 3600,   # 1 hour
        'version_data': 7200,        # 2 hours
        'api_key_data': 3600,       # 1 hour
        'rate_limit_data': 60,       # 1 minute
        'test_results': 300,         # 5 minutes
        'deployment_status': 120,     # 2 minutes
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'api_endpoints_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 600)


# URL Configuration Class
class APIEndpointsURLConfig:
    """URL configuration class for API endpoints."""
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_performance_view(request):
        """Debug view for performance monitoring."""
        try:
            from django.core.cache import cache
            cache_stats = {
                'hits': getattr(cache, '_cache', {}).get('hits', 0),
                'misses': getattr(cache, '_cache', {}).get('misses', 0),
                'size': len(getattr(cache, '_cache', {})),
            }
            
            return JsonResponse({
                'cache_stats': cache_stats,
                'url_patterns': len(urlpatterns),
                'endpoints': [
                    'api_endpoints', 'rest_endpoints', 'graphql_endpoints', 'websocket_endpoints',
                    'documentation', 'versions', 'authentication', 'rate_limiting',
                    'real_time', 'config', 'monitoring', 'export', 'interactive'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'websocket_support': True,
                    'graphql_support': True
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_websockets_view(request):
        """Debug view for WebSocket monitoring."""
        try:
            from django.core.cache import cache
            
            # Get WebSocket cache keys
            websocket_keys = []
            if hasattr(cache, '_cache'):
                websocket_keys = [key for key in cache._cache.keys() if 'websocket' in str(key)]
            
            # Get WebSocket info
            websocket_info = {}
            for key in websocket_keys[:50]:  # Limit to 50 keys
                try:
                    websocket_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    websocket_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'websocket_keys': websocket_keys,
                'websocket_info': websocket_info,
                'total_keys': len(websocket_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Export configuration classes for use in settings
API_ENDPOINTS_CONFIG = {
    'URL_VALIDATOR': APIEndpointsURLValidator,
    'RESPONSE_COMPRESSION': APIEndpointsResponseCompression,
    'CSRF_PROTECTION': APIEndpointsCSRFProtection,
    'CACHING_HEADERS': APIEndpointsCachingHeaders,
    'DATABASE_HINTS': APIEndpointsDatabaseHints,
    'RATE_LIMIT_CONFIG': APIEndpointsRateLimitConfig,
    'API_VERSIONING': APIEndpointsAPIVersioning,
    'INPUT_VALIDATION': APIEndpointsInputValidation,
    'RESPONSE_OPTIMIZER': APIEndpointsResponseOptimizer,
    'AUDIT_CONFIG': APIEndpointsAuditConfig,
    'DATABASE_CONFIG': APIEndpointsDatabaseConfig,
    'CORS_CONFIG': APIEndpointsCORSConfig,
    'CACHE_CONFIG': APIEndpointsCacheConfig,
    'URL_CONFIG': APIEndpointsURLConfig,
}
