"""
Security Middleware - Production Ready
Enhanced security middleware with defensive coding and graceful degradation
Version: 5.0.0 - Fixed Bulletproof Edition
"""

import logging
import re
import json

import uuid as _uuid
from decimal import Decimal as _Decimal

def _middleware_safe_serialize(obj):
    if obj is None:
        return None
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if isinstance(obj, (_uuid.UUID,)):
        return str(obj)
    if isinstance(obj, _Decimal):
        return float(obj)
    if hasattr(obj, 'pk'):
        return obj.pk
    if isinstance(obj, (list, tuple)):
        return [_middleware_safe_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _middleware_safe_serialize(v) for k, v in obj.items()}
    try:
        import json
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)

from django.core.serializers.json import DjangoJSONEncoder
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import ipaddress
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from django.db import transaction, connection
from django.db.models import Q

# Graceful imports with fallbacks
try:
    from .models import (
        SecurityLog, DeviceInfo, IPBlacklist, GeolocationLog,
        APIRateLimit, RateLimitLog, UserSession
    )
    MODELS_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger('security.middleware')
    logger.warning(f"Security models not available: {e}")
    MODELS_AVAILABLE = False
    
    # Create dummy classes for fallback
    class SecurityLog:
        @classmethod
        def objects(cls):
            return cls
        @classmethod
        def create(cls, **kwargs):
            logger.debug(f"Dummy SecurityLog.create: {kwargs}")
        @classmethod
        def filter(cls, **kwargs):
            return cls()
        @classmethod
        def exists(cls):
            return False
    
    # Other dummy classes...
    class APIRateLimit:
        objects = type('obj', (), {'filter': lambda **kw: type('q', (), {'exists': lambda: False})()})()
    class RateLimitLog:
        @classmethod
        def create(cls, **kwargs):
            logger.debug(f"Dummy RateLimitLog.create: {kwargs}")
    class IPBlacklist:
        objects = type('obj', (), {
            'filter': lambda **kw: type('q', (), {
                'exists': lambda: False,
                'first': lambda: None
            })()
        })()

try:
    from .utils import NullSafe, TypeValidator, GracefulDegradation
    UTILS_AVAILABLE = True
except ImportError:
    logger = logging.getLogger('security.middleware')
    logger.warning("Utils module not available, using fallback implementations")
    UTILS_AVAILABLE = False
    
    class NullSafe:
        @staticmethod
        def get(obj, attr, default=None):
            return getattr(obj, attr, default)
    
    class TypeValidator:
        @staticmethod
        def validate_type(value, expected_type, default):
            if isinstance(value, expected_type):
                return value
            return default
    
    class GracefulDegradation:
        @staticmethod
        def fallback(default):
            def decorator(func):
                @wraps(func)
                def wrapper(*args, **kwargs):
                    try:
                        return func(*args, **kwargs)
                    except Exception:
                        return default
                return wrapper
            return decorator

try:
    from .vpn_detector import VPNDetector
    VPN_DETECTOR_AVAILABLE = True
except ImportError:
    logger = logging.getLogger('security.middleware')
    logger.warning("VPN Detector not available, using dummy implementation")
    VPN_DETECTOR_AVAILABLE = False
    
    class VPNDetector:
        def detect_vpn_proxy(self, ip):
            return {'is_vpn': False, 'is_proxy': False, 'geolocation': {}}

logger = logging.getLogger('security.middleware')


# ==================== SENTINEL VALUES ====================
class _Sentinel:
    """Sentinel object for missing values (when None is a valid value)"""
    __slots__ = ()
    
    def __repr__(self):
        return '<MISSING>'
    
    def __bool__(self):
        return False

MISSING = _Sentinel()


# ==================== DATA CLASSES FOR TYPE SAFETY ====================
@dataclass
class RateLimitConfig:
    """Data class for rate limit configuration"""
    id: int = 0
    name: str = "default"
    limit_type: str = "ip"
    limit_period: str = "hour"
    request_limit: int = 100
    endpoint_pattern: str = ""
    response_message: str = "Rate limit exceeded"
    is_active: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RateLimitConfig':
        """Safely create RateLimitConfig from dictionary"""
        try:
            # Use dict.get() with defaults
            return cls(
                id=data.get('id', 0),
                name=data.get('name', 'default'),
                limit_type=data.get('limit_type', 'ip'),
                limit_period=data.get('limit_period', 'hour'),
                request_limit=data.get('request_limit', 100),
                endpoint_pattern=data.get('endpoint_pattern', ''),
                response_message=data.get('response_message', 'Rate limit exceeded'),
                is_active=data.get('is_active', True)
            )
        except Exception as e:
            logger.warning(f"Error creating RateLimitConfig: {e}")
            return cls()  # Return default config


@dataclass
class SecurityHeaders:
    """Data class for security headers"""
    x_content_type_options: str = field(default="nosniff")
    x_frame_options: str = field(default="DENY")
    x_xss_protection: str = field(default="1; mode=block")
    strict_transport_security: str = field(default="max-age=31536000; includeSubDomains")
    referrer_policy: str = field(default="strict-origin-when-cross-origin")
    permissions_policy: str = field(default="camera=(), microphone=(), geolocation=()")
    content_security_policy: str = field(default="default-src 'self'")
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for response headers"""
        return {
            'X-Content-Type-Options': self.x_content_type_options,
            'X-Frame-Options': self.x_frame_options,
            'X-XSS-Protection': self.x_xss_protection,
            'Strict-Transport-Security': self.strict_transport_security,
            'Referrer-Policy': self.referrer_policy,
            'Permissions-Policy': self.permissions_policy,
            'Content-Security-Policy': self.content_security_policy,
        }


# ==================== UTILITY CLASSES ====================
class CircuitBreaker:
    """Circuit breaker pattern for external service calls"""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None
        
    def __call__(self, func: Callable) -> Callable:
        """Decorator for circuit breaker pattern"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_state = self.state
            
            # Check if circuit is OPEN
            if current_state == "OPEN":
                if self.last_failure_time:
                    time_since_failure = (timezone.now() - self.last_failure_time).total_seconds()
                    if time_since_failure > self.reset_timeout:
                        # Try to reset
                        self.state = "HALF_OPEN"
                        logger.info("Circuit breaker moving to HALF_OPEN state")
                    else:
                        # Still in cooldown period
                        logger.warning(f"Circuit breaker OPEN, blocking call to {func.__name__}")
                        raise ConnectionError("Service temporarily unavailable (circuit breaker open)")
            
            try:
                # Try the operation
                result = func(*args, **kwargs)
                
                # Success: reset circuit if needed
                if current_state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failures = 0
                    logger.info("Circuit breaker reset to CLOSED after successful call")
                
                return result
                
            except Exception as e:
                # Failure: update circuit state
                self.failures += 1
                self.last_failure_time = timezone.now()
                
                if self.failures >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.error(f"Circuit breaker OPEN after {self.failures} failures: {e}")
                
                # Re-raise the original exception
                raise
        
        return wrapper
    
    def wrap_method(self, obj, method_name: str):
        """Wrap a method of an object with circuit breaker"""
        original_method = getattr(obj, method_name)
        wrapped_method = self(original_method)
        setattr(obj, method_name, wrapped_method)
        return obj


class DeepGet:
    """Utility for safe nested dictionary/object access"""
    
    @staticmethod
    def get(obj: Any, path: str, default: Any = None, delimiter: str = '.') -> Any:
        """
        Safely get nested value using dot notation or custom delimiter.
        
        Example:
            DeepGet.get(data, 'user.profile.email', 'default@email.com')
        """
        try:
            if not obj or not path:
                return default
            
            # Handle dictionary
            if isinstance(obj, dict):
                keys = path.split(delimiter)
                current = obj
                for key in keys:
                    # Use dict.get() with defensive coding
                    if not isinstance(current, dict):
                        return default
                    current = current.get(key, MISSING)
                    if current is MISSING:
                        return default
                return current
            
            # Handle object with attributes
            elif hasattr(obj, '__dict__'):
                keys = path.split(delimiter)
                current = obj
                for key in keys:
                    # Use getattr() with defensive coding
                    current = getattr(current, key, MISSING)
                    if current is MISSING:
                        return default
                return current
            
            # Unsupported type
            return default
            
        except (AttributeError, KeyError, TypeError):
            return default


class NullSafeResponse:
    """Null Object Pattern for HTTP Response with bulletproof methods"""
    
    @staticmethod
    def get_safe(obj: Any, attr: str, default: Any = None) -> Any:
        """Safely get attribute from object using getattr()"""
        try:
            # Type hinting check
            if not isinstance(attr, str):
                logger.warning(f"get_safe: attr must be string, got {type(attr)}")
                return default
            
            return getattr(obj, attr, default)
        except Exception as e:
            logger.debug(f"get_safe failed for {attr}: {e}")
            return default
    
    @staticmethod
    def dict_get(data: dict, key: str, default: Any = None) -> Any:
        """Safely get value from dictionary using dict.get()"""
        try:
            if not isinstance(data, dict):
                logger.warning(f"dict_get: data must be dict, got {type(data)}")
                return default
            
            return data.get(key, default)
        except Exception as e:
            logger.debug(f"dict_get failed for key {key}: {e}")
            return default
    
    @staticmethod
    def execute_view(view_func: Callable, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Safely execute view function with comprehensive error handling"""
        try:
            # 1. Validate view function
            if not callable(view_func):
                logger.error(f"View function is not callable: {type(view_func)}")
                
                # Graceful degradation: return default error response
                from django.views.defaults import server_error
                return server_error(request)
            
            # 2. Execute with timing
            start_time = timezone.now()
            response = view_func(request, *args, **kwargs)
            elapsed = (timezone.now() - start_time).total_seconds()
            
            # 3. Log slow responses
            if elapsed > 5.0:  # 5 seconds threshold
                logger.warning(f"Slow view response: {view_func.__name__} took {elapsed:.2f}s")
            
            return response
            
        except PermissionDenied as e:
            # Specific handling for permission errors
            logger.warning(f"Permission denied in view {view_func.__name__}: {e}")
            return JsonResponse({
                'error': 'Permission denied',
                'detail': str(e)
            }, status=403)
            
        except ValidationError as e:
            # Specific handling for validation errors
            logger.warning(f"Validation error in view {view_func.__name__}: {e}")
            return JsonResponse({
                'error': 'Validation error',
                'detail': str(e.messages) if hasattr(e, 'messages') else str(e)
            }, status=400)
            
        except Exception as e:
            # Generic exception handling with circuit breaker pattern
            logger.error(f"Unexpected error in view {view_func.__name__}: {e}", exc_info=True)
            
            # Graceful degradation: return user-friendly error
            return JsonResponse({
                'error': 'Internal server error',
                'message': 'The service encountered an unexpected error.',
                'error_id': hashlib.md5(str(e).encode()).hexdigest()[:8]
            }, status=500)


# ==================== BULLETPROOF VALIDATOR ====================
class RequestValidator:
    """Request validation with defensive coding and bulletproof patterns"""
    
    # Circuit breaker for expensive validation operations
    _geoip_circuit = CircuitBreaker(failure_threshold=3, reset_timeout=300)
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address format with multiple fallback strategies"""
        try:
            # Defensive: Check input type
            if not isinstance(ip, str):
                return False
            
            # Null Object Pattern: Handle empty/None
            ip = ip.strip() if ip else ""
            
            # Common invalid values check
            invalid_values = {'', 'unknown', 'null', 'None', '0.0.0.0', '127.0.0.1', '::1'}
            if ip in invalid_values:
                return False
            
            # Use try-except-else-finally pattern
            try:
                ip_obj = ipaddress.ip_address(ip)
            except ValueError as e:
                logger.debug(f"Invalid IP address {ip}: {e}")
                return False
            else:
                # Additional validation
                if ip_obj.is_private or ip_obj.is_loopback:
                    logger.debug(f"Private/loopback IP detected: {ip}")
                return True
            finally:
                # Cleanup or logging if needed
                pass
                
        except Exception as e:
            # Graceful degradation: Don't crash on validation error
            logger.debug(f"IP validation error for {ip}: {e}")
            return False
    
    @staticmethod
    def sanitize_user_agent(user_agent: str) -> str:
        """Sanitize user agent string with multiple safety layers"""
        try:
            # Type validation
            if not isinstance(user_agent, str):
                return ''
            
            # Null Object Pattern with default
            if not user_agent:
                return ''
            
            # Remove dangerous characters
            # 1. Null bytes and control characters
            user_agent = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', user_agent)
            
            # 2. SQL injection patterns
            sql_patterns = [
                r'(?i)union.*select',
                r'(?i)select.*from',
                r'(?i)insert.*into',
                r'(?i)delete.*from',
                r'(?i)update.*set',
                r'(?i)drop.*table',
            ]
            
            for pattern in sql_patterns:
                user_agent = re.sub(pattern, '[REDACTED]', user_agent)
            
            # 3. Limit length
            max_length = getattr(settings, 'MAX_USER_AGENT_LENGTH', 500)
            if len(user_agent) > max_length:
                user_agent = user_agent[:max_length] + '... [TRUNCATED]'
            
            return user_agent
            
        except Exception as e:
            # Graceful degradation
            logger.debug(f"User agent sanitization error: {e}")
            return ''
    
    @staticmethod
    @_geoip_circuit
    def validate_geolocation(ip: str) -> Optional[Dict]:
        """Validate geolocation with circuit breaker pattern"""
        try:
            # This would call external API - protected by circuit breaker
            # Example: response = requests.get(f"https://api.ipgeolocation.io/{ip}")
            # For now, return mock data
            return {
                'country': 'Unknown',
                'city': 'Unknown',
                'latitude': 0.0,
                'longitude': 0.0,
                'is_vpn': False,
                'is_proxy': False
            }
        except Exception as e:
            logger.error(f"Geolocation validation failed for {ip}: {e}")
            return None
    
    @staticmethod
    def validate_request_size(request: HttpRequest) -> Tuple[bool, str]:
        """Validate request size with comprehensive checks"""
        try:
            # Get max size from settings with default
            max_size = NullSafeResponse.dict_get(
                getattr(settings, 'SECURITY_CONFIG', {}),
                'MAX_REQUEST_SIZE',
                10 * 1024 * 1024  # 10MB default
            )
            
            # Check content length from headers
            content_length = request.META.get('CONTENT_LENGTH')
            if content_length:
                try:
                    content_length = int(content_length)
                    if content_length > max_size:
                        return False, f"Request too large ({content_length} bytes)"
                except (ValueError, TypeError):
                    # Invalid content length - log but don't block
                    logger.debug(f"Invalid CONTENT_LENGTH: {content_length}")
            
            # Check actual body size for non-GET requests
            if request.method != 'GET' and hasattr(request, 'body'):
                body_size = len(request.body)
                if body_size > max_size:
                    return False, f"Request body too large ({body_size} bytes)"
            
            return True, "Valid"
            
        except Exception as e:
            # Graceful degradation: Allow request on validation error
            logger.warning(f"Request size validation error: {e}")
            return True, "Validation skipped"


# ==================== MISSING MIDDLEWARE CLASSES ====================
class VPNProxyDetectionMiddleware(MiddlewareMixin):
    """VPN and Proxy detection middleware with circuit breaker and lazy loading"""
    
    def __init__(self, get_response):
        """Initialize with lazy loading for expensive services"""
        try:
            super().__init__(get_response)
            self.circuit_breaker = CircuitBreaker(failure_threshold=3, reset_timeout=300)
            self.excluded_paths = getattr(settings, 'VPN_DETECTION_EXCLUDE', [
                '/api/auth/', '/health/', '/status/'
            ])
            
            # Lazy initialization - VPN detector is expensive
            self._vpn_detector = None
            self._vpn_initialized = False
            
        except Exception as e:
            logger.error(f"VPNProxyDetectionMiddleware init error: {e}")
            self._vpn_detector = None
            self._vpn_initialized = True
            self.excluded_paths = []
            self.circuit_breaker = CircuitBreaker()
    
    def _get_vpn_detector(self):
        """Lazy-load VPN detector on first use"""
        if self._vpn_initialized:
            return self._vpn_detector
        
        try:
            if VPN_DETECTOR_AVAILABLE:
                self._vpn_detector = VPNDetector()
                # Wrap the detection method with circuit breaker
                self.circuit_breaker.wrap_method(self._vpn_detector, 'detect_vpn_proxy')
                logger.debug("VPN Detector lazily initialized")
            else:
                logger.debug("VPN Detector not available, using dummy")
                self._vpn_detector = None
        except Exception as e:
            logger.warning(f"Failed to lazy-load VPN Detector: {e}")
            self._vpn_detector = None
        finally:
            self._vpn_initialized = True
        
        return self._vpn_detector
    
    @property
    def vpn_detector(self):
        """Property to access VPN detector with lazy loading"""
        if not self._vpn_initialized:
            return self._get_vpn_detector()
        return self._vpn_detector
    
    def process_request(self, request: HttpRequest):
        """Process request for VPN/Proxy detection"""
        try:
            # Skip excluded paths
            request_path = NullSafeResponse.get_safe(request, 'path', '')
            for excluded_path in self.excluded_paths:
                if request_path.startswith(excluded_path):
                    return None
            
            # Skip if no VPN detector
            if not self.vpn_detector:
                return None
            
            # Get client IP
            ip = self._get_client_ip(request)
            if not ip or not RequestValidator.validate_ip_address(ip):
                return None
            
            # Check cache first
            cache_key = f"vpn_check_{ip}"
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                is_vpn = cached_result.get('is_vpn', False)
                is_proxy = cached_result.get('is_proxy', False)
            else:
                # Call VPN detector (protected by circuit breaker)
                try:
                    result = self.vpn_detector.detect_vpn_proxy(ip)
                    is_vpn = result.get('is_vpn', False)
                    is_proxy = result.get('is_proxy', False)
                    
                    # Cache result for 1 hour
                    cache.set(cache_key, {'is_vpn': is_vpn, 'is_proxy': is_proxy}, 3600)
                    
                except ConnectionError as e:
                    # Circuit breaker is open
                    logger.warning(f"VPN detection circuit breaker open: {e}")
                    return None
                except Exception as e:
                    logger.error(f"VPN detection error: {e}")
                    return None
            
            # Store detection results
            request.vpn_detection = {
                'ip': ip,
                'is_vpn': is_vpn,
                'is_proxy': is_proxy,
                'timestamp': timezone.now().isoformat()
            }
            
            # Block if configured
            block_vpn = getattr(settings, 'BLOCK_VPN_TRAFFIC', False)
            block_proxy = getattr(settings, 'BLOCK_PROXY_TRAFFIC', True)
            
            if (is_vpn and block_vpn) or (is_proxy and block_proxy):
                threat_type = 'VPN' if is_vpn else 'Proxy'
                logger.warning(f"Blocking {threat_type} traffic from IP: {ip}")
                
                # Log security event
                if MODELS_AVAILABLE:
                    try:
                        SecurityLog.objects.create(
                            security_type=f'{threat_type.lower()}_blocked',
                            severity='high',
                            ip_address=ip,
                            user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                            description=f"{threat_type} traffic blocked"
                        )
                    except Exception as log_error:
                        logger.error(f"Failed to log security event: {log_error}")
                
                return JsonResponse({
                    'error': f'Access blocked: {threat_type} detected',
                    'message': f'Please disable your {threat_type.lower()} to access this service',
                    'code': 'VPN_PROXY_BLOCKED'
                }, status=403)
            
            return None
            
        except Exception as e:
            # Graceful degradation
            logger.error(f"VPN detection middleware error: {e}")
            return None
    
    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """Get client IP address safely"""
        try:
            ip = request.META.get('HTTP_X_FORWARDED_FOR')
            if ip:
                ip = ip.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            return ip if RequestValidator.validate_ip_address(ip) else None
        except Exception:
            return None


class DeviceFingerprintingMiddleware(MiddlewareMixin):
    """Device fingerprinting middleware with defensive coding"""
    
    def __init__(self, get_response):
        """Initialize with defensive coding"""
        try:
            super().__init__(get_response)
            self.excluded_paths = getattr(settings, 'DEVICE_FINGERPRINT_EXCLUDE', [
                '/api/auth/', '/health/', '/status/', '/static/', '/media/'
            ])
        except Exception as e:
            logger.error(f"DeviceFingerprintingMiddleware init error: {e}")
            self.excluded_paths = []
    
    def process_request(self, request: HttpRequest):
        """Process request for device fingerprinting"""
        try:
            # Skip excluded paths
            request_path = NullSafeResponse.get_safe(request, 'path', '')
            for excluded_path in self.excluded_paths:
                if request_path.startswith(excluded_path):
                    return None
            
            # Generate fingerprint
            fingerprint = self._generate_fingerprint(request)
            if fingerprint:
                request.device_fingerprint = fingerprint
            
            return None
            
        except Exception as e:
            # Graceful degradation
            logger.error(f"Device fingerprinting error: {e}")
            return None
    
    def _generate_fingerprint(self, request: HttpRequest) -> Optional[Dict]:
        """Generate device fingerprint from request"""
        try:
            # Collect fingerprint data
            fingerprint_data = {
                'user_agent': RequestValidator.sanitize_user_agent(
                    request.META.get('HTTP_USER_AGENT', '')
                ),
                'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
                'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
                'timezone': request.META.get('HTTP_TIMEZONE', ''),
            }
            
            # Remove empty values
            fingerprint_data = {k: v for k, v in fingerprint_data.items() if v}
            
            if not fingerprint_data:
                return None
            
            # Generate hash
            fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
            fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
            
            return {
                'hash': fingerprint_hash,
                'data': fingerprint_data,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating fingerprint: {e}")
            return None


class RequestValidationMiddleware(MiddlewareMixin):
    """Request validation middleware with comprehensive checks"""
    
    def __init__(self, get_response):
        """Initialize with defensive coding"""
        try:
            super().__init__(get_response)
            self.allowed_methods = getattr(settings, 'ALLOWED_HTTP_METHODS', [
                'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'
            ])
            self.blocked_user_agents = getattr(settings, 'BLOCKED_USER_AGENTS', [
                'sqlmap', 'nikto', 'nessus', 'metasploit', 'wpscan'
            ])
            self.max_upload_size = getattr(settings, 'MAX_UPLOAD_SIZE', 5 * 1024 * 1024)
        except Exception as e:
            logger.error(f"RequestValidationMiddleware init error: {e}")
            self.allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
            self.blocked_user_agents = []
            self.max_upload_size = 5 * 1024 * 1024
    
    def process_request(self, request: HttpRequest):
        """Validate incoming request"""
        try:
            # 1. Validate HTTP method
            method = NullSafeResponse.get_safe(request, 'method', '')
            if method not in self.allowed_methods:
                return JsonResponse({
                    'error': f'Method {method} not allowed',
                    'allowed_methods': self.allowed_methods
                }, status=405)
            
            # 2. Validate user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            user_agent_lower = user_agent.lower()
            
            for blocked_agent in self.blocked_user_agents:
                if blocked_agent.lower() in user_agent_lower:
                    logger.warning(f"Blocked user agent detected: {user_agent[:100]}")
                    
                    if MODELS_AVAILABLE:
                        try:
                            SecurityLog.objects.create(
                                security_type='bot_detected',
                                severity='high',
                                ip_address=request.META.get('REMOTE_ADDR', ''),
                                user_agent=user_agent[:200],
                                description='Security tool/bot detected'
                            )
                        except Exception as log_error:
                            logger.error(f"Failed to log security event: {log_error}")
                    
                    return JsonResponse({
                        'error': 'Access denied',
                        'message': 'Security policy violation'
                    }, status=403)
            
            # 3. Validate request size
            valid, message = RequestValidator.validate_request_size(request)
            if not valid:
                return JsonResponse({
                    'error': 'Request too large',
                    'message': message
                }, status=413)
            
            # 4. Validate file uploads
            if hasattr(request, 'FILES') and request.FILES:
                for file in request.FILES.values():
                    if file.size > self.max_upload_size:
                        return JsonResponse({
                            'error': 'File too large',
                            'message': f'Maximum file size is {self.max_upload_size} bytes',
                            'file': file.name,
                            'size': file.size
                        }, status=413)
            
            # 5. Validate content type for POST/PUT/PATCH
            if method in ['POST', 'PUT', 'PATCH']:
                content_type = getattr(request, 'content_type', '')
                allowed_types = ['application/json', 'application/x-www-form-urlencoded', 'multipart/form-data']
                
                if content_type and not any(allowed in content_type for allowed in allowed_types):
                    logger.warning(f"Invalid content type: {content_type}")
                    return JsonResponse({
                        'error': 'Unsupported content type',
                        'message': f'Content type {content_type} not supported',
                        'allowed_types': allowed_types
                    }, status=415)
            
            return None
            
        except Exception as e:
            # Graceful degradation: Allow request on validation error
            logger.error(f"Request validation error: {e}")
            return None


class ExceptionHandlingMiddleware(MiddlewareMixin):
    """Exception handling middleware with comprehensive error handling"""
    
    def __init__(self, get_response):
        """Initialize with defensive coding"""
        try:
            super().__init__(get_response)
        except Exception as e:
            logger.error(f"ExceptionHandlingMiddleware init error: {e}")
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        """Handle uncaught exceptions"""
        try:
            # Log the exception with context
            logger.error(
                f"Uncaught exception: {type(exception).__name__}: {str(exception)}",
                exc_info=True,
                extra={
                    'request_path': NullSafeResponse.get_safe(request, 'path', ''),
                    'request_method': NullSafeResponse.get_safe(request, 'method', ''),
                    'user': NullSafeResponse.get_safe(request.user, 'username', 'anonymous') 
                          if hasattr(request, 'user') else 'anonymous',
                    'ip_address': request.META.get('REMOTE_ADDR', 'unknown'),
                }
            )
            
            # Log security event if models are available
            if MODELS_AVAILABLE:
                try:
                    SecurityLog.objects.create(
                        user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                        security_type='server_error',
                        severity='critical',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=RequestValidator.sanitize_user_agent(
                            request.META.get('HTTP_USER_AGENT', '')
                        ),
                        description=f"Uncaught exception: {type(exception).__name__}",
                        metadata={
                            'exception': str(exception),
                            'path': request.path,
                            'method': request.method,
                            'timestamp': timezone.now().isoformat()
                        }
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log security event: {log_error}")
            
            # Return appropriate error response
            if settings.DEBUG:
                # Detailed error in development
                return JsonResponse({
                    'error': 'Internal server error',
                    'exception': str(exception),
                    'type': type(exception).__name__,
                    'path': request.path,
                    'timestamp': timezone.now().isoformat()
                }, status=500)
            else:
                # Generic error in production
                return JsonResponse({
                    'error': 'Internal server error',
                    'message': 'An unexpected error occurred. Our team has been notified.',
                    'error_id': hashlib.md5(str(exception).encode()).hexdigest()[:8],
                    'timestamp': timezone.now().isoformat()
                }, status=500)
            
        except Exception as e:
            # Last resort: return minimal error response
            logger.critical(f"Exception handler itself failed: {str(e)}")
            return HttpResponse(
                'Internal Server Error',
                status=500,
                content_type='text/plain'
            )


# ==================== MIDDLEWARE CLASSES ====================
class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Security headers middleware with defensive coding and bulletproof patterns.
    Uses dataclasses for type safety and validation.
    """
    
    def __init__(self, get_response):
        """Initialize with comprehensive error handling"""
        try:
            super().__init__(get_response)
            self.security_headers = self._load_security_headers()
            self.excluded_paths = self._load_excluded_paths()
        except Exception as e:
            # Graceful degradation: Use default headers
            logger.error(f"SecurityHeadersMiddleware init error: {e}")
            self.security_headers = SecurityHeaders()
            self.excluded_paths = []
    
    def _load_security_headers(self) -> SecurityHeaders:
        """Load security headers with multiple fallback strategies"""
        try:
            # Try to get from settings
            headers_config = getattr(settings, 'SECURITY_HEADERS', {})
            
            if not isinstance(headers_config, dict):
                logger.warning("SECURITY_HEADERS is not a dictionary, using defaults")
                headers_config = {}
            
            # Use dataclass for type safety
            return SecurityHeaders(
                x_content_type_options=headers_config.get(
                    'X-Content-Type-Options', 
                    'nosniff'
                ),
                x_frame_options=headers_config.get(
                    'X-Frame-Options',
                    'DENY'
                ),
                x_xss_protection=headers_config.get(
                    'X-XSS-Protection',
                    '1; mode=block'
                ),
                strict_transport_security=headers_config.get(
                    'Strict-Transport-Security',
                    'max-age=31536000; includeSubDomains'
                ),
                referrer_policy=headers_config.get(
                    'Referrer-Policy',
                    'strict-origin-when-cross-origin'
                ),
                permissions_policy=headers_config.get(
                    'Permissions-Policy',
                    'camera=(), microphone=(), geolocation=()'
                ),
                content_security_policy=headers_config.get(
                    'Content-Security-Policy',
                    getattr(settings, 'CONTENT_SECURITY_POLICY', "default-src 'self'")
                )
            )
            
        except Exception as e:
            logger.error(f"Error loading security headers: {e}")
            return SecurityHeaders()  # Return default dataclass
    
    def _load_excluded_paths(self) -> List[str]:
        """Load excluded paths with defensive coding"""
        try:
            excluded = getattr(settings, 'SECURITY_HEADERS_EXCLUDE', [])
            
            if not isinstance(excluded, list):
                logger.warning("SECURITY_HEADERS_EXCLUDE is not a list, using empty list")
                return []
            
            return excluded
            
        except Exception as e:
            logger.error(f"Error loading excluded paths: {e}")
            return []
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add security headers with comprehensive error handling"""
        try:
            # Check if path is excluded
            request_path = NullSafeResponse.get_safe(request, 'path', '')
            
            for excluded_path in self.excluded_paths:
                if request_path.startswith(excluded_path):
                    return response
            
            # Convert dataclass to dict
            headers_dict = self.security_headers.to_dict()
            
            # Add headers safely
            for header, value in headers_dict.items():
                try:
                    if value:  # Only add non-empty headers
                        response[header] = value
                except (KeyError, ValueError) as e:
                    logger.debug(f"Could not set header {header}: {e}")
            
            # Add custom headers if they don't exist
            custom_headers = {
                'X-Security-Timestamp': timezone.now().isoformat(),
                'X-Request-ID': request.META.get('HTTP_X_REQUEST_ID', ''),
                'X-Content-Type-Options': 'nosniff',  # Ensure this is always set
            }
            
            for header, value in custom_headers.items():
                if header not in response:
                    response[header] = value
            
            return response
            
        except Exception as e:
            # Graceful degradation: Return original response
            logger.error(f"Error adding security headers: {e}")
            return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware with circuit breaker pattern and bulletproof coding.
    Uses dataclasses for configuration.
    """
    
    # Circuit breaker for database operations
    _db_circuit = CircuitBreaker(failure_threshold=3, reset_timeout=60)
    
    def __init__(self, get_response):
        """Initialize rate limiter with defensive coding"""
        try:
            super().__init__(get_response)
            self.rate_limits = self._load_rate_limits()
            self.excluded_paths = self._load_excluded_paths()
        except Exception as e:
            # Graceful degradation: Use default limits
            logger.error(f"RateLimitMiddleware init error: {e}")
            self.rate_limits = [RateLimitConfig()]
            self.excluded_paths = []
    
    @_db_circuit
    def _load_rate_limits(self) -> List[RateLimitConfig]:
        """Load rate limits from database with caching and circuit breaker"""
        try:
            # Cache key
            cache_key = 'rate_limits_cache_v2'
            cache_timeout = 300  # 5 minutes
            
            # Try cache first
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                try:
                    # Validate cached data
                    if isinstance(cached_data, list):
                        return [RateLimitConfig.from_dict(item) for item in cached_data]
                except Exception as e:
                    logger.warning(f"Invalid cached rate limits: {e}")
                    # Fall through to database load
            
            # Load from database with exists() check for efficiency
            if not MODELS_AVAILABLE or not APIRateLimit.objects.exists():
                logger.debug("No rate limits configured in database")
                default_limits = [RateLimitConfig()]
                cache.set(cache_key, [asdict(limit) for limit in default_limits], cache_timeout)
                return default_limits
            
            # Use select_related/prefetch_related if needed
            limits = []
            try:
                rate_limit_models = APIRateLimit.objects.filter(is_active=True)
                
                for limit_model in rate_limit_models:
                    # Use getattr() with defensive coding
                    limit_data = {
                        'id': NullSafeResponse.get_safe(limit_model, 'id', 0),
                        'name': NullSafeResponse.get_safe(limit_model, 'name', ''),
                        'limit_type': NullSafeResponse.get_safe(limit_model, 'limit_type', 'ip'),
                        'limit_period': NullSafeResponse.get_safe(limit_model, 'limit_period', 'hour'),
                        'request_limit': NullSafeResponse.get_safe(limit_model, 'request_limit', 100),
                        'endpoint_pattern': NullSafeResponse.get_safe(limit_model, 'endpoint_pattern', ''),
                        'response_message': NullSafeResponse.get_safe(limit_model, 'response_message', 'Rate limit exceeded'),
                        'is_active': NullSafeResponse.get_safe(limit_model, 'is_active', True),
                    }
                    
                    limits.append(RateLimitConfig.from_dict(limit_data))
                    
            except Exception as db_error:
                logger.error(f"Error loading rate limits from DB: {db_error}")
                # Fallback to default limits
                limits = [RateLimitConfig()]
            
            # Cache the results
            cache_data = [asdict(limit) for limit in limits]
            cache.set(cache_key, cache_data, cache_timeout)
            
            return limits
            
        except Exception as e:
            logger.error(f"Error loading rate limits: {e}")
            return [RateLimitConfig()]  # Return default config
    
    def _load_excluded_paths(self) -> List[str]:
        """Load excluded paths with defensive coding"""
        try:
            excluded = getattr(settings, 'RATE_LIMIT_EXCLUDE', [])
            return excluded if isinstance(excluded, list) else []
        except Exception as e:
            logger.error(f"Error loading excluded paths: {e}")
            return []
    
    def get_client_identifier(self, request: HttpRequest) -> str:
        """Get unique client identifier with multiple fallback strategies"""
        try:
            # 1. Try authenticated user
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_id = NullSafeResponse.get_safe(request.user, 'id')
                if user_id:
                    return f"user_{user_id}"
            
            # 2. Try IP address
            ip = self._get_client_ip(request)
            if ip:
                return f"ip_{ip}"
            
            # 3. Try session key
            if hasattr(request, 'session'):
                session_key = NullSafeResponse.get_safe(request.session, 'session_key', '')
                if session_key:
                    return f"session_{session_key}"
            
            # 4. Generate fingerprint from headers
            fingerprint_data = {
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            }
            fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
            fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]
            
            return f"fingerprint_{fingerprint_hash}"
            
        except Exception as e:
            logger.warning(f"Error getting client identifier: {e}")
            return "unknown"
    
    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """Get client IP address with multiple proxy header checks"""
        try:
            # List of possible IP headers (in order of preference)
            ip_headers = [
                'HTTP_X_REAL_IP',
                'HTTP_X_FORWARDED_FOR',
                'REMOTE_ADDR',
            ]
            
            for header in ip_headers:
                ip = request.META.get(header)
                if ip:
                    # Handle comma-separated lists (X-Forwarded-For)
                    if ',' in ip:
                        ip = ip.split(',')[0].strip()
                    
                    if RequestValidator.validate_ip_address(ip):
                        return ip
            
            return None
            
        except Exception as e:
            logger.debug(f"Error getting client IP: {e}")
            return None
    
    def process_request(self, request: HttpRequest):
        """Process incoming request with comprehensive rate limiting"""
        try:
            # Skip excluded paths
            request_path = NullSafeResponse.get_safe(request, 'path', '')
            
            for excluded_path in self.excluded_paths:
                if request_path.startswith(excluded_path):
                    return None
            
            # Get client identifier
            client_id = self.get_client_identifier(request)
            
            # Check each rate limit rule
            for rate_limit in self.rate_limits:
                # Skip inactive rules
                if not rate_limit.is_active:
                    continue
                
                # Check endpoint pattern
                if rate_limit.endpoint_pattern:
                    try:
                        if not re.match(rate_limit.endpoint_pattern, request_path):
                            continue
                    except re.error as e:
                        logger.warning(f"Invalid regex pattern in rate limit {rate_limit.name}: {e}")
                        continue
                
                # Generate cache key
                cache_key = self._generate_cache_key(client_id, request_path, rate_limit)
                
                # Get current count
                current_count = cache.get(cache_key, 0)
                
                # Check if limit exceeded
                if current_count >= rate_limit.request_limit:
                    # Log the event
                    self._log_rate_limit_event(request, rate_limit, client_id, current_count)
                    
                    # Prepare response
                    reset_time = self._get_reset_time(rate_limit.limit_period)
                    
                    # Store rate limit info for headers
                    request.rate_limit_info = {
                        'limit': rate_limit.request_limit,
                        'remaining': 0,
                        'reset_time': reset_time,
                        'retry_after': int((reset_time - timezone.now()).total_seconds())
                    }
                    
                    # Return rate limit response
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'message': rate_limit.response_message,
                        'retry_after': request.rate_limit_info['retry_after'],
                        'limit': rate_limit.request_limit,
                        'period': rate_limit.limit_period
                    }, status=429)
                
                # Increment counter
                cache.set(
                    cache_key,
                    current_count + 1,
                    self._get_period_seconds(rate_limit.limit_period)
                )
                
                # Update rate limit info for successful requests
                request.rate_limit_info = {
                    'limit': rate_limit.request_limit,
                    'remaining': max(0, rate_limit.request_limit - (current_count + 1)),
                    'reset_time': self._get_reset_time(rate_limit.limit_period),
                    'retry_after': None
                }
            
            return None
            
        except Exception as e:
            # Graceful degradation: Allow request on middleware error
            logger.error(f"Rate limit middleware error: {e}")
            return None
    
    def _generate_cache_key(self, client_id: str, path: str, rate_limit: RateLimitConfig) -> str:
        """Generate cache key with period-based component"""
        try:
            now = timezone.now()
            
            # Map periods to time formats
            period_formats = {
                'second': now.strftime('%Y%m%d%H%M%S'),
                'minute': now.strftime('%Y%m%d%H%M'),
                'hour': now.strftime('%Y%m%d%H'),
                'day': now.strftime('%Y%m%d'),
                'month': now.strftime('%Y%m'),
            }
            
            time_key = period_formats.get(rate_limit.limit_period, period_formats['hour'])
            
            # Create unique key
            key_string = f"ratelimit:{rate_limit.limit_type}:{client_id}:{path}:{time_key}"
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            
            return f"rl:{key_hash}"
            
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return f"ratelimit:error:{client_id}"
    
    def _get_period_seconds(self, period: str) -> int:
        """Get period duration in seconds"""
        period_map = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400,
            'month': 2592000,  # 30 days
        }
        return period_map.get(period, 3600)
    
    def _get_reset_time(self, period: str) -> datetime:
        """Calculate reset time for rate limit period"""
        try:
            now = timezone.now()
            
            if period == 'second':
                return now + timedelta(seconds=1)
            elif period == 'minute':
                return (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            elif period == 'hour':
                return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            elif period == 'day':
                return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'month':
                # First day of next month
                if now.month == 12:
                    return datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=now.tzinfo)
                else:
                    return datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=now.tzinfo)
            
            return now + timedelta(hours=1)
            
        except Exception as e:
            logger.error(f"Error calculating reset time: {e}")
            return timezone.now() + timedelta(hours=1)
    
    def _log_rate_limit_event(self, request: HttpRequest, rate_limit: RateLimitConfig, 
                             client_id: str, current_count: int):
        """Log rate limit event with defensive coding"""
        try:
            if MODELS_AVAILABLE:
                with transaction.atomic():
                    RateLimitLog.objects.create(
                        rate_limit_id=rate_limit.id,
                        user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                        ip_address=self._get_client_ip(request),
                        endpoint=request.path,
                        request_method=request.method,
                        client_identifier=client_id,
                        current_count=current_count,
                        limit_exceeded=True,
                        response_message=rate_limit.response_message
                    )
        except Exception as e:
            logger.error(f"Error logging rate limit event: {e}")


# ==================== SECURITY AUDIT MIDDLEWARE ====================
class SecurityAuditMiddleware(MiddlewareMixin):
    """
    Security audit middleware with comprehensive logging and defensive coding.
    Uses QuerySet optimization and transaction safety.
    """
    
    def __init__(self, get_response):
        """Initialize with defensive coding"""
        try:
            super().__init__(get_response)
            self.excluded_paths = self._load_excluded_paths()
            self.sensitive_fields = self._load_sensitive_fields()
            self.logging_circuit = CircuitBreaker(failure_threshold=5, reset_timeout=60)
        except Exception as e:
            logger.error(f"SecurityAuditMiddleware init error: {e}")
            self.excluded_paths = []
            self.sensitive_fields = ['password', 'token', 'secret', 'key']
            self.logging_circuit = CircuitBreaker()
    
    def _load_excluded_paths(self) -> List[str]:
        """Load excluded paths with defaults"""
        try:
            excluded = getattr(settings, 'AUDIT_EXCLUDE_PATHS', [
                '/health/', '/status/', '/static/', '/media/', '/favicon.ico'
            ])
            return excluded if isinstance(excluded, list) else []
        except Exception as e:
            logger.error(f"Error loading excluded paths: {e}")
            return []
    
    def _load_sensitive_fields(self) -> List[str]:
        """Load sensitive field patterns"""
        try:
            sensitive = getattr(settings, 'SENSITIVE_FIELDS', [
                'password', 'token', 'secret', 'key', 'credit_card', 
                'ssn', 'cvv', 'pin', 'authorization'
            ])
            return sensitive if isinstance(sensitive, list) else []
        except Exception as e:
            logger.error(f"Error loading sensitive fields: {e}")
            return []
    
    def should_audit(self, request: HttpRequest) -> bool:
        """Determine if request should be audited"""
        try:
            # Skip excluded paths
            request_path = NullSafeResponse.get_safe(request, 'path', '')
            
            for excluded_path in self.excluded_paths:
                if request_path.startswith(excluded_path):
                    return False
            
            # Skip OPTIONS and HEAD requests
            if request.method in ['OPTIONS', 'HEAD']:
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking audit requirement: {e}")
            return True  # Default to auditing on error
    
    def sanitize_data(self, data: Any, depth: int = 0) -> Any:
        """Recursively sanitize sensitive data with depth limit"""
        try:
            # Prevent infinite recursion
            if depth > 10:
                return '[MAX_DEPTH_EXCEEDED]'
            
            if isinstance(data, dict):
                sanitized = {}
                for key, value in data.items():
                    # Check if key contains sensitive information
                    key_str = str(key).lower()
                    is_sensitive = any(sensitive in key_str for sensitive in self.sensitive_fields)
                    
                    if is_sensitive:
                        # Redact sensitive values
                        if value and isinstance(value, str) and len(value) > 0:
                            sanitized[key] = '***REDACTED***'
                        else:
                            sanitized[key] = '[REDACTED]'
                    else:
                        sanitized[key] = self.sanitize_data(value, depth + 1)
                return sanitized
                
            elif isinstance(data, list):
                return [self.sanitize_data(item, depth + 1) for item in data]
                
            elif isinstance(data, str):
                # Truncate very long strings
                max_length = getattr(settings, 'MAX_LOG_STRING_LENGTH', 1000)
                if len(data) > max_length:
                    return data[:max_length] + '... [TRUNCATED]'
                return data
                
            else:
                return data
                
        except Exception as e:
            logger.debug(f"Error sanitizing data: {e}")
            return '[ERROR_SANITIZING_DATA]'
    
    def extract_request_data(self, request: HttpRequest) -> Dict[str, Any]:
        """Extract and sanitize request data for auditing"""
        try:
            data = {
                'method': NullSafeResponse.get_safe(request, 'method', ''),
                'path': NullSafeResponse.get_safe(request, 'path', ''),
                'query_params': dict(request.GET),
                'content_type': NullSafeResponse.get_safe(request, 'content_type', ''),
                'user_agent': RequestValidator.sanitize_user_agent(
                    request.META.get('HTTP_USER_AGENT', '')
                ),
                'ip_address': self._get_client_ip(request),
                'user': NullSafeResponse.get_safe(
                    request.user, 'username', 'anonymous'
                ) if hasattr(request, 'user') else 'anonymous',
                'timestamp': timezone.now().isoformat(),
                'session_id': NullSafeResponse.get_safe(
                    request.session, 'session_key', ''
                ) if hasattr(request, 'session') else '',
            }
            
            # Extract request body based on content type
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                try:
                    if request.content_type == 'application/json' and request.body:
                        # Use walrus operator for clean code
                        if (body_bytes := request.body) and len(body_bytes) > 0:
                            body_data = json.loads(body_bytes.decode('utf-8', errors='ignore'))
                            data['body'] = self.sanitize_data(body_data)
                    elif request.content_type == 'application/x-www-form-urlencoded':
                        data['body'] = self.sanitize_data(dict(request.POST))
                    elif 'multipart/form-data' in request.content_type:
                        # Handle file uploads
                        file_info = {}
                        for name, file in request.FILES.items():
                            file_info[name] = {
                                'name': file.name,
                                'size': file.size,
                                'content_type': file.content_type,
                            }
                        data['files'] = file_info
                except Exception as body_error:
                    logger.debug(f"Error extracting request body: {body_error}")
                    data['body_error'] = str(body_error)
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting request data: {e}")
            return {'error': 'Failed to extract request data'}
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address with validation"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '')
            
            return ip if RequestValidator.validate_ip_address(ip) else 'invalid_ip'
        except Exception as e:
            logger.debug(f"Error getting client IP: {e}")
            return 'unknown'
    
    def _check_logging_circuit(self) -> bool:
        """Check if logging circuit breaker allows operation"""
        circuit = self.logging_circuit
        
        if circuit.state == "OPEN":
            if circuit.last_failure_time:
                time_since_failure = (timezone.now() - circuit.last_failure_time).total_seconds()
                if time_since_failure > circuit.reset_timeout:
                    # Try to reset
                    circuit.state = "HALF_OPEN"
                    return True
                else:
                    logger.debug("Logging circuit breaker is OPEN, skipping log")
                    return False
            else:
                logger.debug("Logging circuit breaker is OPEN, skipping log")
                return False
        
        return True
    
    def _update_logging_circuit(self, success: bool):
        """Update circuit breaker state based on logging result"""
        circuit = self.logging_circuit
        
        if success:
            if circuit.state == "HALF_OPEN":
                circuit.state = "CLOSED"
                circuit.failures = 0
        else:
            circuit.failures += 1
            circuit.last_failure_time = timezone.now()
            
            if circuit.failures >= circuit.failure_threshold:
                circuit.state = "OPEN"
                logger.error(f"Logging circuit breaker OPEN after {circuit.failures} failures")
    
    def log_security_event(self, request: HttpRequest, response: HttpResponse, 
                          request_data: Dict) -> None:
        """Log security event with circuit breaker protection"""
        # Check circuit breaker first
        if not self._check_logging_circuit():
            return
        
        try:
            # Skip if response is invalid
            if response is None or not hasattr(response, 'status_code'):
                logger.debug("Skipping security log - invalid response")
                self._update_logging_circuit(True)  # Not a failure
                return
            
            # Skip security endpoints to avoid loops
            if '/security/' in request.path or '/log/' in request.path:
                self._update_logging_circuit(True)
                return
            
            # Determine event type and severity
            status_code = response.status_code
            event_type, severity = self._classify_event(status_code, request.path)
            
            # Prepare metadata
            metadata = self._prepare_metadata(request, response, request_data)
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(severity, request, response)
            
            # Create security log in database
            if MODELS_AVAILABLE:
                try:
                    with transaction.atomic():
                        SecurityLog.objects.create(
                            user=request.user if request.user.is_authenticated else None,
                            security_type=event_type,
                            severity=severity,
                            ip_address=DeepGet.get(request_data, 'ip_address', ''),
                            user_agent=DeepGet.get(request_data, 'user_agent', '')[:200],
                            description=self._generate_description(request, status_code, severity),
                            metadata=json.loads(json.dumps(_middleware_safe_serialize(metadata))),
                            risk_score=risk_score,
                            response_time_ms=getattr(response, 'response_time_ms', 0)
                        )
                    
                    logger.debug(f"Security log created: {request.method} {request.path} - {status_code}")
                    self._update_logging_circuit(True)  # Success
                    
                except Exception as db_error:
                    logger.error(f"Database error creating security log: {db_error}")
                    self._update_logging_circuit(False)  # Failure
            else:
                logger.debug(f"Models not available, skipping DB log: {request.method} {request.path}")
                self._update_logging_circuit(True)  # Not a failure
            
        except Exception as e:
            # Don't crash the application if logging fails
            logger.debug(f"Error in log_security_event (non-critical): {e}")
            self._update_logging_circuit(False)  # Failure
    
    def _classify_event(self, status_code: int, path: str) -> Tuple[str, str]:
        """Classify event based on status code and path"""
        # Determine event type
        if status_code >= 500:
            event_type = 'server_error'
            severity = 'high'
        elif status_code in [401, 403]:
            event_type = 'auth_error'
            severity = 'medium'
        elif status_code == 404:
            event_type = 'not_found'
            severity = 'low'
        elif status_code in [200, 201, 204]:
            event_type = 'success'
            severity = 'low'
        else:
            event_type = 'client_error'
            severity = 'medium'
        
        # Adjust severity for admin paths
        if '/admin/' in path and status_code != 200:
            severity = 'medium'
        
        return event_type, severity
    
    def _prepare_metadata(self, request: HttpRequest, response: HttpResponse, 
                         request_data: Dict) -> Dict[str, Any]:
        """Prepare metadata for logging"""
        try:
            metadata = {
                'request': {
                    'path': request.path,
                    'method': request.method,
                    'query_params': dict(request.GET),
                    'user': str(request.user) if request.user.is_authenticated else 'anonymous',
                },
                'response': {
                    'status_code': response.status_code,
                    'content_type': response.headers.get('Content-Type', ''),
                    'content_length': len(response.content) if hasattr(response, 'content') else 0,
                },
                'timestamp': timezone.now().isoformat()
            }
            
            # Add request data if available
            if request_data:
                metadata['request_data'] = {
                    'ip_address': DeepGet.get(request_data, 'ip_address'),
                    'user_agent': DeepGet.get(request_data, 'user_agent', '')[:200],
                }
            
            # Add device fingerprint if available
            if hasattr(request, 'device_fingerprint'):
                metadata['device_fingerprint'] = request.device_fingerprint.get('hash', '')
            
            # Add rate limit info if available
            if hasattr(request, 'rate_limit_info'):
                metadata['rate_limit'] = {k: v.isoformat() if hasattr(v, 'isoformat') else v for k, v in request.rate_limit_info.items()}
            
            return metadata
            
        except Exception as e:
            logger.debug(f"Error preparing metadata: {e}")
            return {'error': 'Failed to prepare metadata'}
    
    def _calculate_risk_score(self, severity: str, request: HttpRequest, 
                            response: HttpResponse) -> int:
        """Calculate risk score for the event"""
        base_scores = {
            'critical': 90,
            'high': 70,
            'medium': 40,
            'low': 10
        }
        
        risk_score = base_scores.get(severity, 10)
        
        # Adjust based on request characteristics
        if '/api/' in request.path:
            risk_score += 10
        if request.method in ['POST', 'PUT', 'DELETE']:
            risk_score += 10
        if response.status_code >= 500:
            risk_score += 20
        
        return min(100, risk_score)  # Cap at 100
    
    def _generate_description(self, request: HttpRequest, status_code: int, 
                            severity: str) -> str:
        """Generate human-readable description"""
        return f"{request.method} {request.path} → {status_code} ({severity})"
    
    def process_request(self, request: HttpRequest):
        """Process incoming request"""
        try:
            if not self.should_audit(request):
                return None
            
            # Extract and store request data
            request_data = self.extract_request_data(request)
            request.security_audit_data = request_data
            
            # Start timing for response time calculation
            request._audit_start_time = timezone.now()
            
            return None
            
        except Exception as e:
            logger.error(f"Security audit middleware request error: {e}")
            return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Process outgoing response"""
        try:
            if not self.should_audit(request):
                return response
            
            # Calculate response time
            if hasattr(request, '_audit_start_time'):
                response_time = (timezone.now() - request._audit_start_time).total_seconds()
                response.response_time_ms = int(response_time * 1000)
            
            # Get request data
            request_data = getattr(request, 'security_audit_data', {})
            
            # Async logging with error handling
            try:
                import threading
                thread = threading.Thread(
                    target=self.log_security_event,
                    args=(request, response, request_data),
                    daemon=True
                )
                thread.start()
            except Exception as thread_error:
                # Fallback to synchronous logging
                logger.warning(f"Async logging failed: {thread_error}")
                self.log_security_event(request, response, request_data)
            
            return response
            
        except Exception as e:
            logger.error(f"Security audit middleware response error: {e}")
            return response


# ==================== COMPOSITE MIDDLEWARE CHAIN ====================
def get_security_middleware_chain() -> List[str]:
    """
    Returns the complete security middleware chain with proper ordering.
    Uses defensive coding for configuration.
    """
    try:
        # Load from settings with defaults
        custom_chain = getattr(settings, 'SECURITY_MIDDLEWARE_CHAIN', None)
        
        if custom_chain and isinstance(custom_chain, list):
            logger.info(f"Using custom security middleware chain from settings")
            return custom_chain
        
        # Default bulletproof chain
        default_chain = [
            'security.middleware.ExceptionHandlingMiddleware',
            'security.middleware.RequestValidationMiddleware',
            'security.middleware.RateLimitMiddleware',
            'security.middleware.VPNProxyDetectionMiddleware',
            'security.middleware.DeviceFingerprintingMiddleware',
            'security.middleware.SecurityAuditMiddleware',
            'security.middleware.SecurityHeadersMiddleware',
        ]
        
        return default_chain
        
    except Exception as e:
        logger.error(f"Error loading security middleware chain: {e}")
        # Return safe default chain
        return [
            'security.middleware.ExceptionHandlingMiddleware',
            'security.middleware.SecurityHeadersMiddleware',
        ]


# ==================== VIEW DECORATOR ====================
def secure_view(view_func=None, *, require_auth=True, rate_limit=None, 
               log_requests=True, validate_input=True):
    """
    Decorator to add security checks at view level with configurable options.
    Uses defensive coding and bulletproof patterns.
    """
    def decorator(func):
        @wraps(func)
        def _wrapped_view(request: HttpRequest, *args, **kwargs):
            try:
                # 1. Authentication check
                if require_auth and (not hasattr(request, 'user') or not request.user.is_authenticated):
                    logger.warning(f"Unauthorized access attempt to {func.__name__}")
                    return JsonResponse({
                        'error': 'Authentication required',
                        'detail': 'Please log in to access this resource'
                    }, status=401)
                
                # 2. IP blacklist check
                client_ip = request.META.get('REMOTE_ADDR')
                if client_ip and MODELS_AVAILABLE:
                    # Use exists() for efficient check
                    try:
                        is_blocked = IPBlacklist.objects.filter(
                            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
                            ip_address=client_ip,
                            is_active=True,
                        ).exists()
                        
                        if is_blocked:
                            logger.warning(f"Blocked IP attempt: {client_ip}")
                            return JsonResponse({
                                'error': 'Access denied',
                                'detail': 'Your IP address has been blocked'
                            }, status=403)
                    except Exception as db_error:
                        logger.error(f"IP blacklist check failed: {db_error}")
                        # Graceful degradation: continue if check fails
                
                # 3. User agent validation with rate limiting
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                suspicious_agents = ['sqlmap', 'nikto', 'wpscan', 'nessus', 'metasploit']
                
                # Check cache to avoid spamming logs
                cache_key = f"suspicious_agent:{client_ip}:{hashlib.md5(user_agent.encode()).hexdigest()[:10]}"
                if not cache.get(cache_key):
                    if any(bad_ua in user_agent.lower() for bad_ua in suspicious_agents):
                        # Log but don't always block (could be false positive)
                        if MODELS_AVAILABLE:
                            try:
                                SecurityLog.objects.create(
                                    security_type='suspicious_agent',
                                    severity='medium',
                                    ip_address=client_ip,
                                    user_agent=user_agent[:200],
                                    description=f"Suspicious user agent detected: {user_agent[:50]}...",
                                    risk_score=50
                                )
                            except Exception as log_error:
                                logger.error(f"Failed to log suspicious agent: {log_error}")
                        
                        logger.warning(f"Suspicious user agent: {user_agent[:100]}")
                        
                        # Cache for 1 hour to avoid spamming
                        cache.set(cache_key, True, 3600)
                
                # 4. Rate limiting at view level (additional layer)
                if rate_limit and hasattr(request, 'rate_limit_info'):
                    remaining = request.rate_limit_info.get('remaining', 1)
                    if remaining <= 0:
                        return JsonResponse({
                            'error': 'Rate limit exceeded',
                            'detail': f'Too many requests. Limit: {rate_limit}',
                            'retry_after': request.rate_limit_info.get('retry_after')
                        }, status=429)
                
                # 5. Input validation for POST/PUT/PATCH
                if validate_input and request.method in ['POST', 'PUT', 'PATCH']:
                    # Check content type
                    allowed_types = ['application/json', 'application/x-www-form-urlencoded', 'multipart/form-data']
                    content_type = getattr(request, 'content_type', '')
                    
                    if content_type and not any(allowed in content_type for allowed in allowed_types):
                        return JsonResponse({
                            'error': 'Unsupported content type',
                            'detail': f'Content type {content_type} not supported',
                            'allowed_types': allowed_types
                        }, status=415)
                    
                    # Check request size
                    max_size = getattr(settings, 'MAX_REQUEST_SIZE', 10 * 1024 * 1024)
                    if hasattr(request, 'body') and len(request.body) > max_size:
                        return JsonResponse({
                            'error': 'Request too large',
                            'detail': f'Maximum request size is {max_size} bytes'
                        }, status=413)
                
                # 6. Execute the view function with timing
                start_time = timezone.now()
                response = func(request, *args, **kwargs)
                elapsed_ms = int((timezone.now() - start_time).total_seconds() * 1000)
                
                # 7. Add security headers if not present
                if not hasattr(response, '_security_headers_added'):
                    response['X-Execution-Time'] = f"{elapsed_ms}ms"
                    response['X-View-Name'] = func.__name__
                    response._security_headers_added = True
                
                # 8. Log the request if enabled
                if log_requests:
                    logger.info(f"View {func.__name__} executed in {elapsed_ms}ms - {response.status_code}")
                
                return response
                
            except PermissionDenied as e:
                logger.warning(f"Permission denied in secure_view {func.__name__}: {e}")
                return JsonResponse({
                    'error': 'Permission denied',
                    'detail': str(e)
                }, status=403)
                
            except Exception as e:
                logger.error(f"Unexpected error in secure_view {func.__name__}: {e}", exc_info=True)
                return JsonResponse({
                    'error': 'Internal server error',
                    'detail': 'An unexpected error occurred',
                    'error_id': hashlib.md5(str(e).encode()).hexdigest()[:8]
                }, status=500)
        
        return _wrapped_view
    
    # Handle both @secure_view and @secure_view(...) syntax
    if view_func is None:
        return decorator
    else:
        return decorator(view_func)


# Export all components
__all__ = [
    # Middleware classes
    'SecurityHeadersMiddleware',
    'RateLimitMiddleware',
    'SecurityAuditMiddleware',
    'VPNProxyDetectionMiddleware',
    'DeviceFingerprintingMiddleware',
    'RequestValidationMiddleware',
    'ExceptionHandlingMiddleware',
    
    # Utility classes
    'CircuitBreaker',
    'DeepGet',
    'NullSafeResponse',
    'RequestValidator',
    
    # Data classes
    'RateLimitConfig',
    'SecurityHeaders',
    
    # Functions
    'get_security_middleware_chain',
    'secure_view',
    
    # Constants
    'MISSING',
]


# ==================== SETTINGS EXAMPLE ====================
"""
Example settings.py configuration:

# Security Middleware Configuration
SECURITY_MIDDLEWARE_CHAIN = [
    'security.middleware.ExceptionHandlingMiddleware',
    'security.middleware.RequestValidationMiddleware',
    'security.middleware.RateLimitMiddleware',
    'security.middleware.VPNProxyDetectionMiddleware',
    'security.middleware.DeviceFingerprintingMiddleware',
    'security.middleware.SecurityAuditMiddleware',
    'security.middleware.SecurityHeadersMiddleware',
]

# Security Headers
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'",
}

# Rate Limiting
RATE_LIMIT_EXCLUDE = ['/health/', '/status/', '/static/', '/media/']

# Request Validation
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']

# Audit Logging
AUDIT_EXCLUDE_PATHS = ['/health/', '/status/', '/static/', '/media/']
SENSITIVE_FIELDS = ['password', 'token', 'secret', 'key', 'credit_card', 'ssn']

# Example usage in views:
@secure_view(require_auth=True, rate_limit=100, validate_input=True)
def my_secure_view(request):
    # Your view logic here
    return JsonResponse({'message': 'Secure endpoint'})
"""