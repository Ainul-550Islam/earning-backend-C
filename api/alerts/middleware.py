"""
Middleware for alerts app - Request context and rate limiting
"""
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import AnonymousUser
import logging
import time
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AlertContextMiddleware:
    """Middleware to add alert context to requests"""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        
    def __call__(self, request):
        # Add alert context to request
        request.alert_context = self._get_alert_context(request)
        
        # Process request
        response = self.get_response(request)
        
        # Add alert headers to response
        self._add_alert_headers(response, request.alert_context)
        
        return response
    
    def _get_alert_context(self, request) -> Dict[str, Any]:
        """Get alert context for request"""
        context = {
            'timestamp': timezone.now().isoformat(),
            'user_id': None,
            'tenant_id': None,
            'session_id': None,
            'request_id': None,
            'active_alerts': 0,
            'pending_alerts': 0,
            'critical_alerts': 0
        }
        
        try:
            # Get user information
            if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
                context['user_id'] = request.user.id
                context['tenant_id'] = getattr(request.user, 'tenant_id', None)
            
            # Get session information
            if hasattr(request, 'session') and request.session.session_key:
                context['session_id'] = request.session.session_key
            
            # Generate request ID
            request_id = getattr(request, 'request_id', None)
            if not request_id:
                import uuid
                request_id = str(uuid.uuid4())
                request.request_id = request_id
            
            context['request_id'] = request_id
            
            # Get alert statistics
            context.update(self._get_alert_statistics(request))
            
        except Exception as e:
            logger.error(f"Error getting alert context: {e}")
        
        return context
    
    def _get_alert_statistics(self, request) -> Dict[str, Any]:
        """Get alert statistics for current user/tenant"""
        try:
            from .models import AlertLog, AlertRule
            
            # Base queryset
            queryset = AlertLog.objects.all()
            
            # Filter by user if authenticated
            if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
                queryset = queryset.filter(user=request.user)
            
            # Filter by tenant if available
            tenant_id = getattr(request, 'user', {}).get('tenant_id')
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
            
            # Get statistics
            context = {
                'active_alerts': queryset.filter(is_resolved=False).count(),
                'pending_alerts': queryset.filter(is_resolved=False, severity__in=['low', 'medium']).count(),
                'critical_alerts': queryset.filter(is_resolved=False, severity__in=['high', 'critical']).count()
            }
            
            # Get recent alerts
            recent_cutoff = timezone.now() - timedelta(hours=24)
            context['recent_alerts'] = queryset.filter(triggered_at__gte=recent_cutoff).count()
            
            # Get active rules
            rules_queryset = AlertRule.objects.filter(is_active=True)
            if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
                rules_queryset = rules_queryset.filter(user=request.user)
            
            context['active_rules'] = rules_queryset.count()
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return {
                'active_alerts': 0,
                'pending_alerts': 0,
                'critical_alerts': 0,
                'recent_alerts': 0,
                'active_rules': 0
            }
    
    def _add_alert_headers(self, response: HttpResponse, context: Dict[str, Any]):
        """Add alert context headers to response"""
        try:
            response['X-Alert-Request-ID'] = context.get('request_id', '')
            response['X-Alert-Timestamp'] = context.get('timestamp', '')
            response['X-Alert-Active-Count'] = str(context.get('active_alerts', 0))
            response['X-Alert-Critical-Count'] = str(context.get('critical_alerts', 0))
            
            # Add CORS headers for alert endpoints
            if hasattr(response, 'status_code') and response.status_code == 200:
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Request-ID'
                
        except Exception as e:
            logger.error(f"Error adding alert headers: {e}")


class AlertRateLimitMiddleware:
    """Middleware for per-tenant alert rate limiting"""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.rate_limits = getattr(settings, 'ALERT_RATE_LIMITS', {
            'default': {
                'requests': 100,
                'window': 3600,  # 1 hour
                'burst': 10
            },
            'critical': {
                'requests': 50,
                'window': 3600,
                'burst': 5
            },
            'emergency': {
                'requests': 20,
                'window': 3600,
                'burst': 2
            }
        })
        
    def __call__(self, request):
        # Check if this is an alert-related request
        if not self._is_alert_request(request):
            return self.get_response(request)
        
        # Get tenant and user information
        tenant_id = self._get_tenant_id(request)
        user_id = self._get_user_id(request)
        
        # Check rate limits
        rate_limit_result = self._check_rate_limit(request, tenant_id, user_id)
        
        if not rate_limit_result['allowed']:
            # Return rate limit response
            return self._rate_limit_response(rate_limit_result)
        
        # Add rate limit headers
        response = self.get_response(request)
        self._add_rate_limit_headers(response, rate_limit_result)
        
        return response
    
    def _is_alert_request(self, request) -> bool:
        """Check if request is alert-related"""
        alert_paths = [
            '/api/alerts/',
            '/api/alert-rules/',
            '/api/notifications/',
            '/alert/',
            '/alerts/'
        ]
        
        return any(request.path.startswith(path) for path in alert_paths)
    
    def _get_tenant_id(self, request) -> Optional[str]:
        """Get tenant ID from request"""
        # Try to get from user
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            tenant_id = getattr(request.user, 'tenant_id', None)
            if tenant_id:
                return str(tenant_id)
        
        # Try to get from headers
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            return tenant_id
        
        # Try to get from session
        if hasattr(request, 'session'):
            tenant_id = request.session.get('tenant_id')
            if tenant_id:
                return tenant_id
        
        return None
    
    def _get_user_id(self, request) -> Optional[str]:
        """Get user ID from request"""
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            return str(request.user.id)
        
        return None
    
    def _check_rate_limit(self, request, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """Check rate limits for request"""
        try:
            # Determine rate limit tier
            tier = self._get_rate_limit_tier(request)
            rate_config = self.rate_limits.get(tier, self.rate_limits['default'])
            
            # Generate cache keys
            tenant_key = f"alert_rate_limit:tenant:{tenant_id}" if tenant_id else None
            user_key = f"alert_rate_limit:user:{user_id}" if user_id else None
            
            # Check tenant rate limit
            if tenant_key:
                tenant_result = self._check_cache_rate_limit(tenant_key, rate_config)
                if not tenant_result['allowed']:
                    return tenant_result
            
            # Check user rate limit
            if user_key:
                user_result = self._check_cache_rate_limit(user_key, rate_config)
                if not user_result['allowed']:
                    return user_result
            
            # Update counters
            if tenant_key:
                self._update_rate_limit_counter(tenant_key, rate_config)
            
            if user_key:
                self._update_rate_limit_counter(user_key, rate_config)
            
            return {
                'allowed': True,
                'tier': tier,
                'limit': rate_config['requests'],
                'window': rate_config['window'],
                'remaining': rate_config['requests'] - 1,
                'reset_time': timezone.now() + timedelta(seconds=rate_config['window'])
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # Allow request on error
            return {
                'allowed': True,
                'error': 'Operation failed'
            }
    
    def _get_rate_limit_tier(self, request) -> str:
        """Determine rate limit tier based on request"""
        # Check for emergency indicators
        if self._is_emergency_request(request):
            return 'emergency'
        
        # Check for critical indicators
        if self._is_critical_request(request):
            return 'critical'
        
        return 'default'
    
    def _is_emergency_request(self, request) -> bool:
        """Check if this is an emergency request"""
        emergency_indicators = [
            'emergency' in request.path.lower(),
            request.META.get('HTTP_X_EMERGENCY') == 'true',
            request.POST.get('emergency') == 'true',
            request.GET.get('emergency') == 'true'
        ]
        
        return any(emergency_indicators)
    
    def _is_critical_request(self, request) -> bool:
        """Check if this is a critical request"""
        critical_indicators = [
            'critical' in request.path.lower(),
            request.META.get('HTTP_X_PRIORITY') == 'critical',
            request.POST.get('priority') == 'critical',
            request.GET.get('priority') == 'critical',
            'severity' in request.POST and request.POST['severity'] in ['high', 'critical'],
            'severity' in request.GET and request.GET['severity'] in ['high', 'critical']
        ]
        
        return any(critical_indicators)
    
    def _check_cache_rate_limit(self, key: str, rate_config: Dict[str, Any]) -> Dict[str, Any]:
        """Check rate limit from cache"""
        try:
            current_time = int(time.time())
            window_start = current_time - rate_config['window']
            
            # Get current counter
            counter_data = cache.get(key, {
                'count': 0,
                'reset_time': current_time + rate_config['window']
            })
            
            # Clean old entries (simplified - in production, use sliding window)
            if counter_data['reset_time'] <= current_time:
                counter_data = {
                    'count': 0,
                    'reset_time': current_time + rate_config['window']
                }
            
            # Check limit
            if counter_data['count'] >= rate_config['requests']:
                return {
                    'allowed': False,
                    'limit': rate_config['requests'],
                    'window': rate_config['window'],
                    'current': counter_data['count'],
                    'reset_time': timezone.datetime.fromtimestamp(counter_data['reset_time']),
                    'retry_after': counter_data['reset_time'] - current_time
                }
            
            return {
                'allowed': True,
                'limit': rate_config['requests'],
                'window': rate_config['window'],
                'current': counter_data['count'],
                'remaining': rate_config['requests'] - counter_data['count'] - 1,
                'reset_time': timezone.datetime.fromtimestamp(counter_data['reset_time'])
            }
            
        except Exception as e:
            logger.error(f"Error checking cache rate limit: {e}")
            return {'allowed': True, 'error': 'Operation failed'}
    
    def _update_rate_limit_counter(self, key: str, rate_config: Dict[str, Any]):
        """Update rate limit counter in cache"""
        try:
            current_time = int(time.time())
            
            # Get current counter
            counter_data = cache.get(key, {
                'count': 0,
                'reset_time': current_time + rate_config['window']
            })
            
            # Reset if window expired
            if counter_data['reset_time'] <= current_time:
                counter_data = {
                    'count': 1,
                    'reset_time': current_time + rate_config['window']
                }
            else:
                counter_data['count'] += 1
            
            # Update cache
            cache.set(key, counter_data, timeout=rate_config['window'])
            
        except Exception as e:
            logger.error(f"Error updating rate limit counter: {e}")
    
    def _rate_limit_response(self, rate_limit_result: Dict[str, Any]) -> JsonResponse:
        """Return rate limit response"""
        response_data = {
            'error': 'Rate limit exceeded',
            'message': 'Too many alert requests',
            'limit': rate_limit_result.get('limit'),
            'window': rate_limit_result.get('window'),
            'retry_after': rate_limit_result.get('retry_after'),
            'reset_time': rate_limit_result.get('reset_time'),
            'tier': rate_limit_result.get('tier')
        }
        
        response = JsonResponse(response_data, status=429)
        self._add_rate_limit_headers(response, rate_limit_result)
        
        return response
    
    def _add_rate_limit_headers(self, response: HttpResponse, rate_limit_result: Dict[str, Any]):
        """Add rate limit headers to response"""
        try:
            response['X-RateLimit-Limit'] = str(rate_limit_result.get('limit', ''))
            response['X-RateLimit-Remaining'] = str(rate_limit_result.get('remaining', ''))
            response['X-RateLimit-Reset'] = str(int(rate_limit_result.get('reset_time', timezone.now()).timestamp()))
            
            if 'retry_after' in rate_limit_result:
                response['Retry-After'] = str(rate_limit_result['retry_after'])
            
            response['X-RateLimit-Tier'] = rate_limit_result.get('tier', 'default')
            
        except Exception as e:
            logger.error(f"Error adding rate limit headers: {e}")


class AlertSecurityMiddleware:
    """Middleware for alert security headers and validation"""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        
    def __call__(self, request):
        # Add security headers
        response = self.get_response(request)
        self._add_security_headers(response, request)
        
        return response
    
    def _add_security_headers(self, response: HttpResponse, request):
        """Add security headers for alert responses"""
        try:
            # Content Security Policy
            if 'Content-Security-Policy' not in response:
                csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
                response['Content-Security-Policy'] = csp
            
            # X-Content-Type-Options
            response['X-Content-Type-Options'] = 'nosniff'
            
            # X-Frame-Options
            response['X-Frame-Options'] = 'DENY'
            
            # X-XSS-Protection
            response['X-XSS-Protection'] = '1; mode=block'
            
            # Strict-Transport-Security (if HTTPS)
            if request.is_secure():
                hsts = 'max-age=31536000; includeSubDomains; preload'
                response['Strict-Transport-Security'] = hsts
            
            # Referrer Policy
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Permissions Policy
            permissions_policy = 'geolocation=(), microphone=(), camera=()'
            response['Permissions-Policy'] = permissions_policy
            
        except Exception as e:
            logger.error(f"Error adding security headers: {e}")


class AlertLoggingMiddleware:
    """Middleware for alert request logging"""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.log_requests = getattr(settings, 'ALERT_LOG_REQUESTS', True)
        self.log_responses = getattr(settings, 'ALERT_LOG_RESPONSES', False)
        
    def __call__(self, request):
        if not self.log_requests:
            return self.get_response(request)
        
        # Check if this is an alert-related request
        if not self._is_alert_request(request):
            return self.get_response(request)
        
        # Log request
        start_time = time.time()
        request_data = self._extract_request_data(request)
        
        # Process request
        response = self.get_response(request)
        
        # Log response
        if self.log_responses:
            response_data = self._extract_response_data(response)
            response_time = time.time() - start_time
            
            self._log_request_response(request_data, response_data, response_time)
        
        return response
    
    def _is_alert_request(self, request) -> bool:
        """Check if request is alert-related"""
        alert_paths = [
            '/api/alerts/',
            '/api/alert-rules/',
            '/api/notifications/',
            '/alert/',
            '/alerts/'
        ]
        
        return any(request.path.startswith(path) for path in alert_paths)
    
    def _extract_request_data(self, request) -> Dict[str, Any]:
        """Extract relevant request data for logging"""
        try:
            data = {
                'timestamp': timezone.now().isoformat(),
                'method': request.method,
                'path': request.path,
                'user_id': None,
                'tenant_id': None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'content_type': request.content_type,
                'content_length': len(request.body) if hasattr(request, 'body') else 0
            }
            
            # Add user information
            if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
                data['user_id'] = request.user.id
                data['tenant_id'] = getattr(request.user, 'tenant_id', None)
            
            # Add query parameters
            if request.GET:
                data['query_params'] = dict(request.GET)
            
            # Add POST data (sanitized)
            if request.POST:
                # Only log non-sensitive fields
                safe_fields = ['alert_type', 'severity', 'priority', 'message']
                data['post_data'] = {
                    k: v for k, v in request.POST.items() 
                    if k in safe_fields
                }
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting request data: {e}")
            return {'error': 'Operation failed'}
    
    def _extract_response_data(self, response) -> Dict[str, Any]:
        """Extract relevant response data for logging"""
        try:
            data = {
                'status_code': response.status_code,
                'content_type': response.get('Content-Type', ''),
                'content_length': len(response.content) if hasattr(response, 'content') else 0
            }
            
            # Add response headers
            if hasattr(response, 'items'):
                data['headers'] = dict(response.items())
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting response data: {e}")
            return {'error': 'Operation failed'}
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _log_request_response(self, request_data: Dict[str, Any], 
                           response_data: Dict[str, Any], response_time: float):
        """Log request and response data"""
        try:
            log_entry = {
                'request': request_data,
                'response': response_data,
                'response_time_ms': round(response_time * 1000, 2)
            }
            
            # Log to file or external service
            logger.info(f"Alert request: {json.dumps(log_entry)}")
            
        except Exception as e:
            logger.error(f"Error logging request/response: {e}")


# Middleware factory functions
def AlertContextMiddlewareFactory(get_response):
    """Factory for AlertContextMiddleware"""
    return AlertContextMiddleware(get_response)


def AlertRateLimitMiddlewareFactory(get_response):
    """Factory for AlertRateLimitMiddleware"""
    return AlertRateLimitMiddleware(get_response)


def AlertSecurityMiddlewareFactory(get_response):
    """Factory for AlertSecurityMiddleware"""
    return AlertSecurityMiddleware(get_response)


def AlertLoggingMiddlewareFactory(get_response):
    """Factory for AlertLoggingMiddleware"""
    return AlertLoggingMiddleware(get_response)
