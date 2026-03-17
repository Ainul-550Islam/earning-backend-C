import logging
import time
import json
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from .services.RateLimitService import RateLimitService
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
            self.rate_limit_service = RateLimitService() if RateLimitService else None
        except Exception as e:
            logger.warning("RateLimitService initialization error: %s", e)
            self.rate_limit_service = None

        # Exclude these paths from rate limiting
        self.exclude_paths = getattr(settings, 'RATE_LIMIT_EXCLUDE_PATHS', [
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
            '/api/rate-limit/health/'
        ])
        
        # Exclude these HTTP methods
        self.exclude_methods = getattr(settings, 'RATE_LIMIT_EXCLUDE_METHODS', ['OPTIONS'])
    
    def process_request(self, request):
        """Process request before view is called"""
        
        # Skip if service not initialized
        # Exempt auth endpoints from rate limiting
        exempt_paths = ['/api/auth/login/', '/api/auth/register/', '/api/auth/token/', '/api/login/', '/login/']
        if any(request.path.startswith(p) for p in exempt_paths):
            return self.get_response(request)

        if not self.rate_limit_service:
            return None
        
        # Check if path should be excluded
        if any(request.path.startswith(path) for path in self.exclude_paths):
            return None
        
        # Check if method should be excluded
        if request.method in self.exclude_methods:
            return None
        
        # Add earning app specific attributes
        self._add_earning_attributes(request)
        
        # Check rate limit
        try:
            result = self.rate_limit_service.check_request(request)
        except Exception as e:
            logger.warning("Rate limit check error (allowing request): %s", e, exc_info=True)
            return None

        if not result.get('is_allowed', True):
            # Rate limit exceeded
            return self._rate_limit_exceeded_response(request, result)
        
        # Add rate limit headers to request for use in views
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
        # Parse request body for task/offer data
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if request.content_type == 'application/json':
                    body = json.loads(request.body.decode('utf-8'))
                    
                    # Extract earning app specific data
                    for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
                        if attr in body:
                            setattr(request, attr, body[attr])
                            
                elif request.content_type in ['application/x-www-form-urlencoded', 'multipart/form-data']:
                    # Handle form data
                    for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
                        if attr in request.POST:
                            setattr(request, attr, request.POST[attr])
                            
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        # Also check query parameters
        for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
            if attr in request.GET:
                setattr(request, attr, request.GET[attr])
    
    def _rate_limit_exceeded_response(self, request, result):
        """Create rate limit exceeded response"""
        failed_configs = result['failed_configs']
        
        if failed_configs:
            failed_config = failed_configs[0]
            config = failed_config['config']
            metadata = failed_config['metadata']
            
            # Custom response for earning app
            if hasattr(request, 'task_id'):
                message = "টাস্ক সম্পূর্ণ করার লিমিট শেষ হয়েছে। আগামীকাল আবার চেষ্টা করুন।"
            elif hasattr(request, 'offer_id'):
                message = "অফার সম্পূর্ণ করার লিমিট শেষ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।"
            elif hasattr(request, 'referral_code'):
                message = "রেফারেল লিঙ্কে খুব বেশি ক্লিক করা হয়েছে। আগামীকাল আবার চেষ্টা করুন।"
            else:
                message = f"রেট লিমিট অতিক্রম করেছেন। {config.requests_per_unit} অনুরোধ প্রতি {config.time_value} {config.time_unit}"
            
            response_data = {
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': message,
                'code': 429,
                'details': {
                    'limit': config.requests_per_unit,
                    'time_unit': config.time_unit,
                    'time_value': config.time_value,
                    'current': metadata.get('current_count', 0),
                    'remaining': metadata.get('remaining', 0),
                    'reset_time': int(metadata.get('reset_time', time.time()))
                },
                'config_name': config.name
            }
        else:
            response_data = {
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': 'রেট লিমিট অতিক্রম করেছেন',
                'code': 429
            }
        
        response = JsonResponse(response_data, status=429)
        
        # Add Retry-After header
        if failed_configs and 'reset_time' in failed_configs[0]['metadata']:
            reset_time = failed_configs[0]['metadata']['reset_time']
            retry_after = max(0, int(reset_time - time.time()))
            response['Retry-After'] = str(retry_after)
        
        return response
    
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
            response['X-RateLimit-Policy'] = f"{strictest_config.requests_per_unit}; w={({"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(strictest_config.time_unit, 3600) * strictest_config.time_value)}"
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class EarningTaskRateLimitMiddleware(MiddlewareMixin):
    """Specialized middleware for earning task rate limiting"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # [OK] Django 5.x compatibility - MUST HAVE
        self.async_capable = False
        self.async_mode = False
        
        try:
            self.rate_limit_service = RateLimitService()
        except Exception as e:
            print(f"[WARN] RateLimitService initialization error: {e}")
            self.rate_limit_service = None
    
    def process_request(self, request):
        """Process task-specific rate limits"""
        
        # Skip if service not initialized
        # Exempt auth endpoints from rate limiting
        exempt_paths = ['/api/auth/login/', '/api/auth/register/', '/api/auth/token/', '/api/login/', '/login/']
        if any(request.path.startswith(p) for p in exempt_paths):
            return self.get_response(request)

        if not self.rate_limit_service:
            return None
        
        # Only process earning-related endpoints
        earning_endpoints = [
            '/api/tasks/complete/',
            '/api/offers/complete/',
            '/api/referral/click/',
            '/api/withdraw/request/'
        ]
        
        if not any(request.path.startswith(endpoint) for endpoint in earning_endpoints):
            return None
        
        # Task completion rate limiting
        if request.path.startswith('/api/tasks/complete/'):
            return self._check_task_completion(request)
        
        # Offer completion rate limiting
        elif request.path.startswith('/api/offers/complete/'):
            return self._check_offer_completion(request)
        
        # Referral click rate limiting
        elif request.path.startswith('/api/referral/click/'):
            return self._check_referral_click(request)
        
        # Withdrawal request rate limiting
        elif request.path.startswith('/api/withdraw/request/'):
            return self._check_withdrawal_request(request)
        
        return None
    
    def _check_task_completion(self, request):
        """Check task completion rate limits"""
        if not request.user.is_authenticated:
            return None
        
        task_type = getattr(request, 'task_type', 'default')
        
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
                'error': 'daily_task_limit_exceeded',
                'message': f'আজ আপনি সর্বোচ্চ {task_limit["limit"]}টি টাস্ক সম্পূর্ণ করেছেন। আগামীকাল আবার চেষ্টা করুন।',
                'remaining_tasks': 0,
                'reset_time': task_limit['reset_time'],
                'is_premium': task_limit['is_premium']
            }, status=429)
        
        # Add task limit info to request
        request.task_limit_info = task_limit
        
        return None
    
    def _check_offer_completion(self, request):
        """Check offer completion rate limits"""
        if not request.user.is_authenticated:
            return None
        
        offer_wall = getattr(request, 'offer_wall', 'default')
        
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
                'error': 'hourly_offer_limit_exceeded',
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
                'error': 'daily_referral_limit_exceeded',
                'message': 'আজকের জন্য রেফারেল লিঙ্কে ক্লিক করার লিমিট শেষ হয়েছে। আগামীকাল আবার চেষ্টা করুন।',
                'remaining_clicks': 0,
                'reset_time': referral_limit['reset_time']
            }, status=429)
        
        return None
    
    def _check_withdrawal_request(self, request):
        """Check withdrawal request rate limits"""
        if not request.user.is_authenticated:
            return None
        
        # Check if user has made too many withdrawal requests today
        try:
            today = time.strftime("%Y-%m-%d")
            key = f"withdrawal_requests:{request.user.id}:{today}"
            
            redis_client = self.rate_limit_service.redis_limiter.redis_client
            request_count = redis_client.incr(key)
            
            if request_count == 1:
                # Set expiration to end of day
                remaining_seconds = 24 * 3600  # Simplified
                redis_client.expire(key, remaining_seconds)
            
            # Allow maximum 3 withdrawal requests per day
            if request_count > 3:
                return JsonResponse({
                    'success': False,
                    'error': 'daily_withdrawal_limit_exceeded',
                    'message': 'আপনি আজ সর্বোচ্চ ৩টি উত্তোলন রিকুয়েস্ট করতে পারবেন। আগামীকাল আবার চেষ্টা করুন।',
                    'remaining_requests': 0
                }, status=429)
        except Exception as e:
            print(f"[WARN] Withdrawal check error: {e}")
            # Allow request if check fails
        
        return None
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip



# from django.http import JsonResponse
# from django.utils.deprecation import MiddlewareMixin
# from django.conf import settings
# import time
# import json
# from .services.RateLimitService import RateLimitService


# class RateLimitMiddleware(MiddlewareMixin):
#     """Rate limiting middleware for Django"""
    
#     def __init__(self, get_response):
#         self.get_response = get_response
#         self.rate_limit_service = RateLimitService()
        
#         # Exclude these paths from rate limiting
#         self.exclude_paths = getattr(settings, 'RATE_LIMIT_EXCLUDE_PATHS', [
#             '/admin/',
#             '/static/',
#             '/media/',
#             '/health/',
#             '/api/rate-limit/health/'
#         ])
        
#         # Exclude these HTTP methods
#         self.exclude_methods = getattr(settings, 'RATE_LIMIT_EXCLUDE_METHODS', ['OPTIONS'])
    
#     def process_request(self, request):
#         """Process request before view is called"""
        
#         # Check if path should be excluded
#         if any(request.path.startswith(path) for path in self.exclude_paths):
#             return None
        
#         # Check if method should be excluded
#         if request.method in self.exclude_methods:
#             return None
        
#         # Add earning app specific attributes
#         self._add_earning_attributes(request)
        
#         # Check rate limit
#         result = self.rate_limit_service.check_request(request)
        
#         if not result['is_allowed']:
#             # Rate limit exceeded
#             return self._rate_limit_exceeded_response(request, result)
        
#         # Add rate limit headers to request for use in views
#         request.rate_limit_info = result
        
#         return None
    
#     def process_response(self, request, response):
#         """Process response before returning to client"""
        
#         # Add rate limit headers if available
#         if hasattr(request, 'rate_limit_info'):
#             self._add_rate_limit_headers(response, request.rate_limit_info, request)
        
#         return response
    
#     def _add_earning_attributes(self, request):
#         """Add earning application specific attributes to request"""
#         # Parse request body for task/offer data
#         if request.method in ['POST', 'PUT', 'PATCH']:
#             try:
#                 if request.content_type == 'application/json':
#                     body = json.loads(request.body.decode('utf-8'))
                    
#                     # Extract earning app specific data
#                     for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
#                         if attr in body:
#                             setattr(request, attr, body[attr])
                            
#                 elif request.content_type in ['application/x-www-form-urlencoded', 'multipart/form-data']:
#                     # Handle form data
#                     for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
#                         if attr in request.POST:
#                             setattr(request, attr, request.POST[attr])
                            
#             except (json.JSONDecodeError, UnicodeDecodeError):
#                 pass
        
#         # Also check query parameters
#         for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
#             if attr in request.GET:
#                 setattr(request, attr, request.GET[attr])
    
#     def _rate_limit_exceeded_response(self, request, result):
#         """Create rate limit exceeded response"""
#         failed_configs = result['failed_configs']
        
#         if failed_configs:
#             failed_config = failed_configs[0]
#             config = failed_config['config']
#             metadata = failed_config['metadata']
            
#             # Custom response for earning app
#             if hasattr(request, 'task_id'):
#                 message = "টাস্ক সম্পূর্ণ করার লিমিট শেষ হয়েছে। আগামীকাল আবার চেষ্টা করুন।"
#             elif hasattr(request, 'offer_id'):
#                 message = "অফার সম্পূর্ণ করার লিমিট শেষ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।"
#             elif hasattr(request, 'referral_code'):
#                 message = "রেফারেল লিঙ্কে খুব বেশি ক্লিক করা হয়েছে। আগামীকাল আবার চেষ্টা করুন।"
#             else:
#                 message = f"রেট লিমিট অতিক্রম করেছেন। {config.requests_per_unit} অনুরোধ প্রতি {config.time_value} {config.time_unit}"
            
#             response_data = {
#                 'success': False,
#                 'error': 'rate_limit_exceeded',
#                 'message': message,
#                 'code': 429,
#                 'details': {
#                     'limit': config.requests_per_unit,
#                     'time_unit': config.time_unit,
#                     'time_value': config.time_value,
#                     'current': metadata.get('current_count', 0),
#                     'remaining': metadata.get('remaining', 0),
#                     'reset_time': int(metadata.get('reset_time', time.time()))
#                 },
#                 'config_name': config.name
#             }
#         else:
#             response_data = {
#                 'success': False,
#                 'error': 'rate_limit_exceeded',
#                 'message': 'রেট লিমিট অতিক্রম করেছেন',
#                 'code': 429
#             }
        
#         response = JsonResponse(response_data, status=429)
        
#         # Add Retry-After header
#         if failed_configs and 'reset_time' in failed_configs[0]['metadata']:
#             reset_time = failed_configs[0]['metadata']['reset_time']
#             retry_after = max(0, int(reset_time - time.time()))
#             response['Retry-After'] = str(retry_after)
        
#         return response
    
#     def _add_rate_limit_headers(self, response, rate_limit_info, request=None):
#         """Add rate limit headers to response"""
#         if not rate_limit_info.get('is_allowed', True):
#             return
        
#         configs = rate_limit_info.get('configs', [])
        
#         if configs:
#             # Use the strictest config
#             strictest_config = min(configs, key=lambda x: x.requests_per_unit / ({"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(x.time_unit, 3600) * x.time_value))
            
#             # Get current usage
#             identifier = f"user:{request.user.id}" if request.user.is_authenticated else f"ip:{self._get_client_ip(request)}"
#             usage_info = self.rate_limit_service.redis_limiter.get_rate_limit_info(
#                 identifier, strictest_config
#             )
            
#             # Add headers
#             response['X-RateLimit-Limit'] = str(strictest_config.requests_per_unit)
#             response['X-RateLimit-Remaining'] = str(usage_info['remaining'])
#             response['X-RateLimit-Reset'] = str(int(usage_info['reset_time']))
#             response['X-RateLimit-Policy'] = f"{strictest_config.requests_per_unit}; w={({"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(strictest_config.time_unit, 3600) * strictest_config.time_value)}"
    
#     def _get_client_ip(self, request):
#         """Get client IP address"""
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             ip = x_forwarded_for.split(',')[0]
#         else:
#             ip = request.META.get('REMOTE_ADDR')
#         return ip


# class EarningTaskRateLimitMiddleware(MiddlewareMixin):
#     """Specialized middleware for earning task rate limiting"""
    
#     def __init__(self, get_response):
#         self.get_response = get_response
#         self.rate_limit_service = RateLimitService()
    
#     def process_request(self, request):
#         """Process task-specific rate limits"""
        
#         # Only process earning-related endpoints
#         earning_endpoints = [
#             '/api/tasks/complete/',
#             '/api/offers/complete/',
#             '/api/referral/click/',
#             '/api/withdraw/request/'
#         ]
        
#         if not any(request.path.startswith(endpoint) for endpoint in earning_endpoints):
#             return None
        
#         # Task completion rate limiting
#         if request.path.startswith('/api/tasks/complete/'):
#             return self._check_task_completion(request)
        
#         # Offer completion rate limiting
#         elif request.path.startswith('/api/offers/complete/'):
#             return self._check_offer_completion(request)
        
#         # Referral click rate limiting
#         elif request.path.startswith('/api/referral/click/'):
#             return self._check_referral_click(request)
        
#         # Withdrawal request rate limiting
#         elif request.path.startswith('/api/withdraw/request/'):
#             return self._check_withdrawal_request(request)
        
#         return None
    
#     def _check_task_completion(self, request):
#         """Check task completion rate limits"""
#         if not request.user.is_authenticated:
#             return None
        
#         task_type = getattr(request, 'task_type', 'default')
        
#         # Check daily task limit
#         task_limit = self.rate_limit_service.check_task_completion_limit(
#             request.user, task_type
#         )
        
#         if not task_limit['is_allowed']:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'daily_task_limit_exceeded',
#                 'message': f'আজ আপনি সর্বোচ্চ {task_limit["limit"]}টি টাস্ক সম্পূর্ণ করেছেন। আগামীকাল আবার চেষ্টা করুন।',
#                 'remaining_tasks': 0,
#                 'reset_time': task_limit['reset_time'],
#                 'is_premium': task_limit['is_premium']
#             }, status=429)
        
#         # Add task limit info to request
#         request.task_limit_info = task_limit
        
#         return None
    
#     def _check_offer_completion(self, request):
#         """Check offer completion rate limits"""
#         if not request.user.is_authenticated:
#             return None
        
#         offer_wall = getattr(request, 'offer_wall', 'default')
        
#         # Check hourly offer limit
#         offer_limit = self.rate_limit_service.check_offer_access_limit(
#             request.user, offer_wall
#         )
        
#         if not offer_limit['is_allowed']:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'hourly_offer_limit_exceeded',
#                 'message': f'আপনি এই ঘন্টায় সর্বোচ্চ {offer_limit["limit"]}টি অফার সম্পূর্ণ করেছেন। পরবর্তী ঘন্টায় আবার চেষ্টা করুন।',
#                 'remaining_offers': 0,
#                 'reset_time': offer_limit['reset_time']
#             }, status=429)
        
#         # Add offer limit info to request
#         request.offer_limit_info = offer_limit
        
#         return None
    
#     def _check_referral_click(self, request):
#         """Check referral click rate limits"""
#         ip_address = self._get_client_ip(request)
        
#         # Check daily referral click limit per IP
#         referral_limit = self.rate_limit_service.check_referral_activity(ip_address)
        
#         if not referral_limit['is_allowed']:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'daily_referral_limit_exceeded',
#                 'message': 'আজকের জন্য রেফারেল লিঙ্কে ক্লিক করার লিমিট শেষ হয়েছে। আগামীকাল আবার চেষ্টা করুন।',
#                 'remaining_clicks': 0,
#                 'reset_time': referral_limit['reset_time']
#             }, status=429)
        
#         return None
    
#     def _check_withdrawal_request(self, request):
#         """Check withdrawal request rate limits"""
#         if not request.user.is_authenticated:
#             return None
        
#         # Check if user has made too many withdrawal requests today
#         today = time.strftime("%Y-%m-%d")
#         key = f"withdrawal_requests:{request.user.id}:{today}"
        
#         redis_client = self.rate_limit_service.redis_limiter.redis_client
#         request_count = redis_client.incr(key)
        
#         if request_count == 1:
#             # Set expiration to end of day
#             remaining_seconds = 24 * 3600  # Simplified
#             redis_client.expire(key, remaining_seconds)
        
#         # Allow maximum 3 withdrawal requests per day
#         if request_count > 3:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'daily_withdrawal_limit_exceeded',
#                 'message': 'আপনি আজ সর্বোচ্চ ৩টি উত্তোলন রিকুয়েস্ট করতে পারবেন। আগামীকাল আবার চেষ্টা করুন।',
#                 'remaining_requests': 0
#             }, status=429)
        
#         return None
    
#     def _get_client_ip(self, request):
#         """Get client IP address"""
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             ip = x_forwarded_for.split(',')[0]
#         else:
#             ip = request.META.get('REMOTE_ADDR')
#         return ip