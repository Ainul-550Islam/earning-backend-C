"""
tasks/middleware/security.py
Security Middleware for comprehensive request validation and protection
"""
import logging
import time
import json
import hashlib
from typing import Dict, Any, Optional
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    """
    Comprehensive security middleware for:
    - Request validation
    - Rate limiting
    - Input sanitization
    - Security headers
    - Audit logging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = {
            'default': {'requests': 1000, 'window': 3600},  # 1000 requests/hour
            'api': {'requests': 500, 'window': 3600},      # 500 requests/hour
            'auth': {'requests': 10, 'window': 300},        # 10 requests/5min
            'upload': {'requests': 5, 'window': 60},          # 5 uploads/minute
        }
    
    def __call__(self, request):
        # Security: Process request
        response = self.process_request(request)
        
        # Security: Process response
        if response:
            response = self.process_response(request, response)
        
        return response
    
    def process_request(self, request):
        """Process incoming request with security checks."""
        try:
            # Security: Add security context
            request.security_context = self._build_security_context(request)
            
            # Security: Rate limiting
            if self._is_rate_limited(request):
                return self._rate_limit_response(request)
            
            # Security: Input validation
            if not self._validate_request(request):
                return self._invalid_request_response(request)
            
            # Security: Add security headers
            self._add_security_headers(request)
            
            # Security: Log request for audit
            self._log_request(request)
            
            return None
            
        except Exception as e:
            logger.error(f"[SecurityMiddleware] Error processing request: {e}")
            return self._error_response("Security check failed")
    
    def process_response(self, request, response):
        """Process outgoing response with security headers."""
        try:
            # Security: Add response headers
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response['Content-Security-Policy'] = "default-src 'self'"
            
            # Security: Remove sensitive headers
            if hasattr(response, 'headers'):
                sensitive_headers = ['Server', 'X-Powered-By', 'X-AspNet-Version']
                for header in sensitive_headers:
                    response.headers.pop(header, None)
            
            # Security: Log response
            self._log_response(request, response)
            
            return response
            
        except Exception as e:
            logger.error(f"[SecurityMiddleware] Error processing response: {e}")
            return response
    
    def _build_security_context(self, request) -> Dict[str, Any]:
        """Build security context for request."""
        return {
            'client_ip': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'request_id': self._generate_request_id(),
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'content_type': request.content_type,
            'content_length': len(request.body) if hasattr(request, 'body') else 0,
            'is_authenticated': request.user.is_authenticated if hasattr(request, 'user') else False,
            'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
            'tenant_id': getattr(request, 'tenant_id', None),
        }
    
    def _is_rate_limited(self, request) -> bool:
        """Check if request is rate limited."""
        try:
            client_ip = self._get_client_ip(request)
            path = request.path
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
            
            # Determine rate limit key
            if path.startswith('/api/'):
                rate_key = f"rate_limit_api_{client_ip}"
            elif path.startswith('/auth/'):
                rate_key = f"rate_limit_auth_{client_ip}_{user_id or 'anon'}"
            else:
                rate_key = f"rate_limit_default_{client_ip}"
            
            # Get current count
            current_count = cache.get(rate_key, 0)
            
            # Determine rate limit
            if path.startswith('/api/'):
                limit_config = self.rate_limits['api']
            elif path.startswith('/auth/'):
                limit_config = self.rate_limits['auth']
            else:
                limit_config = self.rate_limits['default']
            
            # Check if exceeded
            if current_count >= limit_config['requests']:
                return True
            
            # Increment count
            cache.set(rate_key, current_count + 1, timeout=limit_config['window'])
            return False
            
        except Exception:
            return False
    
    def _validate_request(self, request) -> bool:
        """Validate request for security issues."""
        try:
            # Security: Check request size
            if hasattr(request, 'body') and len(request.body) > 10 * 1024 * 1024:  # 10MB
                logger.warning(f"[SecurityMiddleware] Request too large: {len(request.body)} bytes")
                return False
            
            # Security: Check content type for POST/PUT
            if request.method in ['POST', 'PUT', 'PATCH']:
                allowed_types = [
                    'application/json',
                    'application/x-www-form-urlencoded',
                    'multipart/form-data'
                ]
                if request.content_type and request.content_type not in allowed_types:
                    logger.warning(f"[SecurityMiddleware] Invalid content type: {request.content_type}")
                    return False
            
            # Security: Check for suspicious patterns
            if hasattr(request, 'body') and request.body:
                body_str = request.body.decode('utf-8', errors='ignore').lower()
                suspicious_patterns = [
                    '<script', 'javascript:', 'vbscript:', 'onload=', 'onerror=',
                    'eval(', 'expression(', 'document.cookie', 'window.location',
                    '../', '..\\', 'cmd.exe', 'powershell', 'bash -'
                ]
                
                for pattern in suspicious_patterns:
                    if pattern in body_str:
                        logger.warning(f"[SecurityMiddleware] Suspicious pattern detected: {pattern}")
                        return False
            
            # Security: Validate JSON structure
            if request.content_type == 'application/json' and hasattr(request, 'body'):
                try:
                    json.loads(request.body)
                except json.JSONDecodeError:
                    logger.warning("[SecurityMiddleware] Invalid JSON in request")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"[SecurityMiddleware] Request validation error: {e}")
            return False
    
    def _add_security_headers(self, request):
        """Add security headers to request."""
        # Security headers are added in process_response
        pass
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _log_request(self, request):
        """Log request for security audit."""
        try:
            if hasattr(request, 'security_context'):
                log_entry = {
                    'type': 'request',
                    'request_id': request.security_context['request_id'],
                    'ip': request.security_context['client_ip'],
                    'method': request.security_context['method'],
                    'path': request.security_context['path'],
                    'user_id': request.security_context['user_id'],
                    'tenant_id': request.security_context['tenant_id'],
                    'user_agent': request.security_context['user_agent'],
                    'content_length': request.security_context['content_length'],
                    'timestamp': request.security_context['timestamp'],
                }
                
                # Store in security audit log
                cache.set(
                    f"security_audit_{request.security_context['request_id']}",
                    log_entry,
                    timeout=86400  # 24 hours
                )
        except Exception as e:
            logger.error(f"[SecurityMiddleware] Error logging request: {e}")
    
    def _log_response(self, request, response):
        """Log response for security audit."""
        try:
            if hasattr(request, 'security_context'):
                log_entry = {
                    'type': 'response',
                    'request_id': request.security_context['request_id'],
                    'status_code': response.status_code,
                    'content_length': len(response.content) if hasattr(response, 'content') else 0,
                    'timestamp': timezone.now().isoformat(),
                }
                
                # Update security audit log
                cache.set(
                    f"security_audit_response_{request.security_context['request_id']}",
                    log_entry,
                    timeout=86400  # 24 hours
                )
        except Exception as e:
            logger.error(f"[SecurityMiddleware] Error logging response: {e}")
    
    def _rate_limit_response(self, request) -> JsonResponse:
        """Return rate limit response."""
        return JsonResponse({
            'error': 'Rate limit exceeded',
            'error_code': 'RATE_LIMIT_EXCEEDED',
            'retry_after': 60,  # seconds
            'details': {
                'message': 'Too many requests. Please try again later.',
                'limit': '1000 requests per hour',
                'client_ip': self._get_client_ip(request)
            }
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    def _invalid_request_response(self, request) -> JsonResponse:
        """Return invalid request response."""
        return JsonResponse({
            'error': 'Invalid request',
            'error_code': 'INVALID_REQUEST',
            'details': {
                'message': 'Request validation failed',
                'client_ip': self._get_client_ip(request)
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def _error_response(self, message: str) -> JsonResponse:
        """Return general error response."""
        return JsonResponse({
            'error': 'Security error',
            'error_code': 'SECURITY_ERROR',
            'details': {'message': message}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantIsolationMiddleware:
    """
    Middleware to ensure tenant data isolation
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            # Security: Extract tenant from request
            tenant_id = self._extract_tenant_id(request)
            
            if tenant_id:
                # Security: Validate tenant exists and is active
                if not self._validate_tenant(tenant_id):
                    return JsonResponse({
                        'error': 'Invalid tenant',
                        'error_code': 'INVALID_TENANT',
                        'details': {'tenant_id': tenant_id}
                    }, status=403)
                
                # Security: Add tenant to request context
                request.tenant_id = tenant_id
                
                # Security: Add tenant filtering to queryset
                self._add_tenant_filtering(request, tenant_id)
            
            return None
            
        except Exception as e:
            logger.error(f"[TenantIsolationMiddleware] Error: {e}")
            return JsonResponse({
                'error': 'Tenant validation failed',
                'error_code': 'TENANT_ERROR'
            }, status=500)
    
    def _extract_tenant_id(self, request) -> Optional[str]:
        """Extract tenant ID from request."""
        # Try header first
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            return tenant_id.strip()
        
        # Try subdomain
        host = request.get_host()
        if host and '.' in host:
            parts = host.split('.')
            if len(parts) >= 2:
                possible_tenant = parts[0]
                if possible_tenant != 'www' and possible_tenant != 'api':
                    return possible_tenant
        
        # Try URL parameter
        if hasattr(request, 'GET'):
            tenant_id = request.GET.get('tenant_id')
            if tenant_id:
                return tenant_id.strip()
        
        return None
    
    def _validate_tenant(self, tenant_id: str) -> bool:
        """Validate tenant exists and is active."""
        try:
            from tenants.models import Tenant
            return Tenant.objects.filter(
                id=tenant_id,
                is_active=True
            ).exists()
        except Exception:
            return False
    
    def _add_tenant_filtering(self, request, tenant_id: str):
        """Add tenant filtering to request context."""
        # This will be used by views to filter querysets
        request.tenant_filter = {'tenant_id': tenant_id}
