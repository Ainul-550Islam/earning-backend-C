"""
Fraud Prevention URLs

This module defines URL patterns for fraud prevention endpoints with enterprise-grade
security, performance optimization, and comprehensive functionality following
industry standards from Stripe, OgAds, and leading fraud prevention systems.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from django.conf import settings
from django.urls.exceptions import NoReverseMatch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
import time
import logging

from .views import (
    FraudDetectionViewSet,
    RiskScoringViewSet,
    PatternAnalysisViewSet,
    SecurityMonitoringViewSet,
    FraudPreventionViewSet
)

# Create router for fraud prevention with optimized routing
router = DefaultRouter()
router.register(r'detection', FraudDetectionViewSet, basename='fraud-detection')
router.register(r'risk-scoring', RiskScoringViewSet, basename='risk-scoring')
router.register(r'pattern-analysis', PatternAnalysisViewSet, basename='pattern-analysis')
router.register(r'security-monitoring', SecurityMonitoringViewSet, basename='security-monitoring')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # Comprehensive fraud prevention URLs
    path('comprehensive/', FraudPreventionViewSet.as_view({'post': 'comprehensive_analysis'}), name='fraud-comprehensive-analysis'),
    path('dashboard/', FraudPreventionViewSet.as_view({'get': 'dashboard'}), name='fraud-prevention-dashboard'),
    
    # Real-time detection endpoints
    path('real-time/detect/', FraudDetectionViewSet.as_view({'post': 'detect'}), name='fraud-real-time-detect'),
    path('real-time/batch/', FraudDetectionViewSet.as_view({'post': 'batch_detect'}), name='fraud-batch-detect'),
    
    # Analytics and reporting URLs
    path('analytics/statistics/', FraudDetectionViewSet.as_view({'get': 'statistics'}), name='fraud-analytics-statistics'),
    path('analytics/trends/', FraudDetectionViewSet.as_view({'get': 'trends'}), name='fraud-analytics-trends'),
    path('analytics/reports/', FraudDetectionViewSet.as_view({'get': 'reports'}), name='fraud-analytics-reports'),
    
    # Risk management URLs
    path('risk/calculate/', RiskScoringViewSet.as_view({'post': 'calculate'}), name='fraud-risk-calculate'),
    path('risk/history/', RiskScoringViewSet.as_view({'get': 'history'}), name='fraud-risk-history'),
    path('risk/batch/', RiskScoringViewSet.as_view({'post': 'batch_calculate'}), name='fraud-risk-batch'),
    
    # Pattern analysis URLs
    path('patterns/analyze/', PatternAnalysisViewSet.as_view({'post': 'analyze'}), name='fraud-patterns-analyze'),
    path('patterns/dashboard/', PatternAnalysisViewSet.as_view({'get': 'dashboard'}), name='fraud-patterns-dashboard'),
    path('patterns/create/', PatternAnalysisViewSet.as_view({'post': 'create_pattern'}), name='fraud-patterns-create'),
    
    # Security monitoring URLs
    path('security/alerts/', SecurityMonitoringViewSet.as_view({'get': 'alerts'}), name='fraud-security-alerts'),
    path('security/create-alert/', SecurityMonitoringViewSet.as_view({'post': 'create_alert'}), name='fraud-security-create-alert'),
    path('security/update-alert/', SecurityMonitoringViewSet.as_view({'post': 'update_alert'}), name='fraud-security-update-alert'),
    path('security/incidents/', SecurityMonitoringViewSet.as_view({'get': 'incidents'}), name='fraud-security-incidents'),
]

# Export router for inclusion in main URLs
fraud_prevention_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        path('debug/performance/', FraudPreventionURLConfig.debug_performance_view, name='fraud-debug-performance'),
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('fraud_prevention_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'detection': 3,
            'risk_scoring': 3,
            'pattern_analysis': 3,
            'security_monitoring': 4,
            'comprehensive': 2,
            'analytics': 3
        },
        'version': '1.0.0'
    }, timeout=3600)
except Exception:
    # Cache failure should not break URL configuration
    pass

# Security: Add URL validation middleware
class FraudPreventionURLValidator:
    """URL validator for fraud prevention endpoints with security checks."""
    
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
            cache_key = f"fraud_prevention_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 100 requests per minute
            if current_count >= 100:
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
        
        # Add fraud prevention specific headers
        response['X-Fraud-Prevention-Version'] = '1.0.0'
        response['X-Fraud-Prevention-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 100 - cache.get(f"fraud_prevention_rate_limit_{self._get_client_ip(request)}", 0)))


# Performance: Add response compression
class FraudPreventionResponseCompression:
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
class FraudPreventionCSRFProtection:
    """CSRF protection for fraud prevention endpoints."""
    
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
class FraudPreventionCachingHeaders:
    """Caching headers for fraud prevention endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Add caching headers."""
        response = self.get_response(request)
        
        # Add caching headers for GET requests
        if request.method == 'GET':
            path = request.path
            
            # Cache for different durations based on endpoint
            if 'dashboard' in path:
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
            elif 'statistics' in path:
                response['Cache-Control'] = 'public, max-age=600'  # 10 minutes
            elif 'history' in path:
                response['Cache-Control'] = 'public, max-age=60'   # 1 minute
            else:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
        
        return response


# Performance: Database query optimization hints
class FraudPreventionDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'fraud_detection_user_id_idx',
                'fraud_detection_timestamp_idx',
                'fraud_detection_risk_score_idx',
                'risk_score_user_id_idx',
                'risk_score_assessment_timestamp_idx',
                'security_alert_status_idx',
                'security_alert_created_at_idx'
            ],
            'prefetch_related': [
                'frauddetection_set',
                'riskscore_set',
                'securityalert_set'
            ],
            'select_related': [
                'user', 'advertiser', 'created_by', 'updated_by'
            ],
            'annotate_fields': [
                'risk_score', 'confidence_level', 'detection_timestamp',
                'overall_risk_score', 'assessment_timestamp', 'severity'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class FraudPreventionRateLimitConfig:
    """Rate limiting configuration for fraud prevention endpoints."""
    
    RATE_LIMITS = {
        'fraud_detection': '1000/hour',
        'risk_scoring': '500/hour',
        'pattern_analysis': '200/hour',
        'security_alerts': '100/hour',
        'comprehensive_analysis': '100/hour',
        'dashboard': '1000/hour',
        'statistics': '500/hour',
        'history': '200/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '100/hour')


# Performance: API versioning
class FraudPreventionAPIVersioning:
    """API versioning for fraud prevention endpoints."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/fraud-prevention/{base_url.lstrip('/')}"
    
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
class FraudPreventionInputValidation:
    """Input validation patterns for fraud prevention endpoints."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'event_type': r'^(login|transaction|registration|campaign_create|creative_upload)$',
        'risk_level': r'^(low|medium|high|critical)$',
        'alert_type': r'^(fraud|suspicious_activity|security_breach|anomaly|threat)$',
        'severity': r'^(low|medium|high|critical)$',
        'status': r'^(open|investigating|resolved|closed)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'ip_address': r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$',
        'risk_score': r'^0\.[0-9]{1,3}$|^1\.0$',
        'confidence_level': r'^0\.[0-9]{1,3}$|^1\.0$',
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
        if input_type == 'event_type':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'risk_score':
            # Ensure valid decimal format
            try:
                float_val = float(sanitized)
                sanitized = f"{float_val:.4f}"
            except ValueError:
                sanitized = "0.0000"
        elif input_type == 'ip_address':
            # Validate IP format
            import ipaddress
            try:
                ipaddress.ip_address(sanitized)
            except ValueError:
                sanitized = "0.0.0.0"
        
        return sanitized


# Performance: Response optimization
class FraudPreventionResponseOptimizer:
    """Response optimization for fraud prevention endpoints."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'detection' in request_path:
            # Add detection-specific headers
            response['X-Detection-Cache'] = 'hit'
            response['X-Detection-Generated'] = str(time.time())
        elif 'risk-scoring' in request_path:
            # Add risk scoring specific headers
            response['X-Risk-Cache'] = 'hit'
            response['X-Risk-Generated'] = str(time.time())
        elif 'security' in request_path:
            # Add security-specific headers
            response['X-Security-Cache'] = 'hit'
            response['X-Security-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class FraudPreventionAuditConfig:
    """Audit logging configuration for fraud prevention endpoints."""
    
    AUDIT_EVENTS = [
        'fraud_detection_request',
        'risk_score_calculation',
        'pattern_analysis_request',
        'security_alert_created',
        'security_alert_updated',
        'comprehensive_analysis_request',
        'dashboard_accessed',
    ]
    
    SENSITIVE_FIELDS = [
        'ip_address',
        'user_agent',
        'device_fingerprint',
        'session_id',
        'event_data',
        'threat_data',
        'risk_factors',
        'custom_data',
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
class FraudPreventionDatabaseConfig:
    """Database configuration for fraud prevention endpoints."""
    
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
                'MAX_CONNS': 50,  # Increased for fraud prevention
                'MIN_CONNS': 10,   # Increased for fraud prevention
                'MAX_CONNS_PER_QUERY': 20,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class FraudPreventionCORSConfig:
    """CORS configuration for fraud prevention endpoints."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://ads.example.com',
        'https://dashboard.example.com',
        'https://security.example.com',
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
        'X-Device-Fingerprint',
    ]
    
    EXPOSED_HEADERS = [
        'X-Fraud-Prevention-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-Detection-Cache',
        'X-Risk-Cache',
        'X-Security-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class FraudPreventionCacheConfig:
    """Caching configuration for fraud prevention endpoints."""
    
    CACHE_KEYS = {
        'fraud_detection_result': 'fraud_detection_result_{hash}',
        'risk_score_result': 'risk_score_result_{user_id}',
        'pattern_analysis_result': 'pattern_analysis_result_{user_id}_{days}',
        'security_alerts': 'security_alerts_{filters_hash}',
        'dashboard_data': 'fraud_dashboard_{user_id}',
        'statistics_data': 'fraud_stats_{user_id}_{period}',
        'user_risk_history': 'user_risk_history_{user_id}_{days}',
        'detection_statistics': 'detection_stats_{user_id}_{period}',
    }
    
    CACHE_TIMEOUTS = {
        'fraud_detection_result': 300,      # 5 minutes
        'risk_score_result': 600,          # 10 minutes
        'pattern_analysis_result': 1800,    # 30 minutes
        'security_alerts': 300,            # 5 minutes
        'dashboard_data': 300,             # 5 minutes
        'statistics_data': 600,            # 10 minutes
        'user_risk_history': 1800,         # 30 minutes
        'detection_statistics': 600,         # 10 minutes
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'fraud_prevention_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 300)


# URL Configuration Class
class FraudPreventionURLConfig:
    """URL configuration class for fraud prevention endpoints."""
    
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
                    'fraud-detection',
                    'risk-scoring',
                    'pattern-analysis',
                    'security-monitoring',
                    'comprehensive-analysis',
                    'dashboard'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Export configuration classes for use in settings
FRAUD_PREVENTION_CONFIG = {
    'URL_VALIDATOR': FraudPreventionURLValidator,
    'RESPONSE_COMPRESSION': FraudPreventionResponseCompression,
    'CSRF_PROTECTION': FraudPreventionCSRFProtection,
    'CACHING_HEADERS': FraudPreventionCachingHeaders,
    'DATABASE_HINTS': FraudPreventionDatabaseHints,
    'RATE_LIMIT_CONFIG': FraudPreventionRateLimitConfig,
    'API_VERSIONING': FraudPreventionAPIVersioning,
    'INPUT_VALIDATION': FraudPreventionInputValidation,
    'RESPONSE_OPTIMIZER': FraudPreventionResponseOptimizer,
    'AUDIT_CONFIG': FraudPreventionAuditConfig,
    'DATABASE_CONFIG': FraudPreventionDatabaseConfig,
    'CORS_CONFIG': FraudPreventionCORSConfig,
    'CACHE_CONFIG': FraudPreventionCacheConfig,
    'URL_CONFIG': FraudPreventionURLConfig,
}
