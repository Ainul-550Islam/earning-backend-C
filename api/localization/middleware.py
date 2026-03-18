# middleware.py
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import activate, get_language
from django.urls import resolve, Resolver404
import logging
import re
import json
from typing import Optional, Dict, Any, Callable, Union
from datetime import datetime, timedelta
from .models import Language, MissingTranslation
from .services_loca import (
    TranslationService, 
    LocalizationService, 
    LanguageDetector,
    translation_service, 
    localization_service, 
    language_detector,
    user_preference_service  
)

logger = logging.getLogger(__name__)

# ======================== Constants ========================
LANGUAGE_COOKIE_NAME = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
LANGUAGE_COOKIE_AGE = getattr(settings, 'LANGUAGE_COOKIE_AGE', 60 * 60 * 24 * 365)  # 1 year
LANGUAGE_COOKIE_PATH = getattr(settings, 'LANGUAGE_COOKIE_PATH', '/')
LANGUAGE_COOKIE_DOMAIN = getattr(settings, 'LANGUAGE_COOKIE_DOMAIN', None)
LANGUAGE_COOKIE_SECURE = getattr(settings, 'LANGUAGE_COOKIE_SECURE', False)
LANGUAGE_COOKIE_HTTPONLY = getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False)
LANGUAGE_COOKIE_SAMESITE = getattr(settings, 'LANGUAGE_COOKIE_SAMESITE', 'Lax')

RATE_LIMIT_ENABLED = getattr(settings, 'RATE_LIMIT_ENABLED', True)
RATE_LIMIT_REQUESTS = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
RATE_LIMIT_PERIOD = getattr(settings, 'RATE_LIMIT_PERIOD', 60)  # seconds


# ======================== Base Middleware ========================

class BaseMiddleware(MiddlewareMixin):
    """Base middleware with common functionality"""
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest):
        """Process request - override in subclasses"""
        pass
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Process response - override in subclasses"""
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception):
        """Handle exceptions - override in subclasses"""
        logger.error(f"Middleware exception: {exception}", exc_info=True)
        return None
    
    def get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
    def is_ajax_request(self, request: HttpRequest) -> bool:
        """Check if request is AJAX"""
        return request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    def is_api_request(self, request: HttpRequest) -> bool:
        """Check if request is API request"""
        return request.path.startswith('/api/')

# ======================== Timezone Middleware ========================

class TimezoneMiddleware(BaseMiddleware):
    """
    Middleware for handling user timezone
    Sets timezone based on user preference, IP geolocation, or default
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.default_timezone = getattr(settings, 'TIME_ZONE', 'UTC')
    
    def _get_timezone_from_ip(self, ip: str) -> Optional[str]:
        """Get timezone from IP address using geoip"""
        # This would integrate with GeoIP
        # For now, return None (implement based on your GeoIP setup)
        return None
    
    def _get_timezone_from_user(self, request: HttpRequest) -> Optional[str]:
        """Get timezone from user preferences"""
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                if hasattr(request.user, 'timezone'):
                    return request.user.timezone
                
                # Try to get from user's country
                if hasattr(request.user, 'country') and request.user.country:
                    return request.user.country.default_timezone
        except Exception as e:
            logger.error(f"Error getting user timezone: {e}")
        
        return None
    
    def _get_timezone_from_session(self, request: HttpRequest) -> Optional[str]:
        """Get timezone from session"""
        return request.session.get('django_timezone')
    
    def _get_timezone_from_cookie(self, request: HttpRequest) -> Optional[str]:
        """Get timezone from cookie"""
        return request.COOKIES.get('django_timezone')
    
    def _set_timezone(self, request: HttpRequest, timezone_name: str):
        """Set timezone for the request"""
        try:
            import pytz
            pytz.timezone(timezone_name)  # Validate timezone
            timezone.activate(timezone_name)
            request.timezone = timezone_name
            logger.debug(f"Timezone set to: {timezone_name}")
        except Exception as e:
            logger.error(f"Invalid timezone {timezone_name}: {e}")
            timezone.deactivate()
            request.timezone = self.default_timezone
    
    def process_request(self, request: HttpRequest):
        """Set timezone for the request"""
        try:
            timezone_name = None
            
            # Try user preference
            timezone_name = self._get_timezone_from_user(request)
            
            # Try session
            if not timezone_name:
                timezone_name = self._get_timezone_from_session(request)
            
            # Try cookie
            if not timezone_name:
                timezone_name = self._get_timezone_from_cookie(request)
            
            # Try IP geolocation
            if not timezone_name:
                ip = self.get_client_ip(request)
                timezone_name = self._get_timezone_from_ip(ip)
            
            # Use default
            if not timezone_name:
                timezone_name = self.default_timezone
            
            # Set timezone
            self._set_timezone(request, timezone_name)
            
        except Exception as e:
            logger.error(f"Timezone middleware error: {e}")
            timezone.deactivate()
            request.timezone = self.default_timezone


