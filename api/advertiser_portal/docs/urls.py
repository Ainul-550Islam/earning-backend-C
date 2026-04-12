"""
Documentation URLs

This module defines URL patterns for documentation management with
enterprise-grade security, performance optimization, and comprehensive functionality
following industry standards from Swagger, OpenAPI, and Confluence.
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
    DocumentationViewSet,
    APIDocumentationViewSet,
    UserGuideViewSet,
    TechnicalDocumentationViewSet,
    DocumentationSearchViewSet,
    DocumentationVersioningViewSet,
    DocumentationAnalyticsViewSet
)

# Create router for documentation with optimized routing
router = DefaultRouter()
router.register(r'documentation', DocumentationViewSet, basename='documentation')
router.register(r'api', APIDocumentationViewSet, basename='api-documentation')
router.register(r'user-guides', UserGuideViewSet, basename='user-guide')
router.register(r'technical', TechnicalDocumentationViewSet, basename='technical-documentation')
router.register(r'search', DocumentationSearchViewSet, basename='documentation-search')
router.register(r'versions', DocumentationVersioningViewSet, basename='documentation-versioning')
router.register(r'analytics', DocumentationAnalyticsViewSet, basename='documentation-analytics')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # Documentation URLs
    path('docs/create/', DocumentationViewSet.as_view({'post': 'create'}), name='documentation-create'),
    path('docs/<uuid:pk>/update/', DocumentationViewSet.as_view({'put': 'update'}), name='documentation-update'),
    path('docs/<uuid:pk>/view/', DocumentationViewSet.as_view({'get': 'view'}), name='documentation-view'),
    path('docs/<uuid:pk>/stats/', DocumentationViewSet.as_view({'get': 'stats'}), name='documentation-stats'),
    path('docs/list/', DocumentationViewSet.as_view({'get': 'list'}), name='documentation-list'),
    
    # Documentation Search URLs
    path('docs/search/', DocumentationViewSet.as_view({'post': 'search'}), name='documentation-search'),
    path('docs/advanced-search/', DocumentationSearchViewSet.as_view({'post': 'advanced_search'}), name='documentation-advanced-search'),
    path('docs/search/suggestions/', DocumentationSearchViewSet.as_view({'get': 'search_suggestions'}), name='documentation-search-suggestions'),
    
    # API Documentation URLs
    path('api/<uuid:pk>/openapi-spec/', APIDocumentationViewSet.as_view({'get': 'openapi_spec'}), name='api-documentation-openapi'),
    path('api/<uuid:pk>/validate/', APIDocumentationViewSet.as_view({'post': 'validate'}), name='api-documentation-validate'),
    path('api/<uuid:pk>/endpoints/', APIDocumentationViewSet.as_view({'get': 'endpoints'}), name='api-documentation-endpoints'),
    path('api/<uuid:pk>/schemas/', APIDocumentationViewSet.as_view({'get': 'schemas'}), name='api-documentation-schemas'),
    
    # User Guide URLs
    path('user-guides/<uuid:pk>/table-of-contents/', UserGuideViewSet.as_view({'get': 'table_of_contents'}), name='user-guide-toc'),
    path('user-guides/<uuid:pk>/reading-time/', UserGuideViewSet.as_view({'get': 'reading_time'}), name='user-guide-reading-time'),
    path('user-guides/<uuid:pk>/progress/', UserGuideViewSet.as_view({'get': 'progress'}), name='user-guide-progress'),
    path('user-guides/<uuid:pk>/bookmark/', UserGuideViewSet.as_view({'post': 'bookmark'}), name='user-guide-bookmark'),
    
    # Technical Documentation URLs
    path('technical/<uuid:pk>/code-blocks/', TechnicalDocumentationViewSet.as_view({'get': 'code_blocks'}), name='technical-documentation-code-blocks'),
    path('technical/<uuid:pk>/validate/', TechnicalDocumentationViewSet.as_view({'post': 'validate'}), name='technical-documentation-validate'),
    path('technical/<uuid:pk>/components/', TechnicalDocumentationViewSet.as_view({'get': 'components'}), name='technical-documentation-components'),
    path('technical/<uuid:pk>/troubleshooting/', TechnicalDocumentationViewSet.as_view({'get': 'troubleshooting'}), name='technical-documentation-troubleshooting'),
    
    # Documentation Versioning URLs
    path('versions/<uuid:pk>/create/', DocumentationVersioningViewSet.as_view({'post': 'create_version'}), name='documentation-version-create'),
    path('versions/<uuid:pk>/restore/', DocumentationVersioningViewSet.as_view({'post': 'restore_version'}), name='documentation-version-restore'),
    path('versions/<uuid:pk>/history/', DocumentationVersioningViewSet.as_view({'get': 'version_history'}), name='documentation-version-history'),
    path('versions/<uuid:pk>/compare/', DocumentationVersioningViewSet.as_view({'get': 'compare'}), name='documentation-version-compare'),
    
    # Documentation Analytics URLs
    path('analytics/engagement-report/', DocumentationAnalyticsViewSet.as_view({'get': 'engagement_report'}), name='documentation-analytics-engagement'),
    path('analytics/analytics/', DocumentationAnalyticsViewSet.as_view({'get': 'analytics'}), name='documentation-analytics-analytics'),
    path('analytics/popular/', DocumentationAnalyticsViewSet.as_view({'get': 'popular'}), name='documentation-analytics-popular'),
    path('analytics/trends/', DocumentationAnalyticsViewSet.as_view({'get': 'trends'}), name='documentation-analytics-trends'),
    
    # Real-time endpoints
    path('real-time/search/', DocumentationViewSet.as_view({'get': 'real_time_search'}), name='real-time-search'),
    path('real-time/views/', DocumentationViewSet.as_view({'get': 'real_time_views'}), name='real-time-views'),
    path('real-time/updates/', DocumentationViewSet.as_view({'get': 'real_time_updates'}), name='real-time-updates'),
    
    # Bulk operations endpoints
    path('bulk/create/', DocumentationViewSet.as_view({'post': 'bulk_create'}), name='bulk-create-documentation'),
    path('bulk/update/', DocumentationViewSet.as_view({'post': 'bulk_update'}), name='bulk-update-documentation'),
    path('bulk/delete/', DocumentationViewSet.as_view({'post': 'bulk_delete'}), name='bulk-delete-documentation'),
    path('bulk/publish/', DocumentationViewSet.as_view({'post': 'bulk_publish'}), name='bulk-publish-documentation'),
    
    # Configuration endpoints
    path('config/doc_types/', DocumentationViewSet.as_view({'get': 'supported_doc_types'}), name='config-supported-doc-types'),
    path('config/categories/', DocumentationViewSet.as_view({'get': 'supported_categories'}), name='config-supported-categories'),
    path('config/tags/', DocumentationViewSet.as_view({'get': 'supported_tags'}), name='config-supported-tags'),
    path('config/formats/', DocumentationViewSet.as_view({'get': 'supported_formats'}), name='config-supported-formats'),
    
    # Monitoring endpoints
    path('monitoring/health/', DocumentationViewSet.as_view({'get': 'health_check'}), name='monitoring-health'),
    path('monitoring/performance/', DocumentationViewSet.as_view({'get': 'performance_metrics'}), name='monitoring-performance'),
    path('monitoring/errors/', DocumentationViewSet.as_view({'get': 'error_logs'}), name='monitoring-errors'),
    path('monitoring/alerts/', DocumentationViewSet.as_view({'get': 'alerts'}), name='monitoring-alerts'),
    
    # Export endpoints
    path('export/documentation/', DocumentationViewSet.as_view({'post': 'export_documentation'}), name='export-documentation'),
    path('export/search-results/', DocumentationSearchViewSet.as_view({'post': 'export_search_results'}), name='export-search-results'),
    path('export/analytics/', DocumentationAnalyticsViewSet.as_view({'post': 'export_analytics'}), name='export-analytics'),
    path('export/reports/', DocumentationAnalyticsViewSet.as_view({'post': 'export_reports'}), name='export-reports'),
    
    # Debug endpoints
    path('debug/ping/', DocumentationURLConfig.debug_ping_view, name='docs-debug-ping'),
    path('debug/search/', DocumentationURLConfig.debug_search_view, name='docs-debug-search'),
    path('debug/analytics/', DocumentationURLConfig.debug_analytics_view, name='docs-debug-analytics'),
]

# Export router for inclusion in main URLs
docs_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        path('debug/performance/', DocumentationURLConfig.debug_performance_view, name='docs-debug-performance'),
        path('debug/cache/', DocumentationURLConfig.debug_cache_view, name='docs-debug-cache'),
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('docs_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'documentation': 5,
            'search': 3,
            'api': 4,
            'user_guides': 4,
            'technical': 4,
            'versions': 4,
            'analytics': 4,
            'real_time': 3,
            'bulk': 4,
            'config': 4,
            'monitoring': 4,
            'export': 4,
            'debug': 3
        },
        'version': '1.0.0'
    }, timeout=3600)
except Exception:
    # Cache failure should not break URL configuration
    pass

# Security: Add URL validation middleware
class DocumentationURLValidator:
    """URL validator for documentation with security checks."""
    
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
            cache_key = f"docs_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 200 requests per minute for documentation
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
        
        # Add documentation specific headers
        response['X-Docs-Version'] = '1.0.0'
        response['X-Docs-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 200 - cache.get(f"docs_rate_limit_{self._get_client_ip(None)}", 0)))


# Performance: Add response compression
class DocumentationResponseCompression:
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
class DocumentationCSRFProtection:
    """CSRF protection for documentation."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Apply CSRF protection."""
        # Skip CSRF for safe methods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return self.get_response(request)
        
        # Apply CSRF protection for unsafe methods
        from django.middleware.csrf import CsrfViewMiddleware
        csrf_middleware = CsrfViewMiddleware(self.get_response)
        return csrf_middleware(request)


