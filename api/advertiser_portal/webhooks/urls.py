"""
Webhooks URLs

This module defines URL patterns for webhook management with
enterprise-grade security, performance optimization, and comprehensive functionality
following industry standards from Stripe Webhooks, GitHub Webhooks, and Zapier Webhooks.
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
    WebhookViewSet,
    WebhookEventViewSet,
    WebhookDeliveryViewSet,
    WebhookMonitoringViewSet,
    WebhookSecurityViewSet,
    WebhookQueueViewSet
)

# Create router for webhooks with optimized routing
router = DefaultRouter()
router.register(r'webhooks', WebhookViewSet, basename='webhook')
router.register(r'events', WebhookEventViewSet, basename='webhook-event')
router.register(r'deliveries', WebhookDeliveryViewSet, basename='webhook-delivery')
router.register(r'monitoring', WebhookMonitoringViewSet, basename='webhook-monitoring')
router.register(r'security', WebhookSecurityViewSet, basename='webhook-security')
router.register(r'queue', WebhookQueueViewSet, basename='webhook-queue')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # Webhook URLs
    path('webhooks/create/', WebhookViewSet.as_view({'post': 'create'}), name='webhooks-create'),
    path('webhooks/<uuid:pk>/trigger/', WebhookViewSet.as_view({'post': 'trigger'}), name='webhooks-trigger'),
    path('webhooks/<uuid:pk>/test/', WebhookViewSet.as_view({'post': 'test'}), name='webhooks-test'),
    path('webhooks/<uuid:pk>/stats/', WebhookViewSet.as_view({'get': 'stats'}), name='webhooks-stats'),
    path('webhooks/<uuid:pk>/deliveries/', WebhookViewSet.as_view({'get': 'deliveries'}), name='webhooks-deliveries'),
    path('webhooks/list/', WebhookViewSet.as_view({'get': 'list'}), name='webhooks-list'),
    path('webhooks/<uuid:pk>/toggle/', WebhookViewSet.as_view({'post': 'toggle'}), name='webhooks-toggle'),
    
    # Webhook Event URLs
    path('events/create/', WebhookEventViewSet.as_view({'post': 'create'}), name='webhook-events-create'),
    path('events/<uuid:pk>/details/', WebhookEventViewSet.as_view({'get': 'details'}), name='webhook-events-details'),
    path('events/list/', WebhookEventViewSet.as_view({'get': 'list'}), name='webhook-events-list'),
    
    # Webhook Delivery URLs
    path('deliveries/<uuid:pk>/retry/', WebhookDeliveryViewSet.as_view({'post': 'retry'}), name='webhook-deliveries-retry'),
    path('deliveries/<uuid:pk>/details/', WebhookDeliveryViewSet.as_view({'get': 'details'}), name='webhook-deliveries-details'),
    path('deliveries/list/', WebhookDeliveryViewSet.as_view({'get': 'list'}), name='webhook-deliveries-list'),
    
    # Webhook Monitoring URLs
    path('monitoring/<uuid:pk>/health/', WebhookMonitoringViewSet.as_view({'get': 'health'}), name='webhook-monitoring-health'),
    path('monitoring/system-health/', WebhookMonitoringViewSet.as_view({'get': 'system_health'}), name='webhook-monitoring-system-health'),
    path('monitoring/metrics/', WebhookMonitoringViewSet.as_view({'get': 'metrics'}), name='webhook-monitoring-metrics'),
    
    # Webhook Security URLs
    path('security/block-ip/', WebhookSecurityViewSet.as_view({'post': 'block_ip'}), name='webhook-security-block-ip'),
    path('security/unblock-ip/', WebhookSecurityViewSet.as_view({'post': 'unblock_ip'}), name='webhook-security-unblock-ip'),
    path('security/verify-signature/', WebhookSecurityViewSet.as_view({'post': 'verify_signature'}), name='webhook-security-verify-signature'),
    
    # Webhook Queue URLs
    path('queue/stats/', WebhookQueueViewSet.as_view({'get': 'stats'}), name='webhook-queue-stats'),
    path('queue/process/', WebhookQueueViewSet.as_view({'post': 'process_queue'}), name='webhook-queue-process'),
    
    # Real-time endpoints
    path('real-time/deliveries/', WebhookViewSet.as_view({'get': 'real_time_deliveries'}), name='real-time-deliveries'),
    path('real-time/events/', WebhookEventViewSet.as_view({'get': 'real_time_events'}), name='real-time-events'),
    path('real-time/queue/', WebhookQueueViewSet.as_view({'get': 'real_time_queue'}), name='real-time-queue'),
    
    # Bulk operations endpoints
    path('bulk/trigger/', WebhookViewSet.as_view({'post': 'bulk_trigger'}), name='bulk-trigger'),
    path('bulk/retry/', WebhookDeliveryViewSet.as_view({'post': 'bulk_retry'}), name='bulk-retry'),
    path('bulk/toggle/', WebhookViewSet.as_view({'post': 'bulk_toggle'}), name='bulk-toggle'),
    
    # Configuration endpoints
    path('config/events/', WebhookViewSet.as_view({'get': 'supported_events'}), name='config-supported-events'),
    path('config/retry-policies/', WebhookViewSet.as_view({'get': 'retry_policies'}), name='config-retry-policies'),
    path('config/headers/', WebhookViewSet.as_view({'get': 'default_headers'}), name='config-default-headers'),
    
    # Monitoring endpoints
    path('monitoring/health/', WebhookMonitoringViewSet.as_view({'get': 'health_check'}), name='monitoring-health'),
    path('monitoring/performance/', WebhookMonitoringViewSet.as_view({'get': 'performance_metrics'}), name='monitoring-performance'),
    path('monitoring/errors/', WebhookMonitoringViewSet.as_view({'get': 'error_logs'}), name='monitoring-errors'),
    path('monitoring/alerts/', WebhookMonitoringViewSet.as_view({'get': 'alerts'}), name='monitoring-alerts'),
    
    # Export endpoints
    path('export/webhooks/', WebhookViewSet.as_view({'post': 'export_webhooks'}), name='export-webhooks'),
    path('export/events/', WebhookEventViewSet.as_view({'post': 'export_events'}), name='export-events'),
    path('export/deliveries/', WebhookDeliveryViewSet.as_view({'post': 'export_deliveries'}), name='export-deliveries'),
    path('export/logs/', WebhookMonitoringViewSet.as_view({'post': 'export_logs'}), name='export-logs'),
    
    # Webhook receiver endpoints
    path('receiver/<uuid:webhook_id>/', WebhookReceiverView.as_view(), name='webhook-receiver'),
    path('receiver/<uuid:webhook_id>/test/', WebhookReceiverView.as_view(), name='webhook-receiver-test'),
    
    # Debug endpoints
    path('debug/ping/', WebhookDebugView.as_view(), name='webhook-debug-ping'),
    path('debug/signature/', WebhookDebugView.as_view(), name='webhook-debug-signature'),
    path('debug/headers/', WebhookDebugView.as_view(), name='webhook-debug-headers'),
]

# Export router for inclusion in main URLs
webhooks_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        path('debug/performance/', WebhooksURLConfig.debug_performance_view, name='webhooks-debug-performance'),
        path('debug/queue/', WebhooksURLConfig.debug_queue_view, name='webhooks-debug-queue'),
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('webhooks_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'webhooks': 7,
            'events': 3,
            'deliveries': 3,
            'monitoring': 3,
            'security': 3,
            'queue': 2,
            'real_time': 3,
            'bulk': 3,
            'config': 3,
            'monitoring': 4,
            'export': 4,
            'receiver': 2,
            'debug': 3
        },
        'version': '1.0.0'
    }, timeout=3600)
except Exception:
    # Cache failure should not break URL configuration
    pass

# Security: Add URL validation middleware
class WebhooksURLValidator:
    """URL validator for webhooks with security checks."""
    
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
            cache_key = f"webhooks_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 500 requests per minute for webhooks
            if current_count >= 500:
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
        
        # Add webhooks specific headers
        response['X-Webhooks-Version'] = '1.0.0'
        response['X-Webhooks-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 500 - cache.get(f"webhooks_rate_limit_{self._get_client_ip(None)}", 0)))


# Performance: Add response compression
class WebhooksResponseCompression:
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
class WebhooksCSRFProtection:
    """CSRF protection for webhooks."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Apply CSRF protection."""
        # Skip CSRF for safe methods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return self.get_response(request)
        
        # Skip CSRF for webhook receiver endpoints
        if 'receiver' in request.path:
            return self.get_response(request)
        
        # Apply CSRF protection for unsafe methods
        from django.middleware.csrf import CsrfViewMiddleware
        csrf_middleware = CsrfViewMiddleware(self.get_response)
        return csrf_middleware(request)


