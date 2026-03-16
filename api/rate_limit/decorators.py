from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from functools import wraps
import time
from .services.RateLimitService import RateLimitService


def rate_limit(config_name: str = None, **kwargs):
    """
    Rate limit decorator for Django views
    
    Usage:
        @rate_limit(config_name='api_limit')
        def my_view(request):
            ...
        
        @rate_limit(requests=100, minutes=1)
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            rate_limit_service = RateLimitService()
            
            # Check if specific config should be used
            if config_name:
                try:
                    from .models import RateLimitConfig
                    config = RateLimitConfig.objects.get(name=config_name, is_active=True)
                    configs = [config]
                except RateLimitConfig.DoesNotExist:
                    # If config doesn't exist, apply default rate limiting
                    configs = rate_limit_service.get_applicable_configs(request)
            else:
                # Use dynamic configuration from kwargs
                configs = rate_limit_service.get_applicable_configs(request)
                
                # Apply additional constraints from kwargs
                if kwargs:
                    # Filter configs based on kwargs
                    filtered_configs = []
                    for config in configs:
                        if all(
                            getattr(config, key, None) == value 
                            for key, value in kwargs.items() 
                            if hasattr(config, key)
                        ):
                            filtered_configs.append(config)
                    configs = filtered_configs
            
            # Check rate limit
            result = rate_limit_service.check_request(request)
            
            if not result['is_allowed']:
                # Rate limit exceeded
                failed_configs = result['failed_configs']
                if failed_configs:
                    failed_config = failed_configs[0]
                    config = failed_config['config']
                    metadata = failed_config['metadata']
                    
                    response = JsonResponse({
                        'success': False,
                        'error': 'rate_limit_exceeded',
                        'message': f'রেট লিমিট অতিক্রম করেছেন: {config.name}',
                        'limit': config.requests_per_unit,
                        'remaining': metadata.get('remaining', 0),
                        'reset_time': int(metadata.get('reset_time', time.time()))
                    }, status=429)
                    
                    # Add Retry-After header
                    if 'reset_time' in metadata:
                        retry_after = max(0, int(metadata['reset_time'] - time.time()))
                        response['Retry-After'] = str(retry_after)
                    
                    return response
            
            # Add rate limit info to request
            request.rate_limit_info = result
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def task_rate_limit(task_type: str = None):
    """
    Task-specific rate limit decorator
    
    Usage:
        @task_rate_limit(task_type='video_watch')
        def complete_video_task(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'authentication_required'
                }, status=401)
            
            rate_limit_service = RateLimitService()
            
            # Determine task type
            actual_task_type = task_type or getattr(request, 'task_type', 'default')
            
            # Check task completion limit
            task_limit = rate_limit_service.check_task_completion_limit(
                request.user, actual_task_type
            )
            
            if not task_limit['is_allowed']:
                return JsonResponse({
                    'success': False,
                    'error': 'daily_task_limit_exceeded',
                    'message': f'আজ আপনি সর্বোচ্চ {task_limit["limit"]}টি টাস্ক সম্পূর্ণ করেছেন।',
                    'remaining_tasks': 0,
                    'reset_time': task_limit['reset_time'],
                    'is_premium': task_limit['is_premium']
                }, status=429)
            
            # Add task limit info to request
            request.task_limit_info = task_limit
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def offer_rate_limit(offer_wall: str = None):
    """
    Offer-specific rate limit decorator
    
    Usage:
        @offer_rate_limit(offer_wall='adgem')
        def complete_offer(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'authentication_required'
                }, status=401)
            
            rate_limit_service = RateLimitService()
            
            # Determine offer wall
            actual_offer_wall = offer_wall or getattr(request, 'offer_wall', 'default')
            
            # Check offer access limit
            offer_limit = rate_limit_service.check_offer_access_limit(
                request.user, actual_offer_wall
            )
            
            if not offer_limit['is_allowed']:
                return JsonResponse({
                    'success': False,
                    'error': 'hourly_offer_limit_exceeded',
                    'message': f'আপনি এই ঘন্টায় সর্বোচ্চ {offer_limit["limit"]}টি অফার সম্পূর্ণ করেছেন।',
                    'remaining_offers': 0,
                    'reset_time': offer_limit['reset_time']
                }, status=429)
            
            # Add offer limit info to request
            request.offer_limit_info = offer_limit
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def referral_rate_limit():
    """
    Referral-specific rate limit decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            rate_limit_service = RateLimitService()
            
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            # Check referral click limit
            referral_limit = rate_limit_service.check_referral_activity(ip)
            
            if not referral_limit['is_allowed']:
                return JsonResponse({
                    'success': False,
                    'error': 'daily_referral_limit_exceeded',
                    'message': 'আজকের জন্য রেফারেল লিঙ্কে ক্লিক করার লিমিট শেষ হয়েছে।',
                    'remaining_clicks': 0,
                    'reset_time': referral_limit['reset_time']
                }, status=429)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def premium_only():
    """
    Decorator to restrict access to premium users only
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'authentication_required'
                }, status=401)
            
            # Check if user has premium rate limit profile
            try:
                from .models import UserRateLimitProfile
                profile = UserRateLimitProfile.objects.get(user=request.user)
                
                if not profile.is_premium:
                    return JsonResponse({
                        'success': False,
                        'error': 'premium_required',
                        'message': 'এই ফিচারটি শুধুমাত্র প্রিমিয়াম ইউজারদের জন্য।'
                    }, status=403)
                
            except UserRateLimitProfile.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'premium_required',
                    'message': 'এই ফিচারটি শুধুমাত্র প্রিমিয়াম ইউজারদের জন্য।'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def dynamic_rate_limit(**dynamic_kwargs):
    """
    Dynamic rate limit decorator that can be configured per view
    
    Usage:
        @dynamic_rate_limit(requests_per_minute=60, premium_requests_per_minute=300)
        def api_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            rate_limit_service = RateLimitService()
            
            # Check if user is premium
            is_premium = False
            if request.user.is_authenticated:
                try:
                    from .models import UserRateLimitProfile
                    profile = UserRateLimitProfile.objects.get(user=request.user)
                    is_premium = profile.is_premium
                except UserRateLimitProfile.DoesNotExist:
                    pass
            
            # Determine limits based on user tier
            if is_premium and 'premium_' in str(dynamic_kwargs):
                # Use premium limits
                limits = {
                    key.replace('premium_', ''): value 
                    for key, value in dynamic_kwargs.items() 
                    if key.startswith('premium_')
                }
            else:
                # Use regular limits
                limits = {
                    key: value 
                    for key, value in dynamic_kwargs.items() 
                    if not key.startswith('premium_')
                }
            
            # Create temporary config for this request
            from .models import RateLimitConfig
            temp_config = RateLimitConfig(
                name=f"dynamic_{view_func.__name__}",
                rate_limit_type='endpoint',
                endpoint=request.path,
                requests_per_unit=limits.get('requests', 60),
                time_unit=limits.get('time_unit', 'minute'),
                time_value=limits.get('time_value', 1),
                is_active=True
            )
            
            # Check rate limit with temporary config
            result = rate_limit_service.redis_limiter.check_rate_limit(request, temp_config)
            
            if not result[0]:
                metadata = result[1]
                return JsonResponse({
                    'success': False,
                    'error': 'rate_limit_exceeded',
                    'message': 'রেট লিমিট অতিক্রম করেছেন',
                    'remaining': metadata.get('remaining', 0),
                    'reset_time': int(metadata.get('reset_time', time.time())),
                    'is_premium': is_premium
                }, status=429)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator