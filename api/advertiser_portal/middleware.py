"""
Middleware for Advertiser Portal

This module contains Django middleware classes for handling
cross-cutting concerns like authentication, logging, rate limiting,
and request processing.
"""

import time
import uuid
import logging
from typing import Callable, Optional, Dict, Any
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin

from .exceptions import *
from .utils import *
from .constants import *
from .enums import *


User = get_user_model()
logger = logging.getLogger(__name__)


class RequestIDMiddleware(MiddlewareMixin):
    """Middleware to add unique request ID to each request."""
    
    def process_request(self, request: HttpRequest) -> None:
        """Add request ID to request object."""
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        
        # Add to response headers
        request.META['HTTP_X_REQUEST_ID'] = request_id
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add request ID to response headers."""
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        return response


class AuthenticationMiddleware(MiddlewareMixin):
    """Middleware for API authentication."""
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Authenticate API requests."""
        # Skip authentication for non-API paths
        if not request.path.startswith('/api/'):
            return None
        
        # Try token authentication
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            return self._authenticate_token(request, token)
        
        # Try API key authentication
        api_key = request.META.get('HTTP_X_API_KEY')
        if api_key:
            return self._authenticate_api_key(request, api_key)
        
        # For protected endpoints, require authentication
        if self._is_protected_endpoint(request.path):
            return JsonResponse(
                ExceptionHandler.get_error_response(
                    AuthenticationError("Authentication required")
                ),
                status=401
            )
        
        return None
    
    def _authenticate_token(self, request: HttpRequest, token: str) -> Optional[HttpResponse]:
        """Authenticate using JWT token."""
        try:
            # JWT token validation would go here
            # For now, placeholder implementation
            payload = ValidationUtils.validate_jwt_token(token)
            
            if payload:
                user_id = payload.get('user_id')
                user = User.objects.get(id=user_id)
                request.user = user
                request.auth_type = 'token'
                return None
            
        except Exception as e:
            logger.warning(f"Token authentication failed: {e}")
        
        return JsonResponse(
            ExceptionHandler.get_error_response(
                AuthenticationError("Invalid authentication token")
            ),
            status=401
        )
    
    def _authenticate_api_key(self, request: HttpRequest, api_key: str) -> Optional[HttpResponse]:
        """Authenticate using API key."""
        try:
            from .models import Advertiser
            advertiser = Advertiser.objects.get(api_key=api_key, is_deleted=False)
            
            if advertiser.is_api_key_valid():
                request.advertiser = advertiser
                request.user = advertiser.user
                request.auth_type = 'api_key'
                return None
            
        except Advertiser.DoesNotExist:
            pass
        except Exception as e:
            logger.warning(f"API key authentication failed: {e}")
        
        return JsonResponse(
            ExceptionHandler.get_error_response(
                AuthenticationError("Invalid API key")
            ),
            status=401
        )
    
    def _is_protected_endpoint(self, path: str) -> bool:
        """Check if endpoint requires authentication."""
        protected_prefixes = [
            '/api/advertiser_portal/advertisers/',
            '/api/advertiser_portal/campaigns/',
            '/api/advertiser_portal/creatives/',
            '/api/advertiser_portal/targeting/',
            '/api/advertiser_portal/analytics/',
            '/api/advertiser_portal/billing/',
        ]
        
        return any(path.startswith(prefix) for prefix in protected_prefixes)