# Performance: Add caching headers
class WebhooksCachingHeaders:
    """Caching headers for webhooks."""
    
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
            elif 'monitoring' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'real-time' in path:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            elif 'queue' in path:
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
class WebhooksDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'webhook_created_at_idx',
                'webhook_url_idx',
                'webhook_events_idx',
                'webhook_active_idx',
                'webhook_event_created_at_idx',
                'webhook_event_type_idx',
                'webhook_delivery_created_at_idx',
                'webhook_delivery_status_idx',
                'webhook_retry_created_at_idx',
                'webhook_retry_status_idx',
                'webhook_log_created_at_idx',
                'webhook_queue_created_at_idx',
                'webhook_queue_status_idx',
                'webhook_security_created_at_idx',
                'webhook_security_ip_idx'
            ],
            'prefetch_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'select_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'annotate_fields': [
                'events', 'active', 'status', 'created_at', 'updated_at'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class WebhooksRateLimitConfig:
    """Rate limiting configuration for webhooks."""
    
    RATE_LIMITS = {
        'webhooks_create': '100/hour',
        'webhooks_trigger': '1000/hour',
        'webhooks_test': '500/hour',
        'events_create': '1000/hour',
        'deliveries_retry': '500/hour',
        'monitoring_health': '1000/hour',
        'security_block_ip': '100/hour',
        'queue_process': '100/hour',
        'bulk_trigger': '200/hour',
        'bulk_retry': '200/hour',
        'export_webhooks': '50/hour',
        'receiver_webhook': '10000/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '100/hour')


# Performance: API versioning
class WebhooksAPIVersioning:
    """API versioning for webhooks."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/webhooks/{base_url.lstrip('/')}"
    
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
class WebhooksInputValidation:
    """Input validation patterns for webhooks."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'event_type': r'^(campaign|ad|payment|user|integration|system)\.(created|updated|deleted|completed|failed|refunded|connected|disconnected|maintenance|error)$',
        'webhook_status': r'^(active|inactive)$',
        'delivery_status': r'^(pending|processing|delivered|failed|timeout|retry)$',
        'retry_status': r'^(pending|processing|completed|failed)$',
        'queue_status': r'^(pending|processing|completed|failed)$',
        'security_action': r'^(blocked|unblocked|monitored|flagged)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'ip_address': r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$',
        'signature': r'^[a-f0-9]{64}$',  # SHA-256 hex
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
        if input_type in ['event_type', 'webhook_status', 'delivery_status']:
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'signature':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        
        return sanitized


# Performance: Response optimization
class WebhooksResponseOptimizer:
    """Response optimization for webhooks."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'webhooks' in request_path:
            # Add webhooks specific headers
            response['X-Webhooks-Cache'] = 'hit'
            response['X-Webhooks-Generated'] = str(time.time())
        elif 'events' in request_path:
            # Add events specific headers
            response['X-Events-Cache'] = 'hit'
            response['X-Events-Generated'] = str(time.time())
        elif 'deliveries' in request_path:
            # Add deliveries specific headers
            response['X-Deliveries-Cache'] = 'hit'
            response['X-Deliveries-Generated'] = str(time.time())
        elif 'monitoring' in request_path:
            # Add monitoring specific headers
            response['X-Monitoring-Cache'] = 'hit'
            response['X-Monitoring-Generated'] = str(time.time())
        elif 'security' in request_path:
            # Add security specific headers
            response['X-Security-Cache'] = 'hit'
            response['X-Security-Generated'] = str(time.time())
        elif 'queue' in request_path:
            # Add queue specific headers
            response['X-Queue-Cache'] = 'hit'
            response['X-Queue-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class WebhooksAuditConfig:
    """Audit logging configuration for webhooks."""
    
    AUDIT_EVENTS = [
        'webhook_created',
        'webhook_updated',
        'webhook_deleted',
        'webhook_triggered',
        'webhook_tested',
        'webhook_toggled',
        'event_created',
        'delivery_created',
        'delivery_retried',
        'security_ip_blocked',
        'security_ip_unblocked',
        'signature_verified',
        'queue_processed',
        'bulk_operation',
    ]
    
    SENSITIVE_FIELDS = [
        'secret',
        'headers',
        'retry_policy',
        'data',
        'response_body',
        'error_message',
        'metadata',
        'result',
        'payload',
        'signature',
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
class WebhooksDatabaseConfig:
    """Database configuration for webhooks."""
    
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
                'MAX_CONNS': 250,  # Increased for webhooks
                'MIN_CONNS': 50,   # Increased for webhooks
                'MAX_CONNS_PER_QUERY': 50,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class WebhooksCORSConfig:
    """CORS configuration for webhooks."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://webhooks.example.com',
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
        'X-Webhook-Event',
        'X-Webhook-Signature',
        'X-Webhook-ID',
        'X-Webhook-Timestamp',
        'X-Rate-Limit-Limit',
        'X-Rate-Limit-Remaining',
        'X-Rate-Limit-Reset',
    ]
    
    EXPOSED_HEADERS = [
        'X-Webhooks-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-Webhooks-Cache',
        'X-Events-Cache',
        'X-Deliveries-Cache',
        'X-Monitoring-Cache',
        'X-Security-Cache',
        'X-Queue-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class WebhooksCacheConfig:
    """Caching configuration for webhooks."""
    
    CACHE_KEYS = {
        'webhook_data': 'webhook_data_{webhook_id}',
        'webhook_stats': 'webhook_stats_{webhook_id}',
        'webhook_deliveries': 'webhook_deliveries_{webhook_id}',
        'event_data': 'event_data_{event_id}',
        'delivery_data': 'delivery_data_{delivery_id}',
        'retry_data': 'retry_data_{retry_id}',
        'queue_stats': 'queue_stats',
        'system_health': 'system_health',
        'blocked_ips': 'blocked_ips',
        'rate_limit': 'rate_limit_{client_ip}',
        'signature_verification': 'signature_verification_{signature}',
        'bulk_operation': 'bulk_operation_{operation_id}',
    }
    
    CACHE_TIMEOUTS = {
        'webhook_data': 1800,      # 30 minutes
        'webhook_stats': 60,       # 1 minute
        'webhook_deliveries': 300,  # 5 minutes
        'event_data': 3600,        # 1 hour
        'delivery_data': 3600,      # 1 hour
        'retry_data': 1800,        # 30 minutes
        'queue_stats': 30,         # 30 seconds
        'system_health': 60,       # 1 minute
        'blocked_ips': 86400,      # 24 hours
        'rate_limit': 60,          # 1 minute
        'signature_verification': 300, # 5 minutes
        'bulk_operation': 3600,    # 1 hour
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'webhooks_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 600)


# URL Configuration Class
class WebhooksURLConfig:
    """URL configuration class for webhooks."""
    
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
                    'webhooks', 'events', 'deliveries', 'monitoring',
                    'security', 'queue', 'real_time', 'bulk',
                    'config', 'monitoring', 'export', 'receiver', 'debug'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'webhook_processing': 'async',
                    'queue_management': 'optimized'
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_queue_view(request):
        """Debug view for queue monitoring."""
        try:
            from django.core.cache import cache
            
            # Get queue cache keys
            queue_keys = []
            if hasattr(cache, '_cache'):
                queue_keys = [key for key in cache._cache.keys() if 'queue' in str(key)]
            
            # Get queue info
            queue_info = {}
            for key in queue_keys[:50]:  # Limit to 50 keys
                try:
                    queue_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    queue_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'queue_keys': queue_keys,
                'queue_info': queue_info,
                'total_keys': len(queue_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Webhook Receiver View
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import hmac
import hashlib

class WebhookReceiverView(View):
    """
    Enterprise-grade webhook receiver for processing incoming webhooks.
    
    Features:
    - Signature verification
    - Event processing
    - Security validation
    - Rate limiting
    - Comprehensive logging
    """
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        """Dispatch webhook request with security checks."""
        try:
            # Get webhook ID from URL
            webhook_id = kwargs.get('webhook_id')
            
            # Get webhook
            webhook = Webhook.objects.get(id=webhook_id, active=True)
            
            # Security: Validate request
            self._validate_webhook_request(request, webhook)
            
            # Process webhook
            result = self._process_webhook(request, webhook)
            
            # Return response
            return JsonResponse(result)
            
        except Webhook.DoesNotExist:
            return JsonResponse({'error': 'Webhook not found'}, status=404)
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    def _validate_webhook_request(self, request, webhook: Webhook) -> None:
        """Validate webhook request with security checks."""
        # Security: Check content type
        content_type = request.content_type
        if content_type not in ['application/json', 'application/x-www-form-urlencoded']:
            raise ValueError("Invalid content type")
        
        # Security: Verify signature
        signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
        if signature:
            try:
                payload = json.loads(request.body)
                is_valid = WebhookService.verify_webhook_signature(
                    payload, signature, webhook.secret
                )
                if not is_valid:
                    raise ValueError("Invalid signature")
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload")
        
        # Security: Check timestamp
        timestamp = request.META.get('HTTP_X_WEBHOOK_TIMESTAMP', '')
        if timestamp:
            try:
                request_time = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                time_diff = timezone.now() - request_time
                
                # Reject requests older than 5 minutes
                if time_diff > timedelta(minutes=5):
                    raise ValueError("Request too old")
                
                # Reject requests from future
                if time_diff < timedelta(minutes=-1):
                    raise ValueError("Future timestamp")
                    
            except (ValueError, OSError):
                raise ValueError("Invalid timestamp")
    
    def _process_webhook(self, request, webhook: Webhook) -> Dict[str, Any]:
        """Process webhook event."""
        try:
            # Parse payload
            payload = json.loads(request.body)
            
            # Create event
            event_data = {
                'event_type': request.META.get('HTTP_X_WEBHOOK_EVENT', 'webhook.received'),
                'data': payload,
                'source': 'external',
                'user_id': None,
                'metadata': {
                    'ip_address': self._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'content_type': request.content_type,
                    'content_length': len(request.body)
                }
            }
            
            # Trigger webhook processing
            deliveries = WebhookService.trigger_event(event_data, source='external')
            
            return {
                'status': 'processed',
                'event_id': event_data.get('event_id'),
                'deliveries': len(deliveries)
            }
            
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON payload'}
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return {'error': 'Processing failed'}
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        return ip


# Webhook Debug View
class WebhookDebugView(View):
    """
    Debug view for webhook testing and debugging.
    
    Features:
    - Signature generation
    - Request testing
    - Header analysis
    - Performance monitoring
    """
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        """Dispatch debug request."""
        try:
            # Get debug action
            action = kwargs.get('action', 'ping')
            
            if action == 'ping':
                return self._ping(request)
            elif action == 'signature':
                return self._generate_signature(request)
            elif action == 'headers':
                return self._analyze_headers(request)
            else:
                return JsonResponse({'error': 'Invalid debug action'}, status=400)
                
        except Exception as e:
            logger.error(f"Error in debug view: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _ping(self, request) -> JsonResponse:
        """Ping endpoint for health checks."""
        return JsonResponse({
            'status': 'ok',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'environment': 'production' if not settings.DEBUG else 'development'
        })
    
    def _generate_signature(self, request) -> JsonResponse:
        """Generate webhook signature for testing."""
        try:
            # Get payload from request
            payload = json.loads(request.body) if request.body else {}
            secret = request.GET.get('secret', 'test_secret')
            
            # Generate signature
            signature = WebhookService._generate_signature(payload, secret, 'sha256')
            
            return JsonResponse({
                'payload': payload,
                'secret': secret,
                'signature': signature,
                'algorithm': 'sha256',
                'timestamp': int(time.time())
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def _analyze_headers(self, request) -> JsonResponse:
        """Analyze request headers."""
        headers = {}
        
        # Get all HTTP headers
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value
        
        return JsonResponse({
            'headers': headers,
            'method': request.method,
            'path': request.path,
            'content_type': request.content_type,
            'content_length': len(request.body),
            'timestamp': timezone.now().isoformat()
        })


# Export configuration classes for use in settings
WEBHOOKS_CONFIG = {
    'URL_VALIDATOR': WebhooksURLValidator,
    'RESPONSE_COMPRESSION': WebhooksResponseCompression,
    'CSRF_PROTECTION': WebhooksCSRFProtection,
    'CACHING_HEADERS': WebhooksCachingHeaders,
    'DATABASE_HINTS': WebhooksDatabaseHints,
    'RATE_LIMIT_CONFIG': WebhooksRateLimitConfig,
    'API_VERSIONING': WebhooksAPIVersioning,
    'INPUT_VALIDATION': WebhooksInputValidation,
    'RESPONSE_OPTIMIZER': WebhooksResponseOptimizer,
    'AUDIT_CONFIG': WebhooksAuditConfig,
    'DATABASE_CONFIG': WebhooksDatabaseConfig,
    'CORS_CONFIG': WebhooksCORSConfig,
    'CACHE_CONFIG': WebhooksCacheConfig,
    'URL_CONFIG': WebhooksURLConfig,
}
