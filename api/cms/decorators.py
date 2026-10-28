# api/cms/decorators.py
"""Custom decorators for CMS views, services and tasks."""
import functools
import logging
import time
from django.core.cache import cache

logger = logging.getLogger(__name__)


def require_cms_admin(view_func):
    """View decorator: require staff or cms_admin group."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'authentication_required'}, status=401)
        if not (request.user.is_staff or
                request.user.groups.filter(name='cms_admin').exists()):
            from django.http import JsonResponse
            return JsonResponse({'error': 'permission_denied'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def cache_response(ttl: int = 300, key_prefix: str = ''):
    """Cache view/function response for ttl seconds."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from prefix + args
            key = f"cms:cache:{key_prefix or func.__name__}:{hash(str(args) + str(kwargs))}"
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator


def atomic_with_retry(max_retries: int = 3, delay_sec: float = 0.1):
    """
    Retry a function on database errors (e.g. deadlock).
    Wraps in atomic transaction.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from django.db import transaction, DatabaseError
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        return func(*args, **kwargs)
                except DatabaseError as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"[Retry] {func.__name__} attempt {attempt + 1}/{max_retries}: {e}")
                    time.sleep(delay_sec * (2 ** attempt))
        return wrapper
    return decorator


def require_user_profile_complete(view_func):
    """View decorator: require complete user profile."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'authentication_required'}, status=401)
        
        try:
            from api.cms.models_new.user_profile import UserProfile
            profile = UserProfile.objects.get(user=request.user)
            if profile.profile_completeness < 50:
                from django.http import JsonResponse
                return JsonResponse({'error': 'profile_incomplete'}, status=400)
        except UserProfile.DoesNotExist:
            from django.http import JsonResponse
            return JsonResponse({'error': 'profile_not_found'}, status=404)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_survey_access(view_func):
    """View decorator: require user to have access to survey."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'authentication_required'}, status=401)
        
        survey_uuid = kwargs.get('survey_uuid')
        if not survey_uuid:
            from django.http import JsonResponse
            return JsonResponse({'error': 'survey_uuid_required'}, status=400)
        
        try:
            from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            if not manager.can_user_access_survey(request.user, survey_uuid):
                from django.http import JsonResponse
                return JsonResponse({'error': 'survey_not_available'}, status=403)
        except Exception as e:
            logger.error(f"[Survey Access] Error checking access: {e}")
            from django.http import JsonResponse
            return JsonResponse({'error': 'survey_check_failed'}, status=500)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def rate_limit_survey_completion(max_per_hour: int = 10):
    """Decorator: rate limit survey completion attempts."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return func(request, *args, **kwargs)
            
            # Check rate limit
            cache_key = f"survey_completion_rate:{request.user.id}"
            current_count = cache.get(cache_key, 0)
            
            if current_count >= max_per_hour:
                from django.http import JsonResponse
                return JsonResponse({'error': 'rate_limit_exceeded'}, status=429)
            
            # Increment counter
            cache.set(cache_key, current_count + 1, 3600)  # 1 hour TTL
            
            try:
                result = func(request, *args, **kwargs)
                return result
            except Exception as e:
                # Decrement on error
                cache.decr(cache_key)
                raise
        
        return wrapper
    return decorator