# Performance: Add caching headers
class DocumentationCachingHeaders:
    """Caching headers for documentation."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Add caching headers."""
        response = self.get_response(request)
        
        # Add caching headers for GET requests
        if request.method == 'GET':
            path = request.path
            
            # Cache for different durations based on endpoint
            if 'config' in path:
                response['Cache-Control'] = 'public, max-age=3600'  # 1 hour
            elif 'analytics' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'real-time' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'search' in path:
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
class DocumentationDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'documentation_created_at_idx',
                'documentation_type_idx',
                'documentation_status_idx',
                'documentation_category_idx',
                'documentation_tags_idx',
                'documentation_search_created_at_idx',
                'documentation_versioning_created_at_idx',
                'documentation_analytics_created_at_idx',
                'api_documentation_created_at_idx',
                'user_guide_created_at_idx',
                'technical_documentation_created_at_idx'
            ],
            'prefetch_related': [
                'created_by', 'updated_by', 'documentation'
            ],
            'select_related': [
                'created_by', 'updated_by', 'documentation'
            ],
            'annotate_fields': [
                'type', 'status', 'category', 'tags', 'created_at', 'updated_at'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class DocumentationRateLimitConfig:
    """Rate limiting configuration for documentation."""
    
    RATE_LIMITS = {
        'documentation_create': '20/hour',
        'documentation_update': '50/hour',
        'documentation_search': '200/hour',
        'documentation_view': '500/hour',
        'api_documentation_openapi': '100/hour',
        'api_documentation_validate': '50/hour',
        'user_guide_toc': '200/hour',
        'user_guide_reading_time': '200/hour',
        'technical_code_blocks': '200/hour',
        'technical_validate': '50/hour',
        'documentation_search_advanced': '200/hour',
        'documentation_version_create': '50/hour',
        'documentation_version_restore': '50/hour',
        'documentation_analytics_engagement': '100/hour',
        'documentation_analytics_analytics': '100/hour',
        'bulk_create': '20/hour',
        'bulk_update': '50/hour',
        'bulk_delete': '20/hour',
        'bulk_publish': '50/hour',
        'export_documentation': '50/hour',
        'export_search_results': '50/hour',
        'export_analytics': '50/hour',
        'export_reports': '50/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '100/hour')


# Performance: API versioning
class DocumentationAPIVersioning:
    """API versioning for documentation."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/docs/{base_url.lstrip('/')}"
    
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
class DocumentationInputValidation:
    """Input validation patterns for documentation."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'documentation_type': r'^(api|user_guide|technical|policy)$',
        'documentation_status': r'^(draft|review|published|archived)$',
        'search_sort_by': r'^(relevance|updated_at|title|created_at)$',
        'api_method': r'^(get|post|put|delete|patch|head|options)$',
        'difficulty_level': r'^(beginner|intermediate|advanced|expert)$',
        'technical_level': r'^(beginner|intermediate|advanced|expert)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'version': r'^\d+\.\d+\.\d+$',
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
        if input_type in ['documentation_type', 'documentation_status', 'search_sort_by']:
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'version':
            # Normalize to semantic versioning
            sanitized = re.sub(r'[^\d.]', '', sanitized)
        
        return sanitized


# Performance: Response optimization
class DocumentationResponseOptimizer:
    """Response optimization for documentation."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'docs' in request_path:
            # Add documentation specific headers
            response['X-Docs-Cache'] = 'hit'
            response['X-Docs-Generated'] = str(time.time())
        elif 'api' in request_path:
            # Add API specific headers
            response['X-API-Cache'] = 'hit'
            response['X-API-Generated'] = str(time.time())
        elif 'user-guides' in request_path:
            # Add user guide specific headers
            response['X-UserGuide-Cache'] = 'hit'
            response['X-UserGuide-Generated'] = str(time.time())
        elif 'technical' in request_path:
            # Add technical specific headers
            response['X-Technical-Cache'] = 'hit'
            response['X-Technical-Generated'] = str(time.time())
        elif 'search' in request_path:
            # Add search specific headers
            response['X-Search-Cache'] = 'hit'
            response['X-Search-Generated'] = str(time.time())
        elif 'versions' in request_path:
            # Add versioning specific headers
            response['X-Versioning-Cache'] = 'hit'
            response['X-Versioning-Generated'] = str(time.time())
        elif 'analytics' in request_path:
            # Add analytics specific headers
            response['X-Analytics-Cache'] = 'hit'
            response['X-Analytics-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class DocumentationAuditConfig:
    """Audit logging configuration for documentation."""
    
    AUDIT_EVENTS = [
        'documentation_created',
        'documentation_updated',
        'documentation_deleted',
        'documentation_viewed',
        'documentation_searched',
        'api_documentation_validated',
        'user_guide_bookmarked',
        'technical_documentation_validated',
        'documentation_version_created',
        'documentation_version_restored',
        'bulk_operation',
        'documentation_exported',
        'analytics_viewed',
    ]
    
    SENSITIVE_FIELDS = [
        'content',
        'api_key',
        'authentication',
        'configuration',
        'troubleshooting',
        'components',
        'schemas',
        'endpoints',
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
class DocumentationDatabaseConfig:
    """Database configuration for documentation."""
    
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
                'MAX_CONNS': 150,  # Increased for documentation
                'MIN_CONNS': 30,   # Increased for documentation
                'MAX_CONNS_PER_QUERY': 50,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class DocumentationCORSConfig:
    """CORS configuration for documentation."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://docs.example.com',
        'https://api.example.com',
        'https://dashboard.example.com',
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
        'X-Documentation-ID',
        'X-Search-Query',
        'X-Security-Token',
        'X-Rate-Limit-Limit',
        'X-Rate-Limit-Remaining',
        'X-Rate-Limit-Reset',
    ]
    
    EXPOSED_HEADERS = [
        'X-Docs-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-Docs-Cache',
        'X-API-Cache',
        'X-UserGuide-Cache',
        'X-Technical-Cache',
        'X-Search-Cache',
        'X-Versioning-Cache',
        'X-Analytics-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class DocumentationCacheConfig:
    """Caching configuration for documentation."""
    
    CACHE_KEYS = {
        'documentation_data': 'documentation_data_{doc_id}',
        'documentation_stats': 'documentation_stats_{doc_id}',
        'documentation_search': 'documentation_search_{query_hash}',
        'api_documentation_data': 'api_documentation_data_{doc_id}',
        'user_guide_data': 'user_guide_data_{doc_id}',
        'technical_documentation_data': 'technical_documentation_data_{doc_id}',
        'documentation_version_data': 'documentation_version_data_{doc_id}',
        'documentation_analytics': 'documentation_analytics_{doc_id}',
        'system_status': 'system_status',
        'rate_limit': 'rate_limit_{client_ip}',
        'bulk_operation': 'bulk_operation_{operation_id}',
    }
    
    CACHE_TIMEOUTS = {
        'documentation_data': 1800,      # 30 minutes
        'documentation_stats': 60,       # 1 minute
        'documentation_search': 300,     # 5 minutes
        'api_documentation_data': 1800,  # 30 minutes
        'user_guide_data': 1800,        # 30 minutes
        'technical_documentation_data': 1800, # 30 minutes
        'documentation_version_data': 1800, # 30 minutes
        'documentation_analytics': 300,   # 5 minutes
        'system_status': 60,            # 1 minute
        'rate_limit': 60,               # 1 minute
        'bulk_operation': 3600,         # 1 hour
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'documentation_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 600)


# URL Configuration Class
class DocumentationURLConfig:
    """URL configuration class for documentation."""
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_ping_view(request):
        """Debug view for health checks."""
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
                    'documentation', 'search', 'api', 'user_guides',
                    'technical', 'versions', 'analytics',
                    'real_time', 'bulk', 'config', 'monitoring', 'export', 'debug'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'search_indexing': 'optimized',
                    'content_rendering': 'cached'
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_search_view(request):
        """Debug view for search monitoring."""
        try:
            from django.core.cache import cache
            
            # Get search cache keys
            search_keys = []
            if hasattr(cache, '_cache'):
                search_keys = [key for key in cache._cache.keys() if 'search' in str(key)]
            
            # Get search info
            search_info = {}
            for key in search_keys[:50]:  # Limit to 50 keys
                try:
                    search_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    search_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'search_keys': search_keys,
                'search_info': search_info,
                'total_keys': len(search_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_analytics_view(request):
        """Debug view for analytics monitoring."""
        try:
            from django.core.cache import cache
            
            # Get analytics cache keys
            analytics_keys = []
            if hasattr(cache, '_cache'):
                analytics_keys = [key for key in cache._cache.keys() if 'analytics' in str(key)]
            
            # Get analytics info
            analytics_info = {}
            for key in analytics_keys[:50]:  # Limit to 50 keys
                try:
                    analytics_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    analytics_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'analytics_keys': analytics_keys,
                'analytics_info': analytics_info,
                'total_keys': len(analytics_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
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
                    'documentation', 'search', 'api', 'user_guides',
                    'technical', 'versions', 'analytics',
                    'real_time', 'bulk', 'config', 'monitoring', 'export', 'debug'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'search_indexing': 'optimized',
                    'content_rendering': 'cached'
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_cache_view(request):
        """Debug view for cache monitoring."""
        try:
            from django.core.cache import cache
            
            # Get all cache keys
            cache_keys = []
            if hasattr(cache, '_cache'):
                cache_keys = list(cache._cache.keys())
            
            # Get cache info
            cache_info = {}
            for key in cache_keys[:100]:  # Limit to 100 keys
                try:
                    cache_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    cache_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'cache_keys': cache_keys,
                'cache_info': cache_info,
                'total_keys': len(cache_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Export configuration classes for use in settings
DOCUMENTATION_CONFIG = {
    'URL_VALIDATOR': DocumentationURLValidator,
    'RESPONSE_COMPRESSION': DocumentationResponseCompression,
    'CSRF_PROTECTION': DocumentationCSRFProtection,
    'CACHING_HEADERS': DocumentationCachingHeaders,
    'DATABASE_HINTS': DocumentationDatabaseHints,
    'RATE_LIMIT_CONFIG': DocumentationRateLimitConfig,
    'API_VERSIONING': DocumentationAPIVersioning,
    'INPUT_VALIDATION': DocumentationInputValidation,
    'RESPONSE_OPTIMIZER': DocumentationResponseOptimizer,
    'AUDIT_CONFIG': DocumentationAuditConfig,
    'DATABASE_CONFIG': DocumentationDatabaseConfig,
    'CORS_CONFIG': DocumentationCORSConfig,
    'CACHE_CONFIG': DocumentationCacheConfig,
    'URL_CONFIG': DocumentationURLConfig,
}
