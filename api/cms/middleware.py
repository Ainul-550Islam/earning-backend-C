# api/cms/middleware.py
"""CMS Django middleware."""
import time
import logging
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MaintenanceModeMiddleware:
    """Block requests during maintenance mode (except admin + allowed IPs)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip admin and API health check
        path = request.path
        if path.startswith('/admin/') or path == '/api/cms/health/':
            return self.get_response(request)

        try:
            from api.cms.services_new.WithdrawalService import SiteConfigService
            ip = request.META.get('REMOTE_ADDR', '')
            if SiteConfigService.is_maintenance(ip=ip):
                if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff:
                    return self.get_response(request)
                from api.cms.models_new.site_config import SiteConfig
                config = SiteConfig.get_active()
                msg = config.maintenance_message if config else "Under maintenance."
                if request.path.startswith('/api/'):
                    return JsonResponse({'error': 'maintenance_mode', 'message': msg}, status=503)
        except Exception:
            pass
        return self.get_response(request)


class CMSRequestTimingMiddleware:
    """Log slow requests and track performance."""
    SLOW_THRESHOLD_MS = 1000

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        elapsed_ms = (time.time() - start) * 1000

        if request.path.startswith('/api/cms/'):
            if elapsed_ms > self.SLOW_THRESHOLD_MS:
                logger.warning(
                    f"[SLOW REQUEST] {request.method} {request.path} "
                    f"{elapsed_ms:.0f}ms status={response.status_code}"
                )
            try:
                try:
                    from api.cms.INTEGRATION_SYSTEM.performance_monitor import PerformanceMonitor
                except ImportError:
                    pass
                endpoint = request.path.replace('/api/cms/', '').split('/')[0]
                PerformanceMonitor.record(endpoint, elapsed_ms,
                                          success=response.status_code < 400)
            except Exception:
                pass

        response['X-Response-Time-Ms'] = f"{elapsed_ms:.0f}"
        return response


class CMSSiteConfigMiddleware:
    """Inject site config into request for templates and context processors."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            domain = request.get_host().split(':')[0]
            cache_key = f"site_config_mw_{domain}"
            config = cache.get(cache_key)
            if config is None:
                from api.cms.services_new.WithdrawalService import SiteConfigService
                config = SiteConfigService.get_config(domain)
                cache.set(cache_key, config, 300)
            request.cms_site_config = config
        except Exception:
            request.cms_site_config = {}
        return self.get_response(request)


class CMSSecurityHeadersMiddleware:
    """Add security headers to all CMS API responses."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/cms/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-CMS-Version'] = '2.0.0'
            response['Cache-Control'] = 'no-store' if 'private' in request.path else 'public, max-age=60'
        return response


class SurveyRateLimitMiddleware:
    """Rate limiting middleware for survey completion attempts."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to survey endpoints
        if not request.path.startswith('/api/cms/v3/surveys'):
            return self.get_response(request)
        
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        from django.core.cache import cache
        cache_key = f"survey_rate_limit:{request.user.id}"
        current_count = cache.get(cache_key, 0)
        
        # Check rate limit (10 surveys per hour)
        if current_count >= 10:
            from django.http import JsonResponse
            return JsonResponse({'error': 'rate_limit_exceeded'}, status=429)
        
        # Increment counter
        cache.set(cache_key, current_count + 1, 3600)
        
        response = self.get_response(request)
        return response


class UserProfileMiddleware:
    """Middleware to ensure user profile completeness for certain actions."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to survey and reward endpoints
        protected_paths = ['/api/cms/v3/surveys', '/api/cms/v3/rewards']
        
        if not any(request.path.startswith(path) for path in protected_paths):
            return self.get_response(request)
        
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        try:
            from api.cms.models_new.user_profile import UserProfile
            profile = UserProfile.objects.get(user=request.user)
            
            if profile.profile_completeness < 50:
                from django.http import JsonResponse
                return JsonResponse({'error': 'profile_incomplete'}, status=400)
        except UserProfile.DoesNotExist:
            from django.http import JsonResponse
            return JsonResponse({'error': 'profile_not_found'}, status=404)
        
        return self.get_response(request)


class TaskSecurityMiddleware:
    """Security middleware for task management endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to task management endpoints
        if not request.path.startswith('/api/cms/v3/tasks'):
            return self.get_response(request)
        
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'authentication_required'}, status=401)
        
        # Check staff permissions for task endpoints
        if not (request.user.is_staff or request.user.is_superuser):
            from django.http import JsonResponse
            return JsonResponse({'error': 'permission_denied'}, status=403)
        
        return self.get_response(request)


class RewardSecurityMiddleware:
    """Security middleware for reward management endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to reward endpoints
        if not request.path.startswith('/api/cms/v3/rewards'):
            return self.get_response(request)
        
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'authentication_required'}, status=401)
        
        # Add security headers for reward endpoints
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        return response


class AnalyticsTrackingMiddleware:
    """Middleware to track analytics for survey and reward interactions."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only track API endpoints
        if not request.path.startswith('/api/cms/'):
            return response
        
        # Track user activity if authenticated
        if request.user.is_authenticated:
            try:
                from django.core.cache import cache
                from datetime import datetime
                
                # Update last activity
                cache_key = f"user_activity:{request.user.id}"
                cache.set(cache_key, datetime.now(), 86400)  # 24 hours
                
                # Track endpoint usage
                usage_key = f"endpoint_usage:{request.user.id}:{request.path}"
                current_usage = cache.get(usage_key, 0)
                cache.set(usage_key, current_usage + 1, 86400)
                
            except Exception:
                pass  # Don't break requests if tracking fails
        
        return response


class WebSocketAuthMiddleware:
    """Middleware to handle WebSocket authentication for real-time features."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to WebSocket upgrade requests
        if 'upgrade' not in request.headers.get('connection', '').lower():
            return self.get_response(request)
        
        if not request.user.is_authenticated:
            from django.http import HttpResponse
            return HttpResponse('Unauthorized', status=401)
        
        return self.get_response(request)
