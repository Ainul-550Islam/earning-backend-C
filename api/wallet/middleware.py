# api/wallet/middleware.py
import logging
from django.utils.deprecation import MiddlewareMixin
import ipaddress
import traceback
from urllib import response
from django.http import JsonResponse, HttpResponse
from django.db import DatabaseError, OperationalError
from django.conf import settings
import re
from django.utils import timezone
import socket
from .utils import safe_ip, safe_get, CircuitBreaker

logger = logging.getLogger(__name__)


class SafeIPMiddleware(MiddlewareMixin):
    """Safe IP Middleware"""
    
    def process_request(self, request):
        try:
            from .validators import extract_client_ip
            client_ip = extract_client_ip(request)
            request.safe_ip = client_ip
            request.META['REMOTE_ADDR'] = client_ip
        except Exception as e:
            logger.error(f"IP middleware error: {e}")
            request.safe_ip = '127.0.0.1'
            request.META['REMOTE_ADDR'] = '127.0.0.1'
        return None


class SecurityLogMiddleware(MiddlewareMixin):
    """Security logging"""
    
    def process_response(self, request, response):
        try:
            if response.status_code not in [403, 404, 500]:
                return response
            
            from .validators import safe_ip_address, extract_client_ip
            
            ip_address = safe_ip_address(
                getattr(request, 'safe_ip', None) or extract_client_ip(request),
                '0.0.0.0'
            )
            
            log_data = {
                'ip': ip_address,
                'path': getattr(request, 'path', '/unknown'),
                'status': response.status_code,
            }
            
            if response.status_code == 404:
                logger.warning(f"🔍 404: {log_data}")
            elif response.status_code == 403:
                logger.warning(f"🔒 403: {log_data}")
            elif response.status_code == 500:
                logger.error(f"💥 500: {log_data}")
        except Exception as e:
            logger.critical(f"[WARN] Logging failed: {e}")
        
        return response








# class SafeIPMiddleware(MiddlewareMixin):
#     """
#     IP address validation middleware - আপনার database error fix করবে
#     """
    
#     def get_client_ip(self, request):
#         """Extract and validate client IP"""
#         try:
#             x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#             if x_forwarded_for:
#                 ip = x_forwarded_for.split(',')[0].strip()
#             else:
#                 ip = request.META.get('REMOTE_ADDR', '')
            
#             # Safe IP validation
#             return safe_ip(ip, default='127.0.0.1')
            
#         except Exception as e:
#             logger.warning(f"IP extraction error: {e}")
#             return '127.0.0.1'
    
#     def process_request(self, request):
#         """Process each request"""
#         request.safe_ip = self.get_client_ip(request)
#         request.META['REMOTE_ADDR'] = request.safe_ip
#         request.META['HTTP_X_REAL_IP'] = request.safe_ip
#         return None


class CircuitBreakerMiddleware(MiddlewareMixin):
    """
    Circuit breaker for tracking failures
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.failure_count = 0
        self.failure_threshold = 10
        self.state = 'CLOSED'
    
    def process_response(self, request, response):
        """Track response status"""
        if response.status_code >= 500:
            self.failure_count += 1
            logger.warning(f"Circuit middleware failure {self.failure_count}/{self.failure_threshold}")
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                logger.error("Circuit breaker OPEN")
        else:
            if self.failure_count > 0:
                self.failure_count -= 1
                if self.failure_count == 0:
                    self.state = 'CLOSED'
        
        return response


class DatabaseErrorMiddleware(MiddlewareMixin):
    """
    Handle database errors gracefully
    """
    
    def process_exception(self, request, exception):
        """Catch and handle database exceptions"""
        
        # Handle invalid IP error specifically
        if 'invalid input syntax for type inet' in str(exception):
            logger.error(f"Database IP error caught: {exception}")
            request.META['REMOTE_ADDR'] = '127.0.0.1'
            return None
        
        # Handle other database errors
        if isinstance(exception, (DatabaseError, OperationalError)):
            logger.error(f"Database error: {exception}")
            logger.error(traceback.format_exc())
            
            if request.path.startswith('/api/'):
                return JsonResponse({
                    'error': 'Database Error',
                    'message': 'A temporary error occurred. Please try again.'
                }, status=503)
            
            return HttpResponse(
                '<h1>Database Error</h1><p>Please try again later.</p>',
                status=503
            )
        
        return None


class PaymentGatewayCircuitBreaker(MiddlewareMixin):
    """
    Circuit breaker for payment gateway calls
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.breakers = {
            'bkash': CircuitBreaker(name='bkash', failure_threshold=3, recovery_timeout=300),
            'nagad': CircuitBreaker(name='nagad', failure_threshold=3, recovery_timeout=300),
            'sslcommerz': CircuitBreaker(name='sslcommerz', failure_threshold=3, recovery_timeout=300),
        }
    
    def process_request(self, request):
        """Check circuit breaker before payment processing"""
        if 'payment' in request.path or 'withdraw' in request.path:
            gateway = self._detect_gateway(request.path)
            if gateway and self.breakers[gateway].state == CircuitBreaker.OPEN:
                logger.warning(f"{gateway} circuit breaker OPEN")
                return JsonResponse({
                    'error': f'{gateway} service temporarily unavailable',
                    'message': 'Please try again later'
                }, status=503)
        return None
    
    def _detect_gateway(self, path):
        """Detect which payment gateway is being called"""
        path_lower = path.lower()
        if 'bkash' in path_lower:
            return 'bkash'
        elif 'nagad' in path_lower:
            return 'nagad'
        elif 'sslcommerz' in path_lower:
            return 'sslcommerz'
        return None


