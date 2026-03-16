"""
   Audit Middleware for automatic request/response logging
   With Defensive Coding & Null Object Pattern
"""

import time
import json
import uuid
import logging
from typing import Optional, Dict, Any
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import AuditLog, AuditLogConfig
from .services import LogService

logger = logging.getLogger(__name__)
User = get_user_model()

# ==================== DEFENSIVE IP DETECTION ====================
try:
    from ipware import get_client_ip
    IPWARE_AVAILABLE = True
except ImportError:
    IPWARE_AVAILABLE = False
    logger.warning("[WARN] ipware not installed. Using fallback IP detection.")
    
    # Fallback function when ipware is not available
    def get_client_ip(request):
        """Fallback IP detection when ipware is not installed"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip, True


# ==================== SAFE DISPLAY UTILITIES ====================
class SafeDisplay:
    """Null Object Pattern for safe attribute access"""
    
    @staticmethod
    def get(obj, attr: str, default=None):
        """Safely get attribute from object"""
        try:
            return getattr(obj, attr, default) if obj is not None else default
        except Exception:
            return default
    
    @staticmethod
    def dict_get(data: dict, key: str, default=None):
        """Safely get from dictionary"""
        if not isinstance(data, dict):
            return default
        return data.get(key, default)
    
    @staticmethod
    def call(func, default=None, *args, **kwargs):
        """Safely call a function"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.debug(f"Function call failed: {e}")
            return default


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log HTTP requests and responses
    With Defensive Coding & Graceful Degradation
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.log_service = SafeDisplay.call(LogService, None) or None
        super().__init__(get_response)
    
    def process_request(self, request):
        """Process request before view is called"""
        
        try:
            # Generate correlation ID if not present
            if not hasattr(request, 'correlation_id'):
                request.correlation_id = str(uuid.uuid4())
            
            # Start timer for response time
            request._audit_start_time = time.time()
            
            # Store request data for logging
            request._audit_data = {
                'method': SafeDisplay.get(request, 'method', 'UNKNOWN'),
                'path': SafeDisplay.get(request, 'path', '/'),
                'path_info': SafeDisplay.get(request, 'path_info', '/'),
                'get_params': dict(request.GET) if hasattr(request, 'GET') else {},
                'headers': self._get_safe_headers(request),
                'body': self._get_request_body(request),
                'user_ip': self._get_client_ip(request),
                'user_agent': SafeDisplay.dict_get(request.META, 'HTTP_USER_AGENT', ''),
            }
        except Exception as e:
            logger.error(f"Error in process_request: {e}")
        
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Process view before it's called"""
        
        try:
            # Store view information
            if hasattr(request, '_audit_data'):
                request._audit_data.update({
                    'view_name': SafeDisplay.get(view_func, '__name__', None),
                    'view_module': SafeDisplay.get(view_func, '__module__', None),
                    'view_args': view_args,
                    'view_kwargs': view_kwargs,
                })
        except Exception as e:
            logger.debug(f"Error in process_view: {e}")
        
        return None
    
    def process_response(self, request, response):
        """Process response before it's returned"""
        
        try:
            # Calculate response time
            response_time_ms = None
            if hasattr(request, '_audit_start_time'):
                response_time = (time.time() - request._audit_start_time) * 1000  # Convert to ms
                response_time_ms = int(response_time)
            
            # Get user information
            user = request.user if hasattr(request, 'user') else None
            user_id = str(user.id) if user and user.is_authenticated else None
            
            # Determine log level based on response status
            status_code = SafeDisplay.get(response, 'status_code', 500)
            if status_code >= 500:
                level = 'ERROR'
            elif status_code >= 400:
                level = 'WARNING'
            else:
                level = 'INFO'
            
            # Check if we should log this request
            if self._should_log_request(request, response):
                
                # Prepare log data
                log_data = {
                    'correlation_id': getattr(request, 'correlation_id', str(uuid.uuid4())),
                    'user': user if user and user.is_authenticated else None,
                    'anonymous_id': self._get_anonymous_id(request) if not user_id else None,
                    'user_ip': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'user_ip'),
                    'user_agent': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'user_agent'),
                    
                    'action': 'API_CALL',
                    'level': level,
                    
                    'request_method': SafeDisplay.get(request, 'method', 'UNKNOWN'),
                    'request_path': SafeDisplay.get(request, 'path', '/'),
                    'request_params': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'get_params', {}),
                    'request_headers': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'headers', {}),
                    'request_body': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'body'),
                    
                    'response_body': self._get_response_body(response),
                    'status_code': status_code,
                    'response_time_ms': response_time_ms,
                    'success': status_code < 400,
                    
                    'message': f"{SafeDisplay.get(request, 'method', 'UNKNOWN')} {SafeDisplay.get(request, 'path', '/')} - {status_code}",
                    
                    'metadata': {
                        'view_name': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'view_name'),
                        'view_module': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'view_module'),
                        'content_type': SafeDisplay.dict_get(response.headers, 'Content-Type', ''),
                        'content_length': len(response.content) if hasattr(response, 'content') else 0,
                    }
                }
                
                # Add location information if available
                location = self._get_location_info(request)
                if location:
                    log_data.update(location)
                
                # Create log asynchronously
                if self.log_service:
                    self.log_service.create_log_async(**log_data)
                
        except Exception as e:
            logger.error(f"Error in process_response: {e}")
        
        return response
    
    def process_exception(self, request, exception):
        """Process exceptions"""
        
        try:
            user = request.user if hasattr(request, 'user') else None
            
            log_data = {
                'correlation_id': getattr(request, 'correlation_id', str(uuid.uuid4())),
                'user': user if user and user.is_authenticated else None,
                'user_ip': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'user_ip'),
                
                'action': 'API_CALL',
                'level': 'ERROR',
                
                'request_method': SafeDisplay.get(request, 'method', 'UNKNOWN'),
                'request_path': SafeDisplay.get(request, 'path', '/'),
                
                'status_code': 500,
                'success': False,
                'error_message': str(exception),
                'stack_trace': self._get_exception_traceback(exception),
                
                'message': f"Exception in {SafeDisplay.get(request, 'method', 'UNKNOWN')} {SafeDisplay.get(request, 'path', '/')}: {exception}",
                
                'metadata': {
                    'exception_type': type(exception).__name__,
                    'view_name': SafeDisplay.dict_get(getattr(request, '_audit_data', {}), 'view_name'),
                }
            }
            
            # Create log for exception
            if self.log_service:
                self.log_service.create_log_async(**log_data)
                
        except Exception as e:
            logger.error(f"Error in process_exception: {e}")
        
        return None
    
    def _should_log_request(self, request, response):
        """Determine if request should be logged"""
        
        try:
            # Skip health checks, static files, admin panel
            excluded_paths = [
                '/health/', '/ping/', '/favicon.ico',
                '/static/', '/media/', '/admin/',
                '/__debug__/', '/docs/', '/redoc/'
            ]
            
            path = SafeDisplay.get(request, 'path', '/')
            for excluded in excluded_paths:
                if path.startswith(excluded):
                    return False
            
            # Skip OPTIONS requests
            if SafeDisplay.get(request, 'method') == 'OPTIONS':
                return False
            
            # Check config for API_CALL action
            try:
                config = AuditLogConfig.objects.filter(action='API_CALL').first()
                if config and not config.enabled:
                    return False
                
                # Check if we should log based on level
                if config and hasattr(config, 'log_level'):
                    # Convert level to numeric for comparison
                    level_order = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4, 'SECURITY': 5}
                    
                    status_code = SafeDisplay.get(response, 'status_code', 500)
                    response_level = 'ERROR' if status_code >= 500 else \
                                    'WARNING' if status_code >= 400 else 'INFO'
                    
                    if level_order.get(response_level, 1) < level_order.get(config.log_level, 1):
                        return False
                
            except Exception:
                # If config doesn't exist or error, default to logging
                pass
            
        except Exception:
            pass
        
        return True
    
    def _get_client_ip(self, request):
        """Get client IP address with defensive coding"""
        try:
            if IPWARE_AVAILABLE:
                ip, is_routable = get_client_ip(request)
                return ip
            else:
                # Fallback
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    return x_forwarded_for.split(',')[0].strip()
                return request.META.get('REMOTE_ADDR')
        except Exception:
            return None
    
    def _get_anonymous_id(self, request):
        """Get anonymous user ID from session or cookie"""
        try:
            if hasattr(request, 'session') and request.session.session_key:
                return f"session_{request.session.session_key}"
            
            # Try to get from cookies
            anonymous_cookie = request.COOKIES.get('anonymous_id')
            if anonymous_cookie:
                return f"cookie_{anonymous_cookie}"
        except Exception:
            pass
        
        return None
    
    def _get_safe_headers(self, request):
        """Get headers with sensitive information redacted"""
        headers = {}
        
        try:
            for key, value in request.META.items():
                if key.startswith('HTTP_'):
                    header_name = key[5:].replace('_', '-').title()
                    
                    # Redact sensitive headers
                    if header_name.lower() in ['authorization', 'cookie', 'x-api-key']:
                        headers[header_name] = '*** REDACTED ***'
                    else:
                        headers[header_name] = value
        except Exception:
            pass
        
        return headers
    
    def _get_request_body(self, request):
        """Get request body safely"""
        try:
            if request.body:
                content_type = request.META.get('CONTENT_TYPE', '')
                
                # For JSON requests
                if 'application/json' in content_type:
                    return json.loads(request.body.decode('utf-8'))
                # For form data
                elif 'application/x-www-form-urlencoded' in content_type:
                    return dict(request.POST)
                # For multipart form data
                elif 'multipart/form-data' in content_type:
                    # Don't log file uploads
                    data = dict(request.POST)
                    if request.FILES:
                        data['_files'] = list(request.FILES.keys())
                    return data
                
                # Return as string for other types
                body_str = request.body.decode('utf-8', errors='ignore')
                if len(body_str) > 10000:  # Truncate very large bodies
                    return f"[TRUNCATED - {len(body_str)} bytes]"
                
                return body_str[:500] if body_str else None
                
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.debug(f"Error parsing request body: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error parsing request body: {e}")
        
        return None
    
    def _get_response_body(self, response):
        """Get response body safely"""
        try:
            if hasattr(response, 'data'):
                # For DRF responses
                return response.data
            elif hasattr(response, 'content'):
                # For Django responses
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    return json.loads(response.content.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as e:
            logger.debug(f"Error parsing response body: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error parsing response body: {e}")
        
        return None
    
    def _get_location_info(self, request):
        """Get location information from IP"""
        # This would typically use a geolocation service
        # For now, return empty dict
        return {}
    
    def _get_exception_traceback(self, exception):
        """Get exception traceback as string"""
        try:
            import traceback
            return ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            ))
        except Exception:
            return str(exception)


class AuditUserActivityMiddleware(MiddlewareMixin):
    """
    Middleware to track user activities like login, logout
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.log_service = SafeDisplay.call(LogService, None) or None
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """Track user logout activity"""
        
        try:
            # Check for logout
            path = SafeDisplay.get(request, 'path', '')
            if path.endswith('/logout/') and request.method == 'POST':
                user = request.user if hasattr(request, 'user') else None
                
                if user and user.is_authenticated:
                    if self.log_service:
                        self.log_service.create_log_async(
                            user=user,
                            action='LOGOUT',
                            level='INFO',
                            message=f"User {SafeDisplay.get(user, 'email', 'unknown')} logged out",
                            user_ip=self._get_client_ip(request),
                            user_agent=SafeDisplay.dict_get(request.META, 'HTTP_USER_AGENT', ''),
                            request_method=request.method,
                            request_path=path,
                            status_code=SafeDisplay.get(response, 'status_code', 200),
                            success=SafeDisplay.get(response, 'status_code', 200) < 400,
                        )
        except Exception as e:
            logger.error(f"Error in AuditUserActivityMiddleware: {e}")
        
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        try:
            if IPWARE_AVAILABLE:
                ip, _ = get_client_ip(request)
                return ip
            else:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    return x_forwarded_for.split(',')[0].strip()
                return request.META.get('REMOTE_ADDR')
        except Exception:
            return None


class AuditPerformanceMiddleware(MiddlewareMixin):
    """
    Middleware to track performance metrics
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.log_service = SafeDisplay.call(LogService, None) or None
        self.slow_request_threshold = 1000  # 1 second in ms
        
    def process_request(self, request):
        try:
            request._performance_start = time.time()
        except Exception:
            pass
        return None
    
    def process_response(self, request, response):
        try:
            if hasattr(request, '_performance_start'):
                response_time = (time.time() - request._performance_start) * 1000
                
                # Log slow requests
                if response_time > self.slow_request_threshold:
                    user = request.user if hasattr(request, 'user') else None
                    
                    if self.log_service:
                        self.log_service.create_log_async(
                            user=user,
                            action='API_CALL',
                            level='WARNING',
                            message=f"Slow request: {SafeDisplay.get(request, 'method', 'UNKNOWN')} {SafeDisplay.get(request, 'path', '/')} took {response_time:.0f}ms",
                            user_ip=self._get_client_ip(request),
                            request_method=SafeDisplay.get(request, 'method', 'UNKNOWN'),
                            request_path=SafeDisplay.get(request, 'path', '/'),
                            status_code=SafeDisplay.get(response, 'status_code', 200),
                            response_time_ms=int(response_time),
                            metadata={
                                'performance': {
                                    'response_time_ms': int(response_time),
                                    'threshold_ms': self.slow_request_threshold,
                                    'is_slow': True
                                }
                            }
                        )
        except Exception as e:
            logger.debug(f"Error in AuditPerformanceMiddleware: {e}")
        
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        try:
            if IPWARE_AVAILABLE:
                ip, _ = get_client_ip(request)
                return ip
            else:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    return x_forwarded_for.split(',')[0].strip()
                return request.META.get('REMOTE_ADDR')
        except Exception:
            return None


class AuditLogMiddleware:
    """Simple middleware for basic IP logging"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            # ইউজারের আইপি অ্যাড্রেস বের করা
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            request.audit_ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
        except Exception:
            request.audit_ip = None
        
        response = self.get_response(request)
        return response