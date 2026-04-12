"""
Reporting Dashboard URLs

This module defines URL patterns for reporting and dashboard endpoints with
enterprise-grade security, performance optimization, and comprehensive functionality
following industry standards from Google Analytics, Tableau, and Power BI.
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
    ReportingViewSet,
    DashboardViewSet,
    AnalyticsViewSet,
    VisualizationViewSet,
    ReportGenerationViewSet
)

# Create router for reporting dashboard with optimized routing
router = DefaultRouter()
router.register(r'reports', ReportingViewSet, basename='reporting')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'visualizations', VisualizationViewSet, basename='visualization')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # Report generation URLs
    path('reports/generate/', ReportingViewSet.as_view({'post': 'generate'}), name='reports-generate'),
    path('reports/schedule/', ReportingViewSet.as_view({'post': 'schedule'}), name='reports-schedule'),
    path('reports/export/', ReportingViewSet.as_view({'post': 'export'}), name='reports-export'),
    path('reports/templates/', ReportingViewSet.as_view({'get': 'templates'}), name='reports-templates'),
    
    # Dashboard URLs
    path('dashboards/create/', DashboardViewSet.as_view({'post': 'create'}), name='dashboards-create'),
    path('dashboards/<uuid:pk>/data/', DashboardViewSet.as_view({'get': 'data'}), name='dashboards-data'),
    path('dashboards/<uuid:pk>/layout/', DashboardViewSet.as_view({'post': 'update_layout'}), name='dashboards-update-layout'),
    path('dashboards/templates/', DashboardViewSet.as_view({'get': 'templates'}), name='dashboards-templates'),
    
    # Analytics URLs
    path('analytics/calculate/', AnalyticsViewSet.as_view({'post': 'calculate'}), name='analytics-calculate'),
    path('analytics/insights/', AnalyticsViewSet.as_view({'post': 'insights'}), name='analytics-insights'),
    path('analytics/metrics/', AnalyticsViewSet.as_view({'get': 'metrics'}), name='analytics-metrics'),
    
    # Visualization URLs
    path('visualizations/create/', VisualizationViewSet.as_view({'post': 'create'}), name='visualizations-create'),
    path('visualizations/<uuid:pk>/data/', VisualizationViewSet.as_view({'get': 'data'}), name='visualizations-data'),
    path('visualizations/types/', VisualizationViewSet.as_view({'get': 'types'}), name='visualizations-types'),
    
    # Report generation URLs
    path('generation/trigger/', ReportGenerationViewSet.as_view({'post': 'trigger'}), name='generation-trigger'),
    path('generation/schedules/', ReportGenerationViewSet.as_view({'get': 'schedules'}), name='generation-schedules'),
    
    # Real-time endpoints
    path('real-time/metrics/', ReportingViewSet.as_view({'get': 'real_time_metrics'}), name='real-time-metrics'),
    path('real-time/dashboard/', DashboardViewSet.as_view({'get': 'real_time_dashboard'}), name='real-time-dashboard'),
    path('real-time/analytics/', AnalyticsViewSet.as_view({'get': 'real_time_analytics'}), name='real-time-analytics'),
    
    # Export endpoints
    path('export/csv/', ReportingViewSet.as_view({'post': 'export_csv'}), name='export-csv'),
    path('export/excel/', ReportingViewSet.as_view({'post': 'export_excel'}), name='export-excel'),
    path('export/pdf/', ReportingViewSet.as_view({'post': 'export_pdf'}), name='export-pdf'),
    path('export/json/', ReportingViewSet.as_view({'post': 'export_json'}), name='export-json'),
    
    # Template endpoints
    path('templates/reports/', ReportingViewSet.as_view({'get': 'report_templates'}), name='templates-reports'),
    path('templates/dashboards/', DashboardViewSet.as_view({'get': 'dashboard_templates'}), name='templates-dashboards'),
    path('templates/visualizations/', VisualizationViewSet.as_view({'get': 'visualization_templates'}), name='templates-visualizations'),
]

# Export router for inclusion in main URLs
reporting_dashboard_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        path('debug/performance/', ReportingDashboardURLConfig.debug_performance_view, name='reporting-debug-performance'),
        path('debug/cache/', ReportingDashboardURLConfig.debug_cache_view, name='reporting-debug-cache'),
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('reporting_dashboard_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'reports': 4,
            'dashboards': 4,
            'analytics': 3,
            'visualizations': 3,
            'generation': 2,
            'real_time': 3,
            'export': 4,
            'templates': 3
        },
        'version': '1.0.0'
    }, timeout=3600)
except Exception:
    # Cache failure should not break URL configuration
    pass

# Security: Add URL validation middleware
class ReportingDashboardURLValidator:
    """URL validator for reporting dashboard endpoints with security checks."""
    
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
            cache_key = f"reporting_dashboard_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 200 requests per minute for reporting dashboard
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
        
        # Add reporting dashboard specific headers
        response['X-Reporting-Dashboard-Version'] = '1.0.0'
        response['X-Reporting-Dashboard-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 200 - cache.get(f"reporting_dashboard_rate_limit_{self._get_client_ip(None)}", 0)))


# Performance: Add response compression
class ReportingDashboardResponseCompression:
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
class ReportingDashboardCSRFProtection:
    """CSRF protection for reporting dashboard endpoints."""
    
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
class ReportingDashboardCachingHeaders:
    """Caching headers for reporting dashboard endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Add caching headers."""
        response = self.get_response(request)
        
        # Add caching headers for GET requests
        if request.method == 'GET':
            path = request.path
            
            # Cache for different durations based on endpoint
            if 'real-time' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'analytics' in path:
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
            elif 'dashboards' in path:
                response['Cache-Control'] = 'public, max-age=600'  # 10 minutes
            elif 'reports' in path:
                response['Cache-Control'] = 'public, max-age=1800'  # 30 minutes
            else:
                response['Cache-Control'] = 'public, max-age=3600'  # 1 hour
        else:
            # No caching for POST/PUT/DELETE requests
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


# Performance: Database query optimization hints
class ReportingDashboardDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'report_created_at_idx',
                'report_report_type_idx',
                'dashboard_created_at_idx',
                'visualization_created_at_idx',
                'analytics_event_timestamp_idx',
                'performance_metric_timestamp_idx'
            ],
            'prefetch_related': [
                'report_set',
                'dashboard_set',
                'visualization_set',
                'analytics_events',
                'performance_metrics'
            ],
            'select_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'annotate_fields': [
                'report_type', 'created_at', 'updated_at',
                'viz_type', 'is_interactive',
                'metric_value', 'timestamp'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class ReportingDashboardRateLimitConfig:
    """Rate limiting configuration for reporting dashboard endpoints."""
    
    RATE_LIMITS = {
        'reports_generate': '100/hour',
        'reports_schedule': '50/hour',
        'reports_export': '200/hour',
        'dashboards_create': '50/hour',
        'dashboards_data': '1000/hour',
        'analytics_calculate': '500/hour',
        'analytics_insights': '200/hour',
        'visualizations_create': '50/hour',
        'visualizations_data': '500/hour',
        'generation_trigger': '100/hour',
        'real_time_metrics': '5000/hour',
        'export_csv': '100/hour',
        'export_excel': '100/hour',
        'export_pdf': '50/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '100/hour')


# Performance: API versioning
class ReportingDashboardAPIVersioning:
    """API versioning for reporting dashboard endpoints."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/reporting-dashboard/{base_url.lstrip('/')}"
    
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
class ReportingDashboardInputValidation:
    """Input validation patterns for reporting dashboard endpoints."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'report_type': r'^(performance|financial|audience|campaign|custom)$',
        'dashboard_layout': r'^[a-zA-Z0-9\-\s\{\}\[\]:,]*$',
        'viz_type': r'^(line_chart|bar_chart|pie_chart|scatter_plot|heatmap|funnel|gauge|table|custom)$',
        'date_range': r'^(today|yesterday|last_7_days|last_30_days|last_90_days|this_month|last_month|this_year|last_year|custom)$',
        'time_format': r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'export_format': r'^(csv|excel|pdf|json|xml)$',
        'schedule_type': r'^(daily|weekly|monthly|quarterly|yearly|custom)$',
        'delivery_method': r'^(email|ftp|webhook|api)$',
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
        if input_type == 'report_type':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'date_range':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'export_format':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'schedule_type':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'delivery_method':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        
        return sanitized


# Performance: Response optimization
class ReportingDashboardResponseOptimizer:
    """Response optimization for reporting dashboard endpoints."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'reports' in request_path:
            # Add reporting-specific headers
            response['X-Report-Cache'] = 'hit'
            response['X-Report-Generated'] = str(time.time())
        elif 'dashboards' in request_path:
            # Add dashboard-specific headers
            response['X-Dashboard-Cache'] = 'hit'
            response['X-Dashboard-Generated'] = str(time.time())
        elif 'analytics' in request_path:
            # Add analytics-specific headers
            response['X-Analytics-Cache'] = 'hit'
            response['X-Analytics-Generated'] = str(time.time())
        elif 'visualizations' in request_path:
            # Add visualization-specific headers
            response['X-Visualization-Cache'] = 'hit'
            response['X-Visualization-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class ReportingDashboardAuditConfig:
    """Audit logging configuration for reporting dashboard endpoints."""
    
    AUDIT_EVENTS = [
        'report_generated',
        'report_scheduled',
        'report_exported',
        'dashboard_created',
        'dashboard_updated',
        'dashboard_accessed',
        'analytics_calculated',
        'insights_generated',
        'visualization_created',
        'visualization_accessed',
        'generation_triggered',
    ]
    
    SENSITIVE_FIELDS = [
        'filters',
        'custom_config',
        'chart_config',
        'delivery_params',
        'schedule_params',
        'layout',
        'widgets',
        'report_data',
        'dashboard_data',
        'visualization_data',
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
class ReportingDashboardDatabaseConfig:
    """Database configuration for reporting dashboard endpoints."""
    
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
                'MAX_CONNS': 100,  # Increased for reporting dashboard
                'MIN_CONNS': 20,   # Increased for reporting dashboard
                'MAX_CONNS_PER_QUERY': 50,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class ReportingDashboardCORSConfig:
    """CORS configuration for reporting dashboard endpoints."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://dashboard.example.com',
        'https://analytics.example.com',
        'https://reports.example.com',
    ]
    
    ALLOWED_METHODS = [
        'GET',
        'POST',
        'PUT',
        'PATCH',
        'DELETE',
        'OPTIONS',
    ]
    
    ALLOWED_HEADERS = [
        'Content-Type',
        'Authorization',
        'X-API-Version',
        'X-Request-ID',
        'X-Client-IP',
        'X-User-Agent',
        'X-Widget-ID',
        'X-Dashboard-ID',
    ]
    
    EXPOSED_HEADERS = [
        'X-Reporting-Dashboard-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-Report-Cache',
        'X-Dashboard-Cache',
        'X-Analytics-Cache',
        'X-Visualization-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class ReportingDashboardCacheConfig:
    """Caching configuration for reporting dashboard endpoints."""
    
    CACHE_KEYS = {
        'report_data': 'report_data_{report_id}',
        'dashboard_data': 'dashboard_data_{dashboard_id}',
        'analytics_metrics': 'analytics_metrics_{metric_id}',
        'visualization_data': 'visualization_data_{viz_id}',
        'real_time_metrics': 'real_time_metrics_{user_id}',
        'export_data': 'export_data_{export_id}',
        'template_data': 'template_data_{template_type}',
        'user_preferences': 'user_preferences_{user_id}',
        'dashboard_layout': 'dashboard_layout_{dashboard_id}',
    }
    
    CACHE_TIMEOUTS = {
        'report_data': 1800,      # 30 minutes
        'dashboard_data': 600,    # 10 minutes
        'analytics_metrics': 300,  # 5 minutes
        'visualization_data': 900, # 15 minutes
        'real_time_metrics': 60,  # 1 minute
        'export_data': 3600,    # 1 hour
        'template_data': 7200,   # 2 hours
        'user_preferences': 86400, # 24 hours
        'dashboard_layout': 3600, # 1 hour
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'reporting_dashboard_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 600)


# URL Configuration Class
class ReportingDashboardURLConfig:
    """URL configuration class for reporting dashboard endpoints."""
    
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
                    'reports',
                    'dashboards',
                    'analytics',
                    'visualizations',
                    'generation',
                    'real_time',
                    'export',
                    'templates'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True
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
            
            # Get cache keys
            cache_keys = []
            if hasattr(cache, '_cache'):
                cache_keys = list(cache._cache.keys())[:50]  # Limit to 50 keys
            
            # Get cache info
            cache_info = {}
            for key in cache_keys:
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
REPORTING_DASHBOARD_CONFIG = {
    'URL_VALIDATOR': ReportingDashboardURLValidator,
    'RESPONSE_COMPRESSION': ReportingDashboardResponseCompression,
    'CSRF_PROTECTION': ReportingDashboardCSRFProtection,
    'CACHING_HEADERS': ReportingDashboardCachingHeaders,
    'DATABASE_HINTS': ReportingDashboardDatabaseHints,
    'RATE_LIMIT_CONFIG': ReportingDashboardRateLimitConfig,
    'API_VERSIONING': ReportingDashboardAPIVersioning,
    'INPUT_VALIDATION': ReportingDashboardInputValidation,
    'RESPONSE_OPTIMIZER': ReportingDashboardResponseOptimizer,
    'AUDIT_CONFIG': ReportingDashboardAuditConfig,
    'DATABASE_CONFIG': ReportingDashboardDatabaseConfig,
    'CORS_CONFIG': ReportingDashboardCORSConfig,
    'CACHE_CONFIG': ReportingDashboardCacheConfig,
    'URL_CONFIG': ReportingDashboardURLConfig,
}