class TransactionAuditMiddleware(MiddlewareMixin):
    """
    Transaction audit logging
    """
    
    def process_response(self, request, response):
        """Log transaction-related requests"""
        if 'transaction' in request.path or 'withdrawal' in request.path or 'wallet' in request.path:
            if response.status_code >= 400:
                user_info = 'Anonymous'
                if hasattr(request, 'user') and request.user.is_authenticated:
                    user_info = f"{request.user.id} - {request.user.username}"
                
                logger.warning(
                    f"Transaction failed: {request.method} {request.path} "
                    f"Status: {response.status_code} User: {user_info}"
                )
        return response


# ============================================
# 🟢 এই ক্লাসটি আগে ছিল না - এখন যোগ করছি
# ============================================

class APIErrorMiddleware(MiddlewareMixin):
    """
    API error handling middleware - এই ক্লাসটি missing ছিল
    """
    
    def process_exception(self, request, exception):
        """Handle API exceptions gracefully"""
        
        # Only handle API requests
        if not request.path.startswith('/api/'):
            return None
        
        logger.error(f"API Error: {exception}")
        logger.error(traceback.format_exc())
        
        # Determine status code based on exception type
        status_code = 500
        error_message = str(exception)
        
        from rest_framework import status
        from django.core.exceptions import PermissionDenied
        from django.http import Http404
        
        if isinstance(exception, Http404):
            status_code = status.HTTP_404_NOT_FOUND
            error_message = "Resource not found"
        elif isinstance(exception, PermissionDenied):
            status_code = status.HTTP_403_FORBIDDEN
            error_message = "Permission denied"
        elif isinstance(exception, ValueError):
            status_code = status.HTTP_400_BAD_REQUEST
        
        # Don't expose internal errors in production
        if not settings.DEBUG and status_code == 500:
            error_message = "An internal server error occurred"
        
        return JsonResponse({
            'error': type(exception).__name__,
            'message': error_message,
            'status': 'error'
        }, status=status_code)


class RequestTimerMiddleware(MiddlewareMixin):
    """
    Request timing middleware for performance monitoring
    """
    
    def process_request(self, request):
        """Start timer"""
        import time
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Log slow requests"""
        if hasattr(request, 'start_time'):
            import time
            duration = (timezone.now() - request.start_time).total_seconds()
            
            # Log slow requests (> 1 second)
            if duration > 1.0:
                logger.warning(f"Slow request: {request.path} took {duration:.2f}s")
            
            # Add timing header for debugging
            response['X-Request-Time'] = f"{duration:.3f}s"
        
        return response


# class SecurityLogMiddleware(MiddlewareMixin):
#     """
#     [SECURE] Security logging middleware - Bulletproof version
    
#     Features:
#     - Validates IP addresses properly
#     - Handles all edge cases
#     - Never crashes
#     - Graceful degradation
#     """
    
#     # IP validation regex
#     IPV4_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
#     IPV6_PATTERN = re.compile(r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}$|^(?:[0-9a-fA-F]{1,4}:){1,7}:$')
    
#     # Safe IP function (bulletproof)
#     @staticmethod
#     def safe_ip(ip, default='0.0.0.0'):
#         """
#         🛡️ Bulletproof IP validation
#         Returns a valid IP or default
#         """
#         # Handle None or empty
#         if ip is None or ip == '':
#             return default
        
#         # Convert to string
#         try:
#             ip_str = str(ip).strip()
#         except:
#             return default
        
#         # Handle 'invalid_ip' string
#         if ip_str == 'invalid_ip' or ip_str.lower() == 'invalid':
#             return default
        
#         # Handle localhost variations
#         if ip_str in ['localhost', '::1', '127.0.0.1']:
#             return '127.0.0.1'
        
#         # Validate IPv4
#         if SecurityLogMiddleware.IPV4_PATTERN.match(ip_str):
#             return ip_str
        
#         # Validate IPv6
#         if SecurityLogMiddleware.IPV6_PATTERN.match(ip_str):
#             return ip_str
        
#         # Try to resolve hostname
#         try:
#             resolved = socket.gethostbyname(ip_str)
#             if SecurityLogMiddleware.IPV4_PATTERN.match(resolved):
#                 return resolved
#         except:
#             pass
        