# ======================== Currency Middleware ========================

class CurrencyMiddleware(BaseMiddleware):
    """
    Middleware for handling user currency preference
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.default_currency = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
    
    def _get_currency_from_user(self, request: HttpRequest) -> Optional[str]:
        """Get currency from user preferences"""
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                if hasattr(request.user, 'currency'):
                    return request.user.currency
                
                # Try to get from user's country
                if hasattr(request.user, 'country') and request.user.country:
                    return request.user.country.default_currency
        except Exception as e:
            logger.error(f"Error getting user currency: {e}")
        
        return None
    
    def _get_currency_from_session(self, request: HttpRequest) -> Optional[str]:
        """Get currency from session"""
        return request.session.get('currency')
    
    def _get_currency_from_cookie(self, request: HttpRequest) -> Optional[str]:
        """Get currency from cookie"""
        return request.COOKIES.get('currency')
    
    def _get_currency_from_ip(self, ip: str) -> Optional[str]:
        """Get currency from IP geolocation"""
        # This would integrate with GeoIP
        # For now, return None
        return None
    
    def _set_currency_cookie(self, response: HttpResponse, currency: str):
        """Set currency cookie"""
        try:
            response.set_cookie(
                'currency',
                currency,
                max_age=60 * 60 * 24 * 365,  # 1 year
                path='/',
                secure=settings.SESSION_COOKIE_SECURE,
                httponly=False,  # Allow JavaScript access
                samesite='Lax',
            )
        except Exception as e:
            logger.error(f"Error setting currency cookie: {e}")
    
    def process_request(self, request: HttpRequest):
        """Set currency for the request"""
        try:
            currency_code = None
            
            # Try user preference
            currency_code = self._get_currency_from_user(request)
            
            # Try session
            if not currency_code:
                currency_code = self._get_currency_from_session(request)
            
            # Try cookie
            if not currency_code:
                currency_code = self._get_currency_from_cookie(request)
            
            # Try IP geolocation
            if not currency_code:
                ip = self.get_client_ip(request)
                currency_code = self._get_currency_from_ip(ip)
            
            # Use default
            if not currency_code:
                currency_code = self.default_currency
            
            # Set request attribute
            request.currency = currency_code
            
        except Exception as e:
            logger.error(f"Currency middleware error: {e}")
            request.currency = self.default_currency
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Set currency cookie if needed"""
        try:
            if hasattr(request, 'currency') and request.currency:
                # Check if cookie needs update
                cookie_currency = request.COOKIES.get('currency')
                if cookie_currency != request.currency:
                    self._set_currency_cookie(response, request.currency)
        except Exception as e:
            logger.error(f"Error setting currency cookie: {e}")
        
        return response


# ======================== Rate Limit Middleware ========================

class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware for rate limiting API requests
    Uses IP-based rate limiting
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.enabled = RATE_LIMIT_ENABLED
        self.requests_limit = RATE_LIMIT_REQUESTS
        self.period = RATE_LIMIT_PERIOD
    
    def _get_rate_limit_key(self, request: HttpRequest) -> str:
        """Get rate limit cache key for request"""
        ip = self.get_client_ip(request)
        
        # Different keys for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"rate_limit:user:{request.user.id}"
        
        return f"rate_limit:ip:{ip}"
    
    def _check_rate_limit(self, key: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit
        Returns (is_allowed, headers)
        """
        try:
            # Get current count
            current = cache.get(key, 0)
            
            # Calculate remaining
            remaining = max(0, self.requests_limit - current)
            
            headers = {
                'X-RateLimit-Limit': str(self.requests_limit),
                'X-RateLimit-Remaining': str(remaining),
                'X-RateLimit-Reset': str(int(timezone.now().timestamp()) + self.period),
            }
            
            if current >= self.requests_limit:
                return False, headers
            
            # Increment count
            if current == 0:
                cache.set(key, 1, self.period)
            else:
                cache.incr(key)
            
            return True, headers
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow request but log
            return True, {}
    
    def process_request(self, request: HttpRequest):
        """Check rate limit for request"""
        if not self.enabled:
            return None
        
        # Only rate limit API requests
        if not self.is_api_request(request):
            return None
        
        key = self._get_rate_limit_key(request)
        allowed, headers = self._check_rate_limit(key)
        
        # Store headers in request for response
        request.rate_limit_headers = headers
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {key}")
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Rate limit exceeded. Please try again later.',
                    'code': 'rate_limit_exceeded',
                    'retry_after': self.period,
                },
                status=429,
                headers={
                    'Retry-After': str(self.period),
                    **headers
                }
            )
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Add rate limit headers to response"""
        if hasattr(request, 'rate_limit_headers'):
            for key, value in request.rate_limit_headers.items():
                response[key] = value
        
        return response


# ======================== Translation Middleware ========================

class TranslationMiddleware(BaseMiddleware):
    """
    Middleware for handling translation-related tasks
    - Logs missing translations
    - Adds translation context to response
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.log_missing_translations = getattr(settings, 'LOG_MISSING_TRANSLATIONS', True)
    
    def process_request(self, request: HttpRequest):
        """Initialize translation context"""
        request.translation_context = {}
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Process translation-related tasks"""
        try:
            # Log missing translations for API requests
            if self.log_missing_translations and self.is_api_request(request):
                self._log_missing_translations(request, response)
            
            # Add translation info header for debugging
            if settings.DEBUG and hasattr(request, 'LANGUAGE_CODE'):
                response['X-Language'] = request.LANGUAGE_CODE
            
        except Exception as e:
            logger.error(f"Translation middleware error: {e}")
        
        return response
    
    def _log_missing_translations(self, request: HttpRequest, response: HttpResponse):
        """Log missing translations from request"""
        # This would need to be implemented based on how you track missing translations
        # For now, it's a placeholder
        pass


# ======================== Device Detection Middleware ========================

class DeviceDetectionMiddleware(BaseMiddleware):
    """
    Middleware for detecting device type and capabilities
    Useful for responsive design and feature detection
    """
    
    MOBILE_USER_AGENTS = re.compile(
        r'android|blackberry|iphone|ipod|iemobile|opera mobile|palmos|webos|googlebot-mobile',
        re.IGNORECASE
    )
    
    TABLET_USER_AGENTS = re.compile(
        r'ipad|android 3|tablet|kindle|silk',
        re.IGNORECASE
    )
    
    def _detect_device(self, request: HttpRequest) -> Dict[str, Any]:
        """Detect device type and capabilities"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        device_info = {
            'is_mobile': bool(self.MOBILE_USER_AGENTS.search(user_agent)),
            'is_tablet': bool(self.TABLET_USER_AGENTS.search(user_agent)),
            'is_desktop': True,
            'is_bot': 'bot' in user_agent or 'crawler' in user_agent,
            'user_agent': user_agent[:255],  # Truncate for safety
        }
        
        # Tablet overrides mobile
        if device_info['is_tablet']:
            device_info['is_mobile'] = False
        
        # Desktop if not mobile or tablet
        device_info['is_desktop'] = not (device_info['is_mobile'] or device_info['is_tablet'])
        
        return device_info
    
    def process_request(self, request: HttpRequest):
        """Detect device and add to request"""
        try:
            request.device = self._detect_device(request)
            logger.debug(f"Device detected: {request.device}")
        except Exception as e:
            logger.error(f"Device detection error: {e}")
            request.device = {'is_desktop': True, 'is_mobile': False, 'is_tablet': False}


# ======================== Performance Monitoring Middleware ========================

class PerformanceMiddleware(BaseMiddleware):
    """
    Middleware for monitoring request performance
    Logs slow requests and adds performance headers
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.slow_threshold = getattr(settings, 'SLOW_REQUEST_THRESHOLD', 1.0)  # seconds
    
    def process_request(self, request: HttpRequest):
        """Start timing the request"""
        request.start_time = timezone.now()
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Calculate and log request duration"""
        try:
            if hasattr(request, 'start_time'):
                duration = (timezone.now() - request.start_time).total_seconds()
                
                # Add performance header
                response['X-Request-Duration'] = f"{duration:.3f}s"
                
                # Log slow requests
                if duration > self.slow_threshold:
                    logger.warning(
                        f"Slow request detected: {request.path} "
                        f"took {duration:.3f}s "
                        f"(threshold: {self.slow_threshold}s)"
                    )
                    
                    # Could send to monitoring service here
                    
        except Exception as e:
            logger.error(f"Performance monitoring error: {e}")
        
        return response


# ======================== Security Headers Middleware ========================

class SecurityHeadersMiddleware(BaseMiddleware):
    """
    Middleware for adding security headers to responses
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Add security headers"""
        try:
            # Content Security Policy
            if not response.has_header('Content-Security-Policy'):
                response['Content-Security-Policy'] = (
                    "default-src 'self' cdn.jsdelivr.net; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net; "
                    "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                    "img-src 'self' cdn.jsdelivr.net data:;"
                )
            
            # X-Content-Type-Options
            if not response.has_header('X-Content-Type-Options'):
                response['X-Content-Type-Options'] = 'nosniff'
            
            # X-Frame-Options
            if not response.has_header('X-Frame-Options'):
                response['X-Frame-Options'] = 'DENY'
            
            # X-XSS-Protection
            if not response.has_header('X-XSS-Protection'):
                response['X-XSS-Protection'] = '1; mode=block'
            
            # Referrer-Policy
            if not response.has_header('Referrer-Policy'):
                response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Permissions-Policy
            if not response.has_header('Permissions-Policy'):
                response['Permissions-Policy'] = (
                    "geolocation=(), microphone=(), camera=()"
                )
            
        except Exception as e:
            logger.error(f"Security headers error: {e}")
        
        return response


# ======================== Cache Headers Middleware ========================

class CacheHeadersMiddleware(BaseMiddleware):
    """
    Middleware for adding cache control headers
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.cache_timeout = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', 600)
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Add cache headers based on request type"""
        try:
            # Don't cache authenticated requests by default
            if hasattr(request, 'user') and request.user.is_authenticated:
                response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                return response
            
            # Cache public API responses
            if self.is_api_request(request) and request.method == 'GET':
                if not response.has_header('Cache-Control'):
                    response['Cache-Control'] = f'public, max-age={self.cache_timeout}'
            
            # Cache static files
            if request.path.startswith('/static/') or request.path.startswith('/media/'):
                if not response.has_header('Cache-Control'):
                    response['Cache-Control'] = f'public, max-age={self.cache_timeout * 24}'
            
        except Exception as e:
            logger.error(f"Cache headers error: {e}")
        
        return response


# ======================== Maintenance Mode Middleware ========================

class MaintenanceModeMiddleware(BaseMiddleware):
    """
    Middleware for handling maintenance mode
    Shows maintenance page when enabled
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
        self.allowed_ips = getattr(settings, 'MAINTENANCE_ALLOWED_IPS', [])
        self.allowed_paths = getattr(settings, 'MAINTENANCE_ALLOWED_PATHS', [
            '/admin/',
            '/api/health/',
            '/static/',
        ])
    
    def _is_allowed(self, request: HttpRequest) -> bool:
        """Check if request should bypass maintenance mode"""
        # Check IP
        ip = self.get_client_ip(request)
        if ip in self.allowed_ips:
            return True
        
        # Check path
        path = request.path_info
        for allowed_path in self.allowed_paths:
            if path.startswith(allowed_path):
                return True
        
        # Check superuser
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
            return True
        
        return False
    
    def process_request(self, request: HttpRequest):
        """Check maintenance mode"""
        if self.maintenance_mode and not self._is_allowed(request):
            logger.info(f"Maintenance mode active, blocking request from {self.get_client_ip(request)}")
            
            if self.is_api_request(request):
                return JsonResponse(
                    {
                        'success': False,
                        'error': 'Service temporarily unavailable due to maintenance',
                        'code': 'maintenance_mode',
                        'retry_after': 3600,
                    },
                    status=503,
                    headers={'Retry-After': '3600'}
                )
            
            # Return maintenance HTML page
            from django.shortcuts import render
            return render(request, '503.html', status=503)
        
        return None


# ======================== Request Logging Middleware ========================

class RequestLoggingMiddleware(BaseMiddleware):
    """
    Middleware for logging all requests
    Useful for debugging and analytics
    """
    
    def process_request(self, request: HttpRequest):
        """Log request details"""
        request.request_id = self._generate_request_id()
        
        logger.info(
            f"Request {request.request_id}: {request.method} {request.path} "
            f"from {self.get_client_ip(request)}"
        )
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Log response details"""
        if hasattr(request, 'request_id'):
            duration = 'N/A'
            if hasattr(request, 'start_time'):
                duration = f"{(timezone.now() - request.start_time).total_seconds():.3f}s"
            
            logger.info(
                f"Response {request.request_id}: {response.status_code} "
                f"({duration})"
            )
            
            # Add request ID to response
            response['X-Request-ID'] = request.request_id
        
        return response
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        import uuid
        return str(uuid.uuid4())[:8]


# ======================== CORS Middleware ========================

class CORSMiddleware(BaseMiddleware):
    """
    Middleware for handling CORS headers
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        self.allowed_methods = getattr(settings, 'CORS_ALLOWED_METHODS', [
            'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'
        ])
        self.allowed_headers = getattr(settings, 'CORS_ALLOWED_HEADERS', [
            'Accept',
            'Accept-Language',
            'Content-Language',
            'Content-Type',
            'Authorization',
            'X-Requested-With',
            'X-CSRFToken',
        ])
    
    def _get_origin(self, request: HttpRequest) -> Optional[str]:
        """Get origin from request"""
        return request.META.get('HTTP_ORIGIN')
    
    def _is_allowed_origin(self, origin: str) -> bool:
        """Check if origin is allowed"""
        if not origin:
            return False
        
        if '*' in self.allowed_origins:
            return True
        
        return origin in self.allowed_origins
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Add CORS headers"""
        try:
            origin = self._get_origin(request)
            
            if origin and self._is_allowed_origin(origin):
                response['Access-Control-Allow-Origin'] = origin
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Allow-Methods'] = ', '.join(self.allowed_methods)
                response['Access-Control-Allow-Headers'] = ', '.join(self.allowed_headers)
                response['Access-Control-Max-Age'] = '86400'  # 24 hours
            
            # Handle preflight requests
            if request.method == 'OPTIONS':
                response.status_code = 200
            
        except Exception as e:
            logger.error(f"CORS error: {e}")
        
        return response


# ======================== Content Compression Middleware ========================

class ContentCompressionMiddleware(BaseMiddleware):
    """
    Middleware for compressing response content
    Supports gzip and brotli compression
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.min_length = getattr(settings, 'COMPRESS_MIN_LENGTH', 500)
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Compress response if applicable"""
        try:
            # Skip if already encoded
            if response.has_header('Content-Encoding'):
                return response
            
            # Skip for small responses
            if len(response.content) < self.min_length:
                return response
            
            # Check if client accepts gzip
            accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
            
            if 'gzip' in accept_encoding:
                import gzip
                
                compressed = gzip.compress(response.content)
                response.content = compressed
                response['Content-Encoding'] = 'gzip'
                response['Content-Length'] = str(len(compressed))
                response['Vary'] = 'Accept-Encoding'
            
            # Brotli compression could be added here
            
        except Exception as e:
            logger.error(f"Compression error: {e}")
        
        return response


class LanguageMiddleware(BaseMiddleware):
    """
    Middleware for handling language selection and activation
    Priority: 1. URL prefix, 2. User preference, 3. Session, 4. Cookie, 5. Header, 6. Default
    """
    
    def __init__(self, get_response: Callable):
        super().__init__(get_response)
        self.supported_languages = self._get_supported_languages()
        self.default_language = self._get_default_language()
    
    def _get_supported_languages(self) -> Dict[str, str]:
        """Get supported languages from database with caching"""
        try:
            cache_key = 'supported_languages_dict'
            languages = cache.get(cache_key)
            
            if not languages:
                languages = dict(Language.objects.filter(
                    is_active=True
                ).values_list('code', 'name'))
                cache.set(cache_key, languages, 3600)
            
            return languages or {'en': 'English'}  # Fallback
        except Exception as e:
            logger.error(f"Error getting supported languages: {e}")
            # Fallback to settings
            return dict(getattr(settings, 'LANGUAGES', [('en', 'English')]))
    
    def _get_default_language(self) -> str:
        """Get default language code"""
        try:
            default = Language.objects.filter(is_default=True).first()
            return getattr(default, 'code', settings.LANGUAGE_CODE)
        except Exception:
            return getattr(settings, 'LANGUAGE_CODE', 'en')
    
    def _extract_language_from_request(self, request: HttpRequest) -> Optional[str]:
        """Extract language from various sources"""
        
        # 1. Check URL prefix (for i18n_patterns)
        try:
            resolver_match = resolve(request.path_info)
            lang_code = getattr(resolver_match, 'kwargs', {}).get('language')
            if lang_code and lang_code in self.supported_languages:
                return lang_code
        except Resolver404:
            pass
        except Exception as e:
            logger.debug(f"URL language extraction error: {e}")
        
        # 2. Check user preference - FIXED VERSION
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                pref = user_preference_service.get_user_preference(request.user)
                if pref and hasattr(pref, 'ui_language'):
                    # Handle both string and object
                    ui_lang = pref.ui_language
                    
                    # Case 1: It's a Language object with code attribute
                    if hasattr(ui_lang, 'code'):
                        lang_code = ui_lang.code
                    # Case 2: It's a string
                    elif isinstance(ui_lang, str):
                        lang_code = ui_lang
                    # Case 3: Unknown type
                    else:
                        lang_code = str(ui_lang)
                    
                    if lang_code in self.supported_languages:
                        return lang_code
            except Exception as e:
                logger.error(f"Error getting user language preference: {e}")
        
        # 3. Check session
        try:
            session_lang = request.session.get(LANGUAGE_COOKIE_NAME)
            if session_lang and session_lang in self.supported_languages:
                return session_lang
        except Exception:
            pass
        
        # 4. Check cookie
        try:
            cookie_lang = request.COOKIES.get(LANGUAGE_COOKIE_NAME)
            if cookie_lang and cookie_lang in self.supported_languages:
                return cookie_lang
        except Exception:
            pass
        
        # 5. Check Accept-Language header
        try:
            accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
            if accept_language:
                # Parse Accept-Language header
                languages = re.findall(r'([a-z]{2})(?:-[A-Z]{2})?(?:;q=[0-9.]+)?', accept_language)
                for lang in languages:
                    if lang in self.supported_languages:
                        return lang
        except Exception as e:
            logger.debug(f"Accept-Language parsing error: {e}")
        
        # 6. Return default
        return self.default_language
    
    def process_request(self, request: HttpRequest):
        """Set language for the request with defensive coding"""
        try:
            # Get language using defensive method
            language_code = self._extract_language_from_request(request)
            
            # Validate language code
            if language_code and language_code in self.supported_languages:
                # Activate language
                activate(language_code)
                request.LANGUAGE_CODE = language_code
                
                # Store in session (if session exists)
                try:
                    request.session[LANGUAGE_COOKIE_NAME] = language_code
                except Exception:
                    pass
                
                logger.debug(f"Language set to: {language_code}")
            else:
                # Fallback to default
                self._set_default_language(request)
            
        except Exception as e:
            logger.error(f"Language middleware error: {e}")
            # Fallback to default
            self._set_default_language(request)
    
    def _set_default_language(self, request: HttpRequest):
        """Set default language safely"""
        try:
            activate(self.default_language)
            request.LANGUAGE_CODE = self.default_language
        except Exception:
            # Ultimate fallback
            activate('en')
            request.LANGUAGE_CODE = 'en'
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Set language cookie in response with defensive coding"""
        try:
            if hasattr(request, 'LANGUAGE_CODE'):
                language = request.LANGUAGE_CODE
                
                # Set cookie if not already set
                current_cookie = request.COOKIES.get(LANGUAGE_COOKIE_NAME)
                if language and current_cookie != language:
                    try:
                        response.set_cookie(
                            LANGUAGE_COOKIE_NAME,
                            language,
                            max_age=LANGUAGE_COOKIE_AGE,
                            path=LANGUAGE_COOKIE_PATH,
                            domain=LANGUAGE_COOKIE_DOMAIN,
                            secure=LANGUAGE_COOKIE_SECURE,
                            httponly=LANGUAGE_COOKIE_HTTPONLY,
                            samesite=LANGUAGE_COOKIE_SAMESITE,
                        )
                        logger.debug(f"Language cookie set to: {language}")
                    except Exception as e:
                        logger.error(f"Error setting language cookie: {e}")
            
            # Add language header for debugging
            if settings.DEBUG and hasattr(request, 'LANGUAGE_CODE'):
                response['X-Language'] = request.LANGUAGE_CODE
                
        except Exception as e:
            logger.error(f"Error in process_response: {e}")
        
        return response



# ======================== Middleware Configuration ========================

class LocalizationMiddleware:
    """
    Combined middleware for localization features
    This can be used as a single middleware in settings
    """
    
    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.language_middleware = LanguageMiddleware(get_response)
        self.timezone_middleware = TimezoneMiddleware(get_response)
        self.currency_middleware = CurrencyMiddleware(get_response)
        self.rate_limit_middleware = RateLimitMiddleware(get_response)
        self.performance_middleware = PerformanceMiddleware(get_response)
        self.security_middleware = SecurityHeadersMiddleware(get_response)
        self.cors_middleware = CORSMiddleware(get_response)
    
    def __call__(self, request: HttpRequest):
        # Process request through all middlewares
        response = self.language_middleware.process_request(request)
        if response:
            return response
        
        response = self.timezone_middleware.process_request(request)
        if response:
            return response
        
        response = self.currency_middleware.process_request(request)
        if response:
            return response
        
        response = self.rate_limit_middleware.process_request(request)
        if response:
            return response
        
        self.performance_middleware.process_request(request)
        
        # Get response from view
        response = self.get_response(request)
        
        # Process response through all middlewares
        response = self.security_middleware.process_response(request, response)
        response = self.cors_middleware.process_response(request, response)
        response = self.language_middleware.process_response(request, response)
        response = self.currency_middleware.process_response(request, response)
        response = self.rate_limit_middleware.process_response(request, response)
        response = self.performance_middleware.process_response(request, response)
        
        return response