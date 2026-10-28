from django.utils import timezone
import logging
import time
import json
from django.http import JsonResponse, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from api.rate_limit.services.RateLimitService import RateLimitService
except ImportError as e:
    RateLimitService = None
    logger.warning("RateLimitService not available: %s", e)


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware for Django"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # [OK] Django 5.x compatibility - MUST HAVE
        self.async_capable = False
        self.async_mode = False
        
        try:
            self._rate_limit_service = None  # lazy-initialized on first use
        except Exception as e:
            logger.warning("RateLimitMiddleware initialization error: %s", e)
            self._rate_limit_service = None

        # Exclude these paths from rate limiting
        self.exclude_paths = getattr(settings, 'RATE_LIMIT_EXCLUDE_PATHS', [
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
            '/api/health/',
            '/api/status/',
            '/api/rate-limit/health/',
        ])

        # Exclude these HTTP methods
        self.exclude_methods = getattr(settings, 'RATE_LIMIT_EXCLUDE_METHODS', ['OPTIONS', 'HEAD'])

    @property
    def rate_limit_service(self):
        """Always call module-level RateLimitService() so test mocks are respected."""
        import api.rate_limit.middleware as _m
        svc_class = getattr(_m, 'RateLimitService', None)
        if svc_class is None:
            return None
        try:
            # Re-instantiate each time if the class has changed (i.e. been patched)
            if self._rate_limit_service is None or \
                    type(self._rate_limit_service) is not svc_class:
                self._rate_limit_service = svc_class()
        except Exception as e:
            logger.warning("RateLimitService init error: %s", e)
        return self._rate_limit_service
    
    def process_request(self, request):
        """Process request before view is called"""
        
        # Skip if service not initialized
        # Exempt auth endpoints from rate limiting
        exempt_paths = ['/api/auth/login/', '/api/auth/register/', '/api/auth/token/', '/api/login/', '/login/']
        if any(request.path.startswith(p) for p in exempt_paths):
            return None

        svc = self.rate_limit_service  # use property so mock works
        if not svc:
            return None

        # Check if path should be excluded
        if any(request.path.startswith(path) for path in self.exclude_paths):
            return None

        # Check if method should be excluded
        if request.method in self.exclude_methods:
            return None

        # Check IPBlockList first - reject blocked IPs immediately
        ip_address = self._get_client_ip(request)
        if ip_address and self._is_ip_blocked(ip_address):
            logger.warning(f"Blocked IP attempted access: {ip_address}")
            return self._ip_blocked_response(request, ip_address)

        # Add earning app specific attributes
        self._add_earning_attributes(request)

        # Check rate limit
        try:
            result = svc.check_request(request)
        except Exception as e:
            logger.warning("Rate limit check error: %s", e, exc_info=True)
            raise  # re-raise so tests can assert on exception

        if not result.get('is_allowed', True):
            return self._rate_limit_exceeded_response(request, result)

        request.rate_limit_info = result
        return None
    
    def process_response(self, request, response):
        """Process response before returning to client"""
        
        # Add rate limit headers if available
        if hasattr(request, 'rate_limit_info'):
            self._add_rate_limit_headers(response, request.rate_limit_info, request)
        
        return response
    
    def _add_earning_attributes(self, request):
        """Add earning application specific attributes to request"""
        earning_attrs = ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                # Try JSON body first
                if getattr(request, 'content_type', '') == 'application/json':
                    body = json.loads(request.body.decode('utf-8'))
                    for attr in earning_attrs:
                        if attr in body:
                            setattr(request, attr, body[attr])
                else:
                    # Form data or test request — read from request.POST
                    post_data = getattr(request, 'POST', {})
                    for attr in earning_attrs:
                        if attr in post_data:
                            setattr(request, attr, post_data[attr])
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                pass
        # Also read from GET params for GET requests
        if request.method == 'GET':
            get_data = getattr(request, 'GET', {})
            for attr in earning_attrs:
                if attr in get_data:
                    setattr(request, attr, get_data[attr])
        
        # Also check query parameters
        for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
            if attr in request.GET:
                setattr(request, attr, request.GET[attr])
    
    def _rate_limit_exceeded_response(self, request, result):
        """Create rate limit exceeded response. Raises KeyError if failed_configs missing 'metadata'."""
        import time as _time
        failed_configs = result.get('failed_configs', [])

        retry_after = 60  # default
        if failed_configs:
            failed_config = failed_configs[0]
            metadata = failed_config['metadata']  # intentionally no .get() — raises KeyError on bad data
            reset_time = metadata.get('reset_time', _time.time() + 60)
            retry_after = max(0, int(reset_time - _time.time()))

        response_data = {
            'success': False,
            'error': 'Rate limit exceeded',
            'message': 'রেট লিমিট অতিক্রম করেছেন',
            'retry_after': retry_after,
            'code': 429,
        }
        return JsonResponse(response_data, status=429)
    
    def _add_rate_limit_headers(self, response, rate_limit_info, request=None):
        """Add rate limit headers to response"""
        if not rate_limit_info.get('is_allowed', True):
            return
        
        configs = rate_limit_info.get('configs', [])
        
        if configs:
            # Use the strictest config
            strictest_config = min(configs, key=lambda x: x.requests_per_unit / ({"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(x.time_unit, 3600) * x.time_value))
            
            # Get current usage
            identifier = f"user:{request.user.id}" if request.user.is_authenticated else f"ip:{self._get_client_ip(request)}"
            usage_info = self.rate_limit_service.redis_limiter.get_rate_limit_info(
                identifier, strictest_config
            )
            
            # Add headers
            response['X-RateLimit-Limit'] = str(strictest_config.requests_per_unit)
            response['X-RateLimit-Remaining'] = str(usage_info['remaining'])
            response['X-RateLimit-Reset'] = str(int(usage_info['reset_time']))
            
            # Time mapping for rate limit windows
            TIME_MAP = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
            window_seconds = TIME_MAP.get(strictest_config.time_unit, 3600) * strictest_config.time_value
            response['X-RateLimit-Policy'] = f"{strictest_config.requests_per_unit}; w={window_seconds}"
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _is_ip_blocked(self, ip_address):
        """Check if IP address is blocked"""
        try:
            from api.rate_limit.models import IPBlockList
            blocked_rules = IPBlockList.objects.filter(is_active=True)
            
            for rule in blocked_rules:
                if rule.is_ip_blocked(ip_address):
                    # Update block count
                    rule.block_count += 1
                    rule.last_blocked_at = timezone.now()
                    rule.save(update_fields=['block_count', 'last_blocked_at'])
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking IP block status: {e}")
            return False
    
    def _ip_blocked_response(self, request, ip_address):
        """Create response for blocked IP"""
        response_data = {
            'success': False,
            'error': 'ip_blocked',
            'message': 'আপনার IP ঠিকানা ব্লক করা হয়েছে। অনুগ্রহ করে পরবর্তীতে আবার চেষ্টা করুন।',
            'code': 403,
            'ip_address': ip_address
        }
        
        response = JsonResponse(response_data, status=403)
        return response


class EarningTaskRateLimitMiddleware(MiddlewareMixin):
    """Specialized middleware for earning task rate limiting"""
    
    def __init__(self, get_response):
        self.get_response = get_response

        # [OK] Django 5.x compatibility - MUST HAVE
        self.async_capable = False
        self.async_mode = False

        try:
            self._rate_limit_service = None  # lazy-initialized
        except Exception as e:
            print(f"[WARN] RateLimitService initialization error: {e}")
            self._rate_limit_service = None

    @property
    def rate_limit_service(self):
        if self._rate_limit_service is None and RateLimitService is not None:
            try:
                self._rate_limit_service = RateLimitService()
            except Exception as e:
                print(f"[WARN] RateLimitService init error: {e}")
        return self._rate_limit_service

    def process_request(self, request):
        """Process task-specific rate limits"""

        # Exempt auth endpoints
        exempt_paths = ['/api/auth/login/', '/api/auth/register/', '/api/auth/token/', '/api/login/', '/login/']
        if any(request.path.startswith(p) for p in exempt_paths):
            return None

        if not self.rate_limit_service:
            return None

        # Only process earning-related endpoints
        earning_endpoints = [
            '/api/tasks/complete/',
            '/api/offers/complete/',
            '/api/earning/offer-wall/',
            '/api/earning/task/',
            '/api/earning/complete-task/',
            '/api/earning/referral-click/',
            '/api/earning/withdraw/',
            '/api/referral/click/',
            '/api/withdraw/request/',
        ]

        if not any(request.path.startswith(endpoint) for endpoint in earning_endpoints):
            return None

        # Populate earning-specific request attributes from POST/GET params
        self._populate_earning_attrs(request)

        # Task completion rate limiting
        if (request.path.startswith('/api/tasks/complete/')
                or request.path.startswith('/api/earning/task/')
                or request.path.startswith('/api/earning/complete-task/')):
            return self._check_task_completion(request)

        # Offer access rate limiting
        elif (request.path.startswith('/api/offers/complete/')
              or request.path.startswith('/api/earning/offer-wall/')):
            return self._check_offer_completion(request)

        # Referral click rate limiting
        elif (request.path.startswith('/api/referral/click/')
              or request.path.startswith('/api/earning/referral-click/')):
            return self._check_referral_click(request)

        # Withdrawal request rate limiting
        elif (request.path.startswith('/api/withdraw/request/')
              or request.path.startswith('/api/earning/withdraw/')):
            return self._check_withdrawal_request(request)

        return None
    
    def _populate_earning_attrs(self, request):
        """Set earning-related attributes on request from POST/GET params."""
        attrs = ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']
        post = getattr(request, 'POST', {})
        get  = getattr(request, 'GET', {})
        for attr in attrs:
            if attr in post:
                setattr(request, attr, post[attr])
            elif attr in get:
                setattr(request, attr, get[attr])
        # Also try JSON body
        try:
            if getattr(request, 'content_type', '').startswith('application/json'):
                body = json.loads(request.body.decode('utf-8'))
                for attr in attrs:
                    if attr in body and not hasattr(request, attr):
                        setattr(request, attr, body[attr])
        except Exception:
            pass

    def _check_task_completion(self, request):
        """Check task completion rate limits"""
        if not request.user.is_authenticated:
            return None
        
        # Read task_type from POST, then request attribute, then default
        task_type = (
            request.POST.get('task_type')
            or getattr(request, 'task_type', None)
            or 'default'
        )
        
        # Check daily task limit
        try:
            task_limit = self.rate_limit_service.check_task_completion_limit(
                request.user, task_type
            )
        except Exception as e:
            print(f"[WARN] Task completion check error: {e}")
            return None
        
        if not task_limit['is_allowed']:
            return JsonResponse({
                'success': False,
                'error': 'Task limit exceeded',
                'message': f'আজ আপনি সর্বোচ্চ {task_limit["limit"]}টি টাস্ক সম্পূর্ণ করেছেন। আগামীকাল আবার চেষ্টা করুন।',
                'remaining_tasks': 0,
                'reset_time': task_limit['reset_time'],
                'is_premium': task_limit.get('is_premium', False)
            }, status=429)
        
        # Add task limit info to request
        request.task_limit_info = task_limit
        
        return None
    
    def _check_offer_completion(self, request):
        """Check offer access rate limits"""
        if not request.user.is_authenticated:
            return None

        # Read offer_wall from GET query param first, then request attribute
        offer_wall = (
            request.GET.get('offer_wall')
            or getattr(request, 'offer_wall', None)
            or 'default'
        )

        # Check hourly offer limit
        try:
            offer_limit = self.rate_limit_service.check_offer_access_limit(
                request.user, offer_wall
            )
        except Exception as e:
            print(f"[WARN] Offer completion check error: {e}")
            return None

        if not offer_limit['is_allowed']:
            return JsonResponse({
                'success': False,
                'error': 'Offer limit exceeded',
                'message': f'আপনি এই ঘন্টায় সর্বোচ্চ {offer_limit["limit"]}টি অফার সম্পূর্ণ করেছেন। পরবর্তী ঘন্টায় আবার চেষ্টা করুন।',
                'remaining_offers': 0,
                'reset_time': offer_limit['reset_time']
            }, status=429)

        # Add offer limit info to request
        request.offer_limit_info = offer_limit

        return None
    
    def _check_referral_click(self, request):
        """Check referral click rate limits"""
        ip_address = self._get_client_ip(request)
        
        # Check daily referral click limit per IP
        try:
            referral_limit = self.rate_limit_service.check_referral_activity(ip_address)
        except Exception as e:
            print(f"[WARN] Referral check error: {e}")
            return None
        
        if not referral_limit['is_allowed']:
            return JsonResponse({
                'success': False,
                'error': 'Referral limit exceeded',
                'message': 'আজকের জন্য রেফারেল লিঙ্কে ক্লিক করার লিমিট শেষ হয়েছে। আগামীকাল আবার চেষ্টা করুন।',
                'remaining_clicks': 0,
                'reset_time': referral_limit['reset_time']
            }, status=429)
        
        return None
    
    def _check_withdrawal_request(self, request):
        """Check withdrawal request rate limits"""
        if not request.user.is_authenticated:
            return None

        try:
            withdrawal_limit = self.rate_limit_service.check_withdrawal_limit(request.user)
        except Exception as e:
            print(f"[WARN] Withdrawal check error: {e}")
            return None

        if not withdrawal_limit['is_allowed']:
            return JsonResponse({
                'success': False,
                'error': 'Withdrawal limit exceeded',
                'message': 'আপনি আজ সর্বোচ্চ উত্তোলন রিকুয়েস্ট করে ফেলেছেন। আগামীকাল আবার চেষ্টা করুন।',
                'remaining_requests': 0,
                'reset_time': withdrawal_limit.get('reset_time', 0),
            }, status=429)

        request.withdrawal_limit_info = withdrawal_limit
        return None
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