#         return default
    
#     def process_response(self, request, response):
#         """
#         Log security events based on response status
#         """
#         try:
#             # Only log certain status codes (403, 404, 500)
#             if response.status_code in [403, 404, 500]:
                
#                 # 👤 User info with multiple fallbacks
#                 user_info = self._get_user_info(request)
                
#                 # 🌐 IP address with bulletproof validation
#                 raw_ip = self._extract_ip(request)
#                 ip_to_log = self.safe_ip(raw_ip, '127.0.0.1')
                
#                 # [NOTE] Create log data
#                 log_data = {
#                     'ip': ip_to_log,
#                     'user': user_info,
#                     'path': getattr(request, 'path', '/unknown'),
#                     'method': getattr(request, 'method', 'UNKNOWN'),
#                     'status': response.status_code,
#                     'user_agent': self._safe_get(request.META, 'HTTP_USER_AGENT', 'Unknown')[:255],
#                     'referer': self._safe_get(request.META, 'HTTP_REFERER', ''),
#                     'timestamp': self._get_timestamp(),
#                 }
                
#                 # [STATS] Structured logging
#                 log_msg = f"Status {response.status_code}: {self._safe_json(log_data)}"
                
#                 # 🎯 Log based on status code
#                 if response.status_code == 404:
#                     logger.warning(f"🔍 404 Not Found: {log_msg}")
#                 elif response.status_code == 403:
#                     logger.warning(f"🔒 403 Forbidden: {log_msg}")
#                 elif response.status_code == 500:
#                     logger.error(f"💥 500 Server Error: {log_msg}")
                    
#                     # Also log to error tracking
#                     self._log_error_details(request, response)
        
#         except Exception as e:
#             # 🛡️ Last resort - never crash
#             try:
#                 logger.critical(f"[WARN] Security logging failed: {str(e)[:200]}")
#             except:
#                 pass  # Absolutely last resort
        
#         return response
    
#     def _get_user_info(self, request):
#         """
#         👤 Safely get user information
#         """
#         try:
#             if hasattr(request, 'user') and request.user:
#                 if hasattr(request.user, 'is_authenticated'):
#                     if request.user.is_authenticated:
#                         return getattr(request.user, 'username', 'authenticated')[:50]
#                     return 'anonymous'
#                 return 'unknown_user'
#         except:
#             pass
#         return 'anonymous'
    
#     def _extract_ip(self, request):
#         """
#         🌐 Extract IP from request with multiple fallbacks
#         """
#         # Try common proxy headers first
#         headers = [
#             ('HTTP_X_FORWARDED_FOR', lambda x: x.split(',')[0].strip()),
#             ('HTTP_X_REAL_IP', None),
#             ('HTTP_CLIENT_IP', None),
#             ('HTTP_X_CLUSTER_CLIENT_IP', None),
#             ('HTTP_FORWARDED_FOR', lambda x: x.split(',')[0].strip()),
#             ('REMOTE_ADDR', None),
#         ]
        
#         for header, processor in headers:
#             value = self._safe_get(request.META, header)
#             if value:
#                 try:
#                     if processor:
#                         value = processor(value)
#                     if value and value != 'unknown':
#                         return value
#                 except:
#                     continue
        
#         return '127.0.0.1'
    
#     def _safe_get(self, dictionary, key, default=''):
#         """
#         🛡️ Safe dictionary access
#         """
#         try:
#             return dictionary.get(key, default)
#         except:
#             return default
    
#     def _safe_json(self, data):
#         """
#         🛡️ Safe JSON serialization for logging
#         """
#         try:
#             import json
#             return json.dumps(data, default=str)
#         except:
#             return str(data)
    
#     def _get_timestamp(self):
#         """
#         ⏰ Safe timestamp generation
#         """
#         try:
#             from datetime import datetime
#             return datetime.now().isoformat()
#         except:
#             return 'unknown'
    
#     def _log_error_details(self, request, response):
#         """
#         [NOTE] Log detailed error information for 500 errors
#         """
#         try:
#             # Check if debug mode is on
#             from django.conf import settings
#             if settings.DEBUG:
#                 # Get exception info if available
#                 import sys
#                 exc_type, exc_value, exc_traceback = sys.exc_info()
#                 if exc_value:
#                     logger.error(f"Exception: {exc_type.__name__}: {str(exc_value)[:200]}")
#         except:
#             pass


# ================================================
# 🛡️ IP Validation Utilities (Standalone)
# ================================================

def validate_ip(ip_address, default='0.0.0.0'):
    """
    🛡️ Standalone IP validation function
    """
    return SecurityLogMiddleware.safe_ip(ip_address, default)


def get_client_ip(request):
    """
    🌐 Get client IP from request (bulletproof)
    """
    middleware = SecurityLogMiddleware()
    raw_ip = middleware._extract_ip(request)
    return SecurityLogMiddleware.safe_ip(raw_ip, '127.0.0.1')