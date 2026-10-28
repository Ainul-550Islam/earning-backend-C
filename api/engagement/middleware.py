# engagement/middleware.py
"""
Custom middleware for engagement system.
Handles user context, analytics, rate limiting, and other cross-cutting concerns.
"""
import time
import uuid
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

from .services.analytics_service import AnalyticsService
from .exceptions import RateLimitExceededError
from .dependencies import is_feature_enabled


class EngagementMiddleware(MiddlewareMixin):
    """
    Main engagement middleware that handles user context and analytics.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Process incoming request before view execution.
        """
        # Generate unique request ID
        request.engagement_request_id = str(uuid.uuid4())
        
        # Record request start time
        request.engagement_start_time = time.time()
        
        # Set up user context
        self._setup_user_context(request)
        
        # Set up tenant context
        self._setup_tenant_context(request)
        
        # Initialize analytics context
        request.engagement_analytics = {
            'request_id': request.engagement_request_id,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': self._get_client_ip(request),
            'path': request.path,
            'method': request.method,
        }
        
        return None
    
    def process_response(self, request, response):
        """
        Process response after view execution.
        """
        # Calculate request duration
        if hasattr(request, 'engagement_start_time'):
            duration = time.time() - request.engagement_start_time
            request.engagement_analytics['duration'] = duration
        
        # Record analytics if enabled
        if is_feature_enabled('analytics'):
            self._record_analytics(request, response)
        
        # Add engagement headers
        self._add_engagement_headers(request, response)
        
        return response
    
    def _setup_user_context(self, request):
        """Set up user-specific context."""
        user = request.user
        
        if not user.is_authenticated:
            request.engagement_user_context = {
                'is_authenticated': False,
                'is_active': False,
                'user_id': None,
                'tenant_id': None,
            }
            return
        
        # Get user status and other context
        request.engagement_user_context = {
            'is_authenticated': True,
            'is_active': getattr(user, 'status', 'active') == 'active',
            'user_id': user.id,
            'tenant_id': getattr(user, 'tenant_id', None),
            'username': user.username,
            'email': user.email,
            'date_joined': getattr(user, 'date_joined', None),
        }
        
        # Check for premium/subscription status
        request.engagement_user_context['has_premium'] = getattr(user, 'has_premium', False)
        request.engagement_user_context['subscription_level'] = getattr(user, 'subscription_level', 'free')
        
        # Check for beta access
        request.engagement_user_context['has_beta_access'] = getattr(user, 'has_beta_access', False)
    
    def _setup_tenant_context(self, request):
        """Set up tenant-specific context."""
        user = request.user
        
        if user.is_authenticated and hasattr(user, 'tenant'):
            request.engagement_tenant_context = {
                'tenant_id': user.tenant.id,
                'tenant_name': getattr(user.tenant, 'name', None),
                'tenant_slug': getattr(user.tenant, 'slug', None),
                'is_multi_tenant': True,
            }
        else:
            request.engagement_tenant_context = {
                'tenant_id': None,
                'tenant_name': None,
                'tenant_slug': None,
                'is_multi_tenant': False,
            }
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _record_analytics(self, request, response):
        """Record analytics data."""
        try:
            # Only record for engagement-related paths
            if not request.path.startswith('/engagement/'):
                return
            
            # Get user and tenant
            user = request.user if request.user.is_authenticated else None
            tenant = getattr(user, 'tenant', None) if user else None
            
            # Determine event type based on response
            event_type = 'api_request'
            if response.status_code >= 400:
                event_type = 'api_error'
            elif response.status_code >= 200 and response.status_code < 300:
                event_type = 'api_success'
            
            # Record analytics event
            AnalyticsService.record(
                user=user,
                event_type=event_type,
                properties=request.engagement_analytics,
                tenant=tenant
            )
            
        except Exception:
            # Silently ignore analytics errors
            pass
    
    def _add_engagement_headers(self, request, response):
        """Add engagement-specific headers."""
        if hasattr(response, 'headers'):
            # Add request ID header
            response.headers['X-Engagement-Request-ID'] = request.engagement_request_id
            
            # Add user context header (for debugging)
            if hasattr(request, 'engagement_user_context'):
                response.headers['X-Engagement-User-ID'] = str(request.engagement_user_context.get('user_id', ''))
                response.headers['X-Engagement-Authenticated'] = str(request.engagement_user_context.get('is_authenticated', False))
            
            # Add tenant context header
            if hasattr(request, 'engagement_tenant_context'):
                response.headers['X-Engagement-Tenant-ID'] = str(request.engagement_tenant_context.get('tenant_id', ''))


class EngagementRateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware for engagement endpoints.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Check rate limits before processing request.
        """
        # Only apply to engagement endpoints
        if not request.path.startswith('/engagement/'):
            return None
        
        # Get rate limit configuration
        rate_limit_config = self._get_rate_limit_config(request)
        
        if rate_limit_config:
            limit, period, scope = rate_limit_config
            
            # Check rate limit
            if self._is_rate_limited(request, limit, period, scope):
                return self._rate_limit_response(limit, period)
        
        return None
    
    def _get_rate_limit_config(self, request):
        """Get rate limit configuration for endpoint."""
        # Rate limit configurations (limit, period_in_seconds, scope)
        rate_limits = {
            '/engagement/daily-checkin/': (1, 86400, 'user'),  # 1 per day per user
            '/engagement/spin-wheel/': (10, 3600, 'user'),  # 10 per hour per user
            '/engagement/quests/': (100, 3600, 'user'),  # 100 per hour per user
            '/engagement/social/': (50, 3600, 'user'),  # 50 per hour per user
            '/engagement/shop/': (20, 3600, 'user'),  # 20 per hour per user
            '/engagement/notifications/': (100, 3600, 'user'),  # 100 per hour per user
        }
        
        # Find matching rate limit
        for path, config in rate_limits.items():
            if request.path.startswith(path):
                return config
        
        # Default rate limit for engagement endpoints
        return (1000, 3600, 'ip')  # 1000 per hour per IP
    
    def _is_rate_limited(self, request, limit, period, scope):
        """Check if request is rate limited."""
        # Generate cache key
        if scope == 'user' and request.user.is_authenticated:
            identifier = f"user_{request.user.id}"
        else:
            identifier = f"ip_{self._get_client_ip(request)}"
        
        cache_key = f"rate_limit:{hash(request.path)}:{identifier}"
        
        # Check current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return True
        
        # Increment counter
        cache.set(cache_key, current_count + 1, period)
        
        return False
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _rate_limit_response(self, limit, period):
        """Generate rate limit response."""
        return JsonResponse({
            'success': False,
            'error': 'Rate limit exceeded',
            'code': 'rate_limit_exceeded',
            'limit': limit,
            'period': period,
            'retry_after': period
        }, status=429)


class EngagementMaintenanceMiddleware(MiddlewareMixin):
    """
    Maintenance mode middleware for engagement system.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Check if system is under maintenance.
        """
        # Only apply to engagement endpoints
        if not request.path.startswith('/engagement/'):
            return None
        
        # Check maintenance mode flag
        maintenance_flag = cache.get('engagement_maintenance_mode', False)
        
        if maintenance_flag:
            return self._maintenance_response()
        
        return None
    
    def _maintenance_response(self):
        """Generate maintenance response."""
        return JsonResponse({
            'success': False,
            'error': 'System is under maintenance',
            'code': 'maintenance_mode',
            'message': 'We\'re currently performing maintenance. Please try again later.'
        }, status=503)


class EngagementSecurityMiddleware(MiddlewareMixin):
    """
    Security middleware for engagement endpoints.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Perform security checks.
        """
        # Only apply to engagement endpoints
        if not request.path.startswith('/engagement/'):
            return None
        
        # Check for suspicious patterns
        if self._is_suspicious_request(request):
            return self._security_response()
        
        return None
    
    def _is_suspicious_request(self, request):
        """Check for suspicious request patterns."""
        # Check for unusual user agents
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        suspicious_agents = ['bot', 'crawler', 'spider', 'scraper']
        
        for agent in suspicious_agents:
            if agent in user_agent:
                return True
        
        # Check for rapid successive requests (basic DoS protection)
        client_ip = self._get_client_ip(request)
        cache_key = f"security:requests:{client_ip}"
        
        recent_requests = cache.get(cache_key, 0)
        if recent_requests > 100:  # More than 100 requests in last minute
            return True
        
        # Increment counter
        cache.set(cache_key, recent_requests + 1, 60)
        
        return False
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _security_response(self):
        """Generate security response."""
        return JsonResponse({
            'success': False,
            'error': 'Security check failed',
            'code': 'security_blocked',
            'message': 'Your request has been blocked for security reasons.'
        }, status=403)


class EngagementCacheMiddleware(MiddlewareMixin):
    """
    Cache middleware for engagement endpoints.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Check cache for GET requests.
        """
        # Only cache GET requests to engagement endpoints
        if request.method != 'GET' or not request.path.startswith('/engagement/'):
            return None
        
        # Check if endpoint is cacheable
        if not self._is_cacheable_endpoint(request):
            return None
        
        # Generate cache key
        cache_key = self._generate_cache_key(request)
        
        # Check cache
        cached_response = cache.get(cache_key)
        if cached_response:
            return cached_response
        
        return None
    
    def process_response(self, request, response):
        """
        Cache GET responses.
        """
        # Only cache successful GET responses
        if (request.method != 'GET' or 
            not request.path.startswith('/engagement/') or
            response.status_code != 200):
            return response
        
        # Check if endpoint is cacheable
        if not self._is_cacheable_endpoint(request):
            return response
        
        # Generate cache key
        cache_key = self._generate_cache_key(request)
        
        # Cache response for 5 minutes
        cache.set(cache_key, response, 300)
        
        return response
    
    def _is_cacheable_endpoint(self, request):
        """Check if endpoint is cacheable."""
        cacheable_endpoints = [
            '/engagement/leaderboard/',
            '/engagement/achievements/',
            '/engagement/shop/items/',
            '/engagement/quests/',
        ]
        
        for endpoint in cacheable_endpoints:
            if request.path.startswith(endpoint):
                return True
        
        return False
    
    def _generate_cache_key(self, request):
        """Generate cache key for request."""
        # Include path, query params, and user context
        key_parts = [
            'engagement_cache',
            request.path,
            request.META.get('QUERY_STRING', ''),
        ]
        
        # Include user context for authenticated users
        if request.user.is_authenticated:
            key_parts.append(f"user_{request.user.id}")
        
        return ':'.join(key_parts)


class EngagementContextMiddleware(MiddlewareMixin):
    """
    Context middleware for engagement system.
    Provides additional context for views and services.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Set up additional context for engagement system.
        """
        # Set up feature flags context
        request.engagement_features = {
            'websockets': is_feature_enabled('websockets'),
            'real_time_notifications': is_feature_enabled('real_time_notifications'),
            'background_tasks': is_feature_enabled('background_tasks'),
            'analytics': is_feature_enabled('analytics'),
            'push_notifications': is_feature_enabled('push_notifications'),
            'image_processing': is_feature_enabled('image_processing'),
            'cloud_storage': is_feature_enabled('cloud_storage'),
            'webhooks': is_feature_enabled('webhooks'),
            'encryption': is_feature_enabled('encryption'),
            'monitoring': is_feature_enabled('monitoring'),
        }
        
        # Set up request metadata
        request.engagement_metadata = {
            'timestamp': timezone.now(),
            'version': '1.0.0',  # Should be from settings
            'environment': 'development',  # Should be from settings
        }
        
        return None


# ── Middleware Configuration ─────────────────────────────────────────────────────

ENGAGEMENT_MIDDLEWARE = [
    'engagement.middleware.EngagementContextMiddleware',
    'engagement.middleware.EngagementSecurityMiddleware',
    'engagement.middleware.EngagementRateLimitMiddleware',
    'engagement.middleware.EngagementMaintenanceMiddleware',
    'engagement.middleware.EngagementCacheMiddleware',
    'engagement.middleware.EngagementMiddleware',
]