def validate_reward_transaction(view_func):
    """View decorator: validate reward transaction parameters."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'authentication_required'}, status=401)
        
        # Validate amount
        amount = kwargs.get('amount')
        if amount is None:
            from django.http import JsonResponse
            return JsonResponse({'error': 'amount_required'}, status=400)
        
        try:
            from decimal import Decimal
            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                from django.http import JsonResponse
                return JsonResponse({'error': 'amount_invalid'}, status=400)
        except (ValueError, TypeError):
            from django.http import JsonResponse
            return JsonResponse({'error': 'amount_invalid'}, status=400)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_task_permission(view_func):
    """View decorator: require task management permissions."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({'error': 'authentication_required'}, status=401)
        
        if not (request.user.is_staff or request.user.is_superuser):
            from django.http import JsonResponse
            return JsonResponse({'error': 'permission_denied'}, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def task_lock_timeout(timeout_seconds: int = 300):
    """Decorator: acquire task lock with timeout."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from api.cms.services_new.TaskManagementService import TaskManagementService
            service = TaskManagementService()
            
            task_name = kwargs.get('task_name', func.__name__)
            lock_key = f"task_lock:{task_name}"
            
            # Try to acquire lock
            if service.acquire_lock(lock_key, timeout_seconds):
                try:
                    return func(*args, **kwargs)
                finally:
                    service.release_lock(lock_key)
            else:
                raise Exception(f"Could not acquire lock for task: {task_name}")
        
        return wrapper
    return decorator


def log_task_execution(view_func):
    """Decorator: log task execution details."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        task_name = kwargs.get('task_name', view_func.__name__)
        
        logger.info(f"[Task] Starting: {task_name}")
        
        try:
            result = view_func(request, *args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"[Task] Completed: {task_name} in {execution_time:.2f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[Task] Failed: {task_name} in {execution_time:.2f}s - {e}")
            raise
        
        return wrapper
    return decorator


def cache_user_data(ttl: int = 1800):
    """Decorator: cache user-specific data."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return func(request, *args, **kwargs)
            
            cache_key = f"user_data:{request.user.id}:{func.__name__}"
            cached = cache.get(cache_key)
            
            if cached is not None:
                return cached
            
            result = func(request, *args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


def validate_survey_response_data(view_func):
    """Decorator: validate survey response data structure."""
    def decorator(func):
        @functools.wraps(func_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.http import JsonResponse
                return JsonResponse({'error': 'authentication_required'}, status=401)
            
            responses = kwargs.get('responses', [])
            if not isinstance(responses, list):
                from django.http import JsonResponse
                return JsonResponse({'error': 'responses_invalid'}, status=400)
            
            # Validate each response
            for response in responses:
                if not isinstance(response, dict) or 'question_id' not in response:
                    from django.http import JsonResponse
                    return JsonResponse({'error': 'response_structure_invalid'}, status=400)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def monitor_performance(threshold_ms: int = 1000):
    """Decorator: monitor and log slow operations."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                if execution_time > threshold_ms:
                    logger.warning(f"[Performance] {func.__name__} took {execution_time:.2f}ms (threshold: {threshold_ms}ms)")
                
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(f"[Performance] {func.__name__} failed after {execution_time:.2f}ms: {e}")
                raise
        
        return wrapper
    return decorator


def handle_service_errors(service_name: str = None):
    """Decorator: handle service-specific errors consistently."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                service_name = service_name or func.__name__
                logger.error(f"[{service_name}] Error: {e}")
                
                # Re-raise with service context
                from api.cms.exceptions import CMSException
                if isinstance(e, CMSException):
                    raise
                else:
                    raise CMSException(
                        detail=f"{service_name} error: {str(e)}",
                        code=f"{service_name}_error"
                    )
        
        return wrapper
    return decorator


def atomic_retry(max_retries: int = 3, delay_sec: float = 0.1):
    """Decorator: retry function inside atomic transaction on OperationalError."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from django.db import transaction, OperationalError
            last_error = None
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        return func(*args, **kwargs)
                except OperationalError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay_sec * (2 ** attempt))
                    logger.warning(f"[atomic_retry] {func.__name__} attempt {attempt+1}/{max_retries}: {e}")
            raise last_error
        return wrapper
    return decorator


def log_service_call(service_name: str = ''):
    """Log service method calls with timing."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = service_name or func.__qualname__
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start) * 1000
                if elapsed > 500:
                    logger.warning(f"[SLOW] {name} took {elapsed:.0f}ms")
                else:
                    logger.debug(f"[Service] {name} — {elapsed:.0f}ms")
                return result
            except Exception as e:
                logger.error(f"[Service ERROR] {name}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


def postback_endpoint(func):
    """
    Mark a view as a CPAlead postback endpoint.
    Disables CSRF, logs all requests, returns text/plain.
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        from django.views.decorators.csrf import csrf_exempt
        from django.http import HttpResponse
        logger.info(
            f"[Postback] {request.method} from {request.META.get('REMOTE_ADDR')} "
            f"params={dict(request.GET)}"
        )
        try:
            result = func(request, *args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"[Postback ERROR] {e}", exc_info=True)
            return HttpResponse("0", content_type="text/plain", status=200)
    wrapper.csrf_exempt = True
    return wrapper


def rate_limit(key_template: str, max_calls: int, window_sec: int):
    """
    Decorator: rate limit by cache key.
    key_template can use {user_id}, {ip} placeholders.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            ip = request.META.get('REMOTE_ADDR', 'unknown')
            user_id = request.user.id if request.user.is_authenticated else 'anon'
            key = f"cms:rl:{key_template.format(user_id=user_id, ip=ip)}"
            count = cache.get(key, 0)
            if count >= max_calls:
                from rest_framework.response import Response
                from rest_framework import status as drf_status
                return Response(
                    {'error': 'rate_limited', 'retry_after': window_sec},
                    status=drf_status.HTTP_429_TOO_MANY_REQUESTS
                )
            cache.set(key, count + 1, window_sec)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_feature_enabled(feature: str):
    """Check if a site feature is enabled before allowing access."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from api.cms.services_new.WithdrawalService import SiteConfigService
                config = SiteConfigService.get_config()
                features = config.get('features', {})
                if not features.get(feature, True):
                    from rest_framework.response import Response
                    return Response(
                        {'error': f'{feature} is currently disabled'},
                        status=503
                    )
            except Exception:
                pass
            return func(*args, **kwargs)
        return wrapper
    return decorator