class AuthorizationMiddleware(MiddlewareMixin):
    """Middleware for API authorization."""
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check user permissions."""
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        # Check permissions for protected endpoints
        if self._requires_permission(request.path):
            required_permission = self._get_required_permission(request)
            
            if not request.user.has_perm(required_permission):
                return JsonResponse(
                    ExceptionHandler.get_error_response(
                        AuthorizationError(
                            "Insufficient permissions",
                            required_permission=required_permission
                        )
                    ),
                    status=403
                )
        
        return None
    
    def _requires_permission(self, path: str) -> bool:
        """Check if path requires specific permissions."""
        # Define permission requirements for different endpoints
        permission_map = {
            '/api/advertiser_portal/advertisers/': 'advertiser_portal.view_advertiser',
            '/api/advertiser_portal/campaigns/': 'advertiser_portal.view_campaign',
            '/api/advertiser_portal/creatives/': 'advertiser_portal.view_creative',
            '/api/advertiser_portal/targeting/': 'advertiser_portal.view_targeting',
            '/api/advertiser_portal/analytics/': 'advertiser_portal.view_analytics',
            '/api/advertiser_portal/billing/': 'advertiser_portal.view_billing',
        }
        
        for prefix, permission in permission_map.items():
            if path.startswith(prefix):
                return True
        
        return False
    
    def _get_required_permission(self, request: HttpRequest) -> str:
        """Get required permission for request."""
        method = request.method.upper()
        path = request.path
        
        # Map HTTP methods to permission types
        method_permission_map = {
            'GET': 'view',
            'POST': 'add',
            'PUT': 'change',
            'PATCH': 'change',
            'DELETE': 'delete',
        }
        
        permission_type = method_permission_map.get(method, 'view')
        
        # Determine resource type from path
        if '/advertisers/' in path:
            return f'advertiser_portal.{permission_type}_advertiser'
        elif '/campaigns/' in path:
            return f'advertiser_portal.{permission_type}_campaign'
        elif '/creatives/' in path:
            return f'advertiser_portal.{permission_type}_creative'
        elif '/targeting/' in path:
            return f'advertiser_portal.{permission_type}_targeting'
        elif '/analytics/' in path:
            return f'advertiser_portal.{permission_type}_analytics'
        elif '/billing/' in path:
            return f'advertiser_portal.{permission_type}_billing'
        
        return 'advertiser_portal.view'


class RateLimitMiddleware(MiddlewareMixin):
    """Middleware for rate limiting API requests."""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check rate limits."""
        if not request.path.startswith('/api/'):
            return None
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        rate_limit_info = self._check_rate_limit(client_id, request.path)
        
        if not rate_limit_info['allowed']:
            return JsonResponse(
                ExceptionHandler.get_error_response(
                    RateLimitError(
                        f"Rate limit exceeded: {rate_limit_info['limit']} requests per {rate_limit_info['window']} seconds",
                        limit=rate_limit_info['limit'],
                        reset_time=rate_limit_info['reset_time']
                    )
                ),
                status=429
            )
        
        # Add rate limit headers
        request.rate_limit_info = rate_limit_info
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add rate limit headers to response."""
        if hasattr(request, 'rate_limit_info'):
            info = request.rate_limit_info
            response['X-RateLimit-Limit'] = str(info['limit'])
            response['X-RateLimit-Remaining'] = str(info['remaining'])
            response['X-RateLimit-Reset'] = str(info['reset_time'])
        
        return response
    
    def _get_client_id(self, request: HttpRequest) -> str:
        """Get client identifier for rate limiting."""
        # Use user ID if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Use advertiser ID if available
        if hasattr(request, 'advertiser'):
            return f"advertiser:{request.advertiser.id}"
        
        # Use IP address as fallback
        ip_address = self._get_client_ip(request)
        return f"ip:{ip_address}"
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _check_rate_limit(self, client_id: str, path: str) -> Dict[str, Any]:
        """Check if client has exceeded rate limit."""
        # Determine rate limit based on path and user type
        limit, window = self._get_rate_limit(client_id, path)
        
        # Create cache key
        cache_key = f"rate_limit:{client_id}:{hash(path)}"
        
        # Get current count
        current_count = cache.get(cache_key, 0)
        
        # Check if limit exceeded
        if current_count >= limit:
            # Calculate reset time
            reset_time = int(time.time()) + window
            return {
                'allowed': False,
                'limit': limit,
                'window': window,
                'remaining': 0,
                'reset_time': reset_time
            }
        
        # Increment counter
        new_count = cache.incr(cache_key)
        if new_count == 1:
            # Set expiration for new counter
            cache.expire(cache_key, window)
        
        return {
            'allowed': True,
            'limit': limit,
            'window': window,
            'remaining': max(0, limit - new_count),
            'reset_time': int(time.time()) + window
        }
    
    def _get_rate_limit(self, client_id: str, path: str) -> tuple:
        """Get rate limit (requests, window_seconds) for client."""
        # Default limits
        default_limit = APIConstants.DEFAULT_RATE_LIMIT
        default_window = 3600  # 1 hour
        
        # Premium users get higher limits
        if client_id.startswith('user:'):
            try:
                user_id = int(client_id.split(':')[1])
                user = User.objects.get(id=user_id)
                
                if hasattr(user, 'advertiser') and user.advertiser.account_type == 'enterprise':
                    return APIConstants.PREMIUM_RATE_LIMIT, default_window
            except (ValueError, User.DoesNotExist, AttributeError):
                pass
        
        # Different limits for different endpoints
        if '/analytics/' in path:
            return default_limit * 2, default_window  # Higher limit for analytics
        elif '/billing/' in path:
            return default_limit // 2, default_window  # Lower limit for billing
        
        return default_limit, default_window


class LoggingMiddleware(MiddlewareMixin):
    """Middleware for request/response logging."""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.logger = logging.getLogger('api.requests')
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest) -> None:
        """Log incoming request."""
        request.start_time = time.time()
        
        # Log request details
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'request_id': getattr(request, 'request_id', 'unknown'),
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.GET),
            'client_ip': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }
        
        # Add user info if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            log_data['user_id'] = request.user.id
            log_data['username'] = request.user.username
        
        # Add advertiser info if available
        if hasattr(request, 'advertiser'):
            log_data['advertiser_id'] = request.advertiser.id
            log_data['company_name'] = request.advertiser.company_name
        
        self.logger.info(f"Request: {log_data}")
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log response details."""
        # Calculate processing time
        if hasattr(request, 'start_time'):
            processing_time = time.time() - request.start_time
            response['X-Processing-Time'] = f"{processing_time:.3f}s"
        
        # Log response details
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'request_id': getattr(request, 'request_id', 'unknown'),
            'status_code': response.status_code,
            'content_type': response.get('Content-Type', ''),
        }
        
        if hasattr(request, 'start_time'):
            log_data['processing_time'] = processing_time
        
        # Log error responses with more detail
        if response.status_code >= 400:
            try:
                if hasattr(response, 'content'):
                    import json
                    content = json.loads(response.content.decode())
                    log_data['error'] = content.get('error', 'Unknown error')
                    log_data['error_code'] = content.get('error_code', None)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        log_level = 'error' if response.status_code >= 500 else 'warning' if response.status_code >= 400 else 'info'
        getattr(self.logger, log_level)(f"Response: {log_data}")
        
        return response
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', 'unknown')


class SecurityMiddleware(MiddlewareMixin):
    """Middleware for security headers and protections."""
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add security headers to response."""
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        
        # Remove server information
        response.pop('Server', None)
        
        return response


class CacheMiddleware(MiddlewareMixin):
    """Middleware for response caching."""
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add caching headers to response."""
        # Only cache GET requests
        if request.method != 'GET':
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response
        
        # Don't cache API responses with sensitive data
        if request.path.startswith('/api/advertiser_portal/billing/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response
        
        # Set cache headers for analytics endpoints
        if request.path.startswith('/api/advertiser_portal/analytics/'):
            # Cache analytics data for 5 minutes
            response['Cache-Control'] = 'public, max-age=300'
            response['ETag'] = self._generate_etag(response)
        
        return response
    
    def _generate_etag(self, response: HttpResponse) -> str:
        """Generate ETag for response."""
        import hashlib
        
        content = response.content
        etag = hashlib.md5(content).hexdigest()
        return f'"{etag}"'


class CORSMiddleware(MiddlewareMixin):
    """Middleware for Cross-Origin Resource Sharing (CORS)."""
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add CORS headers to response."""
        # Get allowed origins from settings
        allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        origin = request.META.get('HTTP_ORIGIN')
        
        # Add CORS headers for allowed origins
        if origin in allowed_origins or '*' in allowed_origins:
            response['Access-Control-Allow-Origin'] = origin if origin != '*' else '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = (
                'Content-Type, Authorization, X-API-Key, X-Request-ID'
            )
            response['Access-Control-Max-Age'] = '86400'  # 24 hours
            response['Access-Control-Allow-Credentials'] = 'true'
        
        # Handle preflight requests
        if request.method == 'OPTIONS':
            response.status_code = 200
        
        return response


class FraudDetectionMiddleware(MiddlewareMixin):
    """Middleware for basic fraud detection."""
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Detect suspicious activity."""
        if not request.path.startswith('/api/'):
            return None
        
        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check for suspicious patterns
        risk_score = self._calculate_risk_score(request, client_ip, user_agent)
        
        if risk_score >= FraudConstants.HIGH_RISK_SCORE:
            # Log suspicious activity
            logger.warning(
                f"High risk activity detected from {client_ip}, "
                f"risk score: {risk_score}, path: {request.path}"
            )
            
            # Block if risk is very high
            if risk_score >= 90:
                return JsonResponse(
                    ExceptionHandler.get_error_response(
                        SuspiciousActivityError(
                            "Request blocked due to suspicious activity",
                            activity_type="high_risk_request",
                            risk_score=risk_score
                        )
                    ),
                    status=403
                )
        
        return None
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _calculate_risk_score(self, request: HttpRequest, client_ip: str, user_agent: str) -> int:
        """Calculate risk score for request."""
        risk_score = 0
        
        # Check for suspicious user agent
        suspicious_agents = ['bot', 'crawler', 'spider', 'scraper']
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            risk_score += 30
        
        # Check request frequency
        cache_key = f"request_count:{client_ip}:{int(time.time() // 60)}"  # Per minute
        request_count = cache.incr(cache_key)
        if request_count == 1:
            cache.expire(cache_key, 60)
        
        if request_count > 100:  # More than 100 requests per minute
            risk_score += 40
        
        # Check for known malicious IPs
        if self._is_malicious_ip(client_ip):
            risk_score += 50
        
        # Check for suspicious headers
        suspicious_headers = ['X-Forwarded-For', 'X-Real-IP']
        for header in suspicious_headers:
            if header in request.META and len(request.META[header].split(',')) > 3:
                risk_score += 20
        
        return min(risk_score, 100)
    
    def _is_malicious_ip(self, ip: str) -> bool:
        """Check if IP is known to be malicious."""
        # This would typically integrate with a threat intelligence service
        # For now, placeholder implementation
        malicious_ips = getattr(settings, 'MALICIOUS_IPS', [])
        return ip in malicious_ips


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """Middleware for performance monitoring."""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.logger = logging.getLogger('api.performance')
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest) -> None:
        """Record request start time."""
        request.start_time = time.time()
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log performance metrics."""
        if hasattr(request, 'start_time'):
            processing_time = time.time() - request.start_time
            
            # Log slow requests
            if processing_time > 2.0:  # More than 2 seconds
                self.logger.warning(
                    f"Slow request detected: {request.method} {request.path} "
                    f"took {processing_time:.3f}s"
                )
            
            # Record performance metrics
            self._record_metrics(request, response, processing_time)
        
        return response
    
    def _record_metrics(self, request: HttpRequest, response: HttpResponse, 
                       processing_time: float) -> None:
        """Record performance metrics."""
        # This would typically send metrics to a monitoring service
        # For now, just log them
        metrics = {
            'endpoint': f"{request.method} {request.path}",
            'status_code': response.status_code,
            'processing_time': processing_time,
            'timestamp': timezone.now().isoformat(),
        }
        
        # Add user info if available
        if hasattr(request, 'user') and request.user.is_authenticated:
            metrics['user_id'] = request.user.id
        
        self.logger.info(f"Performance metrics: {metrics}")


class ContextMiddleware(MiddlewareMixin):
    """Middleware for setting up request context."""
    
    def process_request(self, request: HttpRequest) -> None:
        """Set up request context."""
        from .dependencies import context_manager
        
        # Create context for this request
        request_id = getattr(request, 'request_id', str(uuid.uuid4()))
        user = getattr(request, 'user', None)
        
        context = context_manager.create_context(request_id, user)
        request.context = context
        
        # Store request in context for later use
        context.set('request', request)
        context.set('path', request.path)
        context.set('method', request.method)
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Clean up request context."""
        if hasattr(request, 'context'):
            from .dependencies import context_manager
            context_manager.remove_context(request.context.request_id)
        
        return response
