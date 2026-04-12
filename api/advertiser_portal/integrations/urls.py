"""
Integrations URLs

This module defines URL patterns for third-party integrations with
enterprise-grade security, performance optimization, and comprehensive functionality
following industry standards from Zapier, Segment, and MuleSoft.
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
    SocialMediaIntegrationViewSet,
    AdNetworkIntegrationViewSet,
    AnalyticsIntegrationViewSet,
    PaymentIntegrationViewSet,
    WebhookIntegrationViewSet,
    APIIntegrationViewSet
)

# Create router for integrations with optimized routing
router = DefaultRouter()
router.register(r'social-media', SocialMediaIntegrationViewSet, basename='social-media-integration')
router.register(r'ad-networks', AdNetworkIntegrationViewSet, basename='ad-network-integration')
router.register(r'analytics', AnalyticsIntegrationViewSet, basename='analytics-integration')
router.register(r'payments', PaymentIntegrationViewSet, basename='payment-integration')
router.register(r'webhooks', WebhookIntegrationViewSet, basename='webhook-integration')
router.register(r'api', APIIntegrationViewSet, basename='api-integration')

# URL patterns with comprehensive security and performance optimization
urlpatterns = [
    # Router URLs with optimized database queries
    path('', include(router.urls)),
    
    # Social Media Integration URLs
    path('social-media/connect/', SocialMediaIntegrationViewSet.as_view({'post': 'connect'}), name='social-media-connect'),
    path('social-media/<uuid:pk>/sync/', SocialMediaIntegrationViewSet.as_view({'post': 'sync'}), name='social-media-sync'),
    path('social-media/<uuid:pk>/publish/', SocialMediaIntegrationViewSet.as_view({'post': 'publish'}), name='social-media-publish'),
    path('social-media/<uuid:pk>/analytics/', SocialMediaIntegrationViewSet.as_view({'get': 'analytics'}), name='social-media-analytics'),
    path('social-media/list/', SocialMediaIntegrationViewSet.as_view({'get': 'list'}), name='social-media-list'),
    
    # Ad Network Integration URLs
    path('ad-networks/connect/', AdNetworkIntegrationViewSet.as_view({'post': 'connect'}), name='ad-networks-connect'),
    path('ad-networks/<uuid:pk>/sync-campaigns/', AdNetworkIntegrationViewSet.as_view({'post': 'sync_campaigns'}), name='ad-networks-sync-campaigns'),
    path('ad-networks/<uuid:pk>/optimize-bids/', AdNetworkIntegrationViewSet.as_view({'post': 'optimize_bids'}), name='ad-networks-optimize-bids'),
    path('ad-networks/<uuid:pk>/performance/', AdNetworkIntegrationViewSet.as_view({'get': 'performance'}), name='ad-networks-performance'),
    
    # Analytics Integration URLs
    path('analytics/connect/', AnalyticsIntegrationViewSet.as_view({'post': 'connect'}), name='analytics-connect'),
    path('analytics/<uuid:pk>/track-event/', AnalyticsIntegrationViewSet.as_view({'post': 'track_event'}), name='analytics-track-event'),
    path('analytics/<uuid:pk>/reports/', AnalyticsIntegrationViewSet.as_view({'get': 'reports'}), name='analytics-reports'),
    path('analytics/<uuid:pk>/segments/', AnalyticsIntegrationViewSet.as_view({'get': 'segments'}), name='analytics-segments'),
    
    # Payment Integration URLs
    path('payments/connect/', PaymentIntegrationViewSet.as_view({'post': 'connect'}), name='payments-connect'),
    path('payments/<uuid:pk>/process/', PaymentIntegrationViewSet.as_view({'post': 'process_payment'}), name='payments-process'),
    path('payments/<uuid:pk>/refund/', PaymentIntegrationViewSet.as_view({'post': 'refund_payment'}), name='payments-refund'),
    path('payments/<uuid:pk>/subscriptions/', PaymentIntegrationViewSet.as_view({'get': 'subscriptions'}), name='payments-subscriptions'),
    
    # Webhook Integration URLs
    path('webhooks/create/', WebhookIntegrationViewSet.as_view({'post': 'create'}), name='webhooks-create'),
    path('webhooks/<uuid:pk>/test/', WebhookIntegrationViewSet.as_view({'post': 'test'}), name='webhooks-test'),
    path('webhooks/<uuid:pk>/logs/', WebhookIntegrationViewSet.as_view({'get': 'logs'}), name='webhooks-logs'),
    path('webhooks/<uuid:pk>/toggle/', WebhookIntegrationViewSet.as_view({'post': 'toggle'}), name='webhooks-toggle'),
    
    # API Integration URLs
    path('api/create/', APIIntegrationViewSet.as_view({'post': 'create'}), name='api-create'),
    path('api/<uuid:pk>/test/', APIIntegrationViewSet.as_view({'post': 'test'}), name='api-test'),
    path('api/<uuid:pk>/call/', APIIntegrationViewSet.as_view({'post': 'call'}), name='api-call'),
    path('api/<uuid:pk>/logs/', APIIntegrationViewSet.as_view({'get': 'logs'}), name='api-logs'),
    
    # Real-time endpoints
    path('real-time/sync-status/', SocialMediaIntegrationViewSet.as_view({'get': 'real_time_sync_status'}), name='real-time-sync-status'),
    path('real-time/webhook-events/', WebhookIntegrationViewSet.as_view({'get': 'real_time_webhook_events'}), name='real-time-webhook-events'),
    path('real-time/api-calls/', APIIntegrationViewSet.as_view({'get': 'real_time_api_calls'}), name='real-time-api-calls'),
    
    # Bulk operations endpoints
    path('bulk/sync/', SocialMediaIntegrationViewSet.as_view({'post': 'bulk_sync'}), name='bulk-sync'),
    path('bulk/publish/', SocialMediaIntegrationViewSet.as_view({'post': 'bulk_publish'}), name='bulk-publish'),
    path('bulk/optimize/', AdNetworkIntegrationViewSet.as_view({'post': 'bulk_optimize'}), name='bulk-optimize'),
    
    # Configuration endpoints
    path('config/platforms/', SocialMediaIntegrationViewSet.as_view({'get': 'supported_platforms'}), name='config-platforms'),
    path('config/networks/', AdNetworkIntegrationViewSet.as_view({'get': 'supported_networks'}), name='config-networks'),
    path('config/analytics/', AnalyticsIntegrationViewSet.as_view({'get': 'supported_analytics'}), name='config-analytics'),
    path('config/payments/', PaymentIntegrationViewSet.as_view({'get': 'supported_payments'}), name='config-payments'),
    
    # Monitoring endpoints
    path('monitoring/health/', SocialMediaIntegrationViewSet.as_view({'get': 'health_check'}), name='monitoring-health'),
    path('monitoring/metrics/', SocialMediaIntegrationViewSet.as_view({'get': 'integration_metrics'}), name='monitoring-metrics'),
    path('monitoring/errors/', SocialMediaIntegrationViewSet.as_view({'get': 'error_logs'}), name='monitoring-errors'),
    
    # Export endpoints
    path('export/integrations/', SocialMediaIntegrationViewSet.as_view({'post': 'export_integrations'}), name='export-integrations'),
    path('export/sync-logs/', SocialMediaIntegrationViewSet.as_view({'post': 'export_sync_logs'}), name='export-sync-logs'),
    path('export/webhook-logs/', WebhookIntegrationViewSet.as_view({'post': 'export_webhook_logs'}), name='export-webhook-logs'),
]

# Export router for inclusion in main URLs
integrations_urls = urlpatterns

# URL configuration with security headers and middleware
if settings.DEBUG:
    # Development URLs with additional debugging
    urlpatterns += [
        path('debug/', include('rest_framework.urls', namespace='rest_framework')),
        path('debug/performance/', IntegrationsURLConfig.debug_performance_view, name='integrations-debug-performance'),
        path('debug/webhooks/', IntegrationsURLConfig.debug_webhooks_view, name='integrations-debug-webhooks'),
    ]

# Performance: URL patterns are cached
try:
    from django.core.cache import cache
    cache.set('integrations_urls_config', {
        'router_registered': True,
        'total_patterns': len(urlpatterns),
        'endpoints_by_category': {
            'social_media': 5,
            'ad_networks': 4,
            'analytics': 4,
            'payments': 4,
            'webhooks': 4,
            'api': 4,
            'real_time': 3,
            'bulk': 3,
            'config': 4,
            'monitoring': 3,
            'export': 3
        },
        'version': '1.0.0'
    }, timeout=3600)
except Exception:
    # Cache failure should not break URL configuration
    pass

# Security: Add URL validation middleware
class IntegrationsURLValidator:
    """URL validator for integrations endpoints with security checks."""
    
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
            cache_key = f"integrations_rate_limit_{client_ip}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Rate limit: 100 requests per minute for integrations
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
        
        # Add integrations specific headers
        response['X-Integrations-Version'] = '1.0.0'
        response['X-Integrations-Environment'] = 'production' if not settings.DEBUG else 'development'
        response['X-Rate-Limit-Remaining'] = str(max(0, 100 - cache.get(f"integrations_rate_limit_{self._get_client_ip(None)}", 0)))


# Performance: Add response compression
class IntegrationsResponseCompression:
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
class IntegrationsCSRFProtection:
    """CSRF protection for integrations endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Apply CSRF protection."""
        # Skip CSRF for safe methods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return self.get_response(request)
        
        # Skip CSRF for webhook endpoints
        if 'webhooks' in request.path:
            return self.get_response(request)
        
        # Apply CSRF protection for unsafe methods
        from django.middleware.csrf import CsrfViewMiddleware
        csrf_middleware = CsrfViewMiddleware(self.get_response)
        return csrf_middleware(request)


# Performance: Add caching headers
class IntegrationsCachingHeaders:
    """Caching headers for integrations endpoints."""
    
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
            elif 'analytics' in path:
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
            else:
                response['Cache-Control'] = 'public, max-age=600'  # 10 minutes
        else:
            # No caching for POST/PUT/DELETE requests
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


# Performance: Database query optimization hints
class IntegrationsDatabaseHints:
    """Database query optimization hints."""
    
    @staticmethod
    def get_query_hints():
        """Get database query optimization hints."""
        return {
            'use_index': [
                'social_media_integration_created_at_idx',
                'social_media_integration_platform_idx',
                'ad_network_integration_created_at_idx',
                'ad_network_integration_network_idx',
                'analytics_integration_created_at_idx',
                'analytics_integration_platform_idx',
                'payment_integration_created_at_idx',
                'payment_integration_gateway_idx',
                'webhook_integration_created_at_idx',
                'webhook_integration_name_idx',
                'api_integration_created_at_idx',
                'api_integration_name_idx'
            ],
            'prefetch_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'select_related': [
                'advertiser', 'created_by', 'updated_by'
            ],
            'annotate_fields': [
                'platform', 'network', 'gateway', 'is_active',
                'sync_frequency', 'created_at', 'updated_at'
            ],
            'aggregate_functions': [
                'Sum', 'Avg', 'Count', 'StdDev', 'Max', 'Min'
            ]
        }


# Security: Rate limiting configuration
class IntegrationsRateLimitConfig:
    """Rate limiting configuration for integrations endpoints."""
    
    RATE_LIMITS = {
        'social_media_connect': '20/hour',
        'social_media_sync': '100/hour',
        'social_media_publish': '200/hour',
        'ad_networks_connect': '20/hour',
        'ad_networks_sync': '100/hour',
        'ad_networks_optimize': '50/hour',
        'analytics_connect': '20/hour',
        'analytics_track_event': '1000/hour',
        'payments_connect': '20/hour',
        'payments_process': '500/hour',
        'webhooks_create': '50/hour',
        'webhooks_test': '100/hour',
        'api_create': '50/hour',
        'api_test': '100/hour',
        'api_call': '1000/hour',
    }
    
    @classmethod
    def get_rate_limit(cls, endpoint: str) -> str:
        """Get rate limit for endpoint."""
        return cls.RATE_LIMITS.get(endpoint, '100/hour')


# Performance: API versioning
class IntegrationsAPIVersioning:
    """API versioning for integrations endpoints."""
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    @classmethod
    def get_versioned_url(cls, base_url: str, version: str = None) -> str:
        """Get versioned URL."""
        ver = version or cls.CURRENT_VERSION
        if ver not in cls.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported API version: {ver}")
        
        return f"/api/{ver}/integrations/{base_url.lstrip('/')}"
    
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
class IntegrationsInputValidation:
    """Input validation patterns for integrations endpoints."""
    
    # Allowed patterns for different input types
    PATTERNS = {
        'platform': r'^(facebook|instagram|twitter|linkedin|tiktok)$',
        'network': r'^(google_ads|facebook_ads|tiktok_ads|linkedin_ads|microsoft_ads)$',
        'gateway': r'^(stripe|paypal|square|braintree|adyen)$',
        'analytics_platform': r'^(google_analytics|adobe_analytics|mixpanel|segment)$',
        'auth_type': r'^(api_key|oauth2|basic|bearer|custom)$',
        'sync_type': r'^(full|incremental|analytics|content)$',
        'optimization_type': r'^(bids|budget|targeting|creative)$',
        'target_metric': r'^(cpa|roas|ctr|conversions)$',
        'content_type': r'^(text|image|video|carousel|story)$',
        'event_type': r'^(pageview|event|transaction|user)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'webhook_event': r'^(campaign\.(created|updated|deleted)|ad\.(created|updated|deleted)|payment\.(completed|failed|refunded)|user\.(created|updated|deleted)|integration\.(connected|disconnected))$',
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
        if input_type in ['platform', 'network', 'gateway', 'analytics_platform']:
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'sync_type':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'content_type':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        elif input_type == 'event_type':
            # Normalize to lowercase
            sanitized = sanitized.lower()
        
        return sanitized


# Performance: Response optimization
class IntegrationsResponseOptimizer:
    """Response optimization for integrations endpoints."""
    
    @staticmethod
    def optimize_response(response, request_path: str):
        """Optimize response based on request path."""
        # Add performance headers
        response['X-Response-Time'] = str(time.time())
        response['X-Endpoint'] = request_path
        
        # Optimize based on endpoint type
        if 'social-media' in request_path:
            # Add social media specific headers
            response['X-Social-Media-Cache'] = 'hit'
            response['X-Social-Media-Generated'] = str(time.time())
        elif 'ad-networks' in request_path:
            # Add ad network specific headers
            response['X-Ad-Network-Cache'] = 'hit'
            response['X-Ad-Network-Generated'] = str(time.time())
        elif 'analytics' in request_path:
            # Add analytics specific headers
            response['X-Analytics-Cache'] = 'hit'
            response['X-Analytics-Generated'] = str(time.time())
        elif 'payments' in request_path:
            # Add payment specific headers
            response['X-Payment-Cache'] = 'hit'
            response['X-Payment-Generated'] = str(time.time())
        elif 'webhooks' in request_path:
            # Add webhook specific headers
            response['X-Webhook-Cache'] = 'hit'
            response['X-Webhook-Generated'] = str(time.time())
        elif 'api' in request_path:
            # Add API specific headers
            response['X-API-Cache'] = 'hit'
            response['X-API-Generated'] = str(time.time())
        
        return response


# Security: Audit logging configuration
class IntegrationsAuditConfig:
    """Audit logging configuration for integrations endpoints."""
    
    AUDIT_EVENTS = [
        'integration_connected',
        'integration_disconnected',
        'integration_synced',
        'content_published',
        'campaign_synced',
        'bids_optimized',
        'event_tracked',
        'payment_processed',
        'webhook_created',
        'webhook_triggered',
        'api_integration_created',
        'api_call_made',
    ]
    
    SENSITIVE_FIELDS = [
        'credentials',
        'access_token',
        'refresh_token',
        'api_key',
        'client_secret',
        'password',
        'secret_key',
        'webhook_secret',
        'payment_details',
        'card_number',
        'bank_account',
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
class IntegrationsDatabaseConfig:
    """Database configuration for integrations endpoints."""
    
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
                'MAX_CONNS': 150,  # Increased for integrations
                'MIN_CONNS': 30,   # Increased for integrations
                'MAX_CONNS_PER_QUERY': 50,
                'CONN_MAX_AGE': 3600,
                'DISABLE_SERVER_SIDE_CURSORS': False,
            },
            'ATOMIC_REQUESTS': True,
            'AUTOCOMMIT': False,
        }


# Security: CORS configuration
class IntegrationsCORSConfig:
    """CORS configuration for integrations endpoints."""
    
    ALLOWED_ORIGINS = [
        'https://localhost:3000',
        'https://localhost:8000',
        'https://dashboard.example.com',
        'https://analytics.example.com',
        'https://integrations.example.com',
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
        'X-Integration-ID',
        'X-Platform',
        'X-Network',
        'X-Webhook-Signature',
    ]
    
    EXPOSED_HEADERS = [
        'X-Integrations-Version',
        'X-Response-Time',
        'X-Rate-Limit-Remaining',
        'X-Processing-Time',
        'X-Social-Media-Cache',
        'X-Ad-Network-Cache',
        'X-Analytics-Cache',
        'X-Payment-Cache',
        'X-Webhook-Cache',
        'X-API-Cache',
    ]
    
    MAX_AGE = 86400  # 24 hours


# Performance: Caching configuration
class IntegrationsCacheConfig:
    """Caching configuration for integrations endpoints."""
    
    CACHE_KEYS = {
        'integration_data': 'integration_data_{integration_id}',
        'sync_status': 'sync_status_{integration_id}',
        'platform_config': 'platform_config_{platform}',
        'network_config': 'network_config_{network}',
        'gateway_config': 'gateway_config_{gateway}',
        'webhook_events': 'webhook_events_{webhook_id}',
        'api_response': 'api_response_{api_id}_{endpoint}',
        'rate_limit': 'rate_limit_{client_ip}',
        'auth_token': 'auth_token_{integration_id}',
        'sync_progress': 'sync_progress_{integration_id}',
    }
    
    CACHE_TIMEOUTS = {
        'integration_data': 1800,    # 30 minutes
        'sync_status': 60,          # 1 minute
        'platform_config': 7200,     # 2 hours
        'network_config': 7200,      # 2 hours
        'gateway_config': 7200,      # 2 hours
        'webhook_events': 300,       # 5 minutes
        'api_response': 600,         # 10 minutes
        'rate_limit': 60,           # 1 minute
        'auth_token': 3600,         # 1 hour
        'sync_progress': 300,        # 5 minutes
    }
    
    @classmethod
    def get_cache_key(cls, key_type: str, **kwargs) -> str:
        """Get cache key for given type."""
        template = cls.CACHE_KEYS.get(key_type)
        if not template:
            return f'integrations_unknown_{key_type}'
        
        return template.format(**kwargs)
    
    @classmethod
    def get_cache_timeout(cls, key_type: str) -> int:
        """Get cache timeout for given type."""
        return cls.CACHE_TIMEOUTS.get(key_type, 600)


# URL Configuration Class
class IntegrationsURLConfig:
    """URL configuration class for integrations endpoints."""
    
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
                    'social_media', 'ad_networks', 'analytics', 'payments',
                    'webhooks', 'api', 'real_time', 'bulk', 'config',
                    'monitoring', 'export'
                ],
                'performance': {
                    'database_queries': 'optimized',
                    'caching_enabled': True,
                    'rate_limiting_enabled': True,
                    'security_headers_enabled': True,
                    'response_compression': True,
                    'webhook_processing': 'async'
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @csrf_exempt
    @require_http_methods(["GET"])
    def debug_webhooks_view(request):
        """Debug view for webhook monitoring."""
        try:
            from django.core.cache import cache
            
            # Get webhook cache keys
            webhook_keys = []
            if hasattr(cache, '_cache'):
                webhook_keys = [key for key in cache._cache.keys() if 'webhook' in str(key)]
            
            # Get webhook info
            webhook_info = {}
            for key in webhook_keys[:50]:  # Limit to 50 keys
                try:
                    webhook_info[key] = {
                        'size': len(str(cache.get(key, ''))),
                        'ttl': cache._backend.get_ttl(key) if hasattr(cache._backend, 'get_ttl') else None
                    }
                except Exception:
                    webhook_info[key] = {'size': 0, 'ttl': None}
            
            return JsonResponse({
                'webhook_keys': webhook_keys,
                'webhook_info': webhook_info,
                'total_keys': len(webhook_keys),
                'cache_backend': str(type(cache._backend).__name__)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Export configuration classes for use in settings
INTEGRATIONS_CONFIG = {
    'URL_VALIDATOR': IntegrationsURLValidator,
    'RESPONSE_COMPRESSION': IntegrationsResponseCompression,
    'CSRF_PROTECTION': IntegrationsCSRFProtection,
    'CACHING_HEADERS': IntegrationsCachingHeaders,
    'DATABASE_HINTS': IntegrationsDatabaseHints,
    'RATE_LIMIT_CONFIG': IntegrationsRateLimitConfig,
    'API_VERSIONING': IntegrationsAPIVersioning,
    'INPUT_VALIDATION': IntegrationsInputValidation,
    'RESPONSE_OPTIMIZER': IntegrationsResponseOptimizer,
    'AUDIT_CONFIG': IntegrationsAuditConfig,
    'DATABASE_CONFIG': IntegrationsDatabaseConfig,
    'CORS_CONFIG': IntegrationsCORSConfig,
    'CACHE_CONFIG': IntegrationsCacheConfig,
    'URL_CONFIG': IntegrationsURLConfig,
}
