# =============================================================================
# auto_mod/decorators.py
# =============================================================================

"""
Custom decorators for auto moderation system.
Provides caching, rate limiting, permission checking, and logging functionality.
"""

import time
import logging
import functools
from typing import Any, Callable, Dict, List, Optional, Union
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .exceptions import (
    ScanRateLimitError, QueueAssignmentRateLimitError, 
    AppealCreationRateLimitError, ModelTrainingRateLimitError
)
from .constants import (
    CACHE_TTL_RULES, CACHE_TTL_SCAN_RESULT, CACHE_TTL_BOT_STATUS,
    CACHE_TTL_MODEL_VERSION
)

logger = logging.getLogger(__name__)
User = get_user_model()


def cache_result(cache_key_func: Callable, ttl: int = 300, 
                cache_none: bool = False) -> Callable:
    """
    Cache function results based on provided cache key function.
    
    Args:
        cache_key_func: Function that generates cache key from function arguments
        ttl: Cache time-to-live in seconds
        cache_none: Whether to cache None results
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_key_func(*args, **kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result (if not None or cache_none is True)
            if result is not None or cache_none:
                cache.set(cache_key, result, ttl)
                logger.debug(f"Cached result for key: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


def rate_limit(limit: int, window: int = 60, 
               key_func: Optional[Callable] = None,
               error_class: Optional[type] = None) -> Callable:
    """
    Rate limiting decorator.
    
    Args:
        limit: Maximum number of requests allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key (defaults to user-based)
        error_class: Exception class to raise on rate limit exceeded
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                rate_key = key_func(*args, **kwargs)
            else:
                # Default to user-based rate limiting
                request = args[0] if args and hasattr(args[0], 'user') else None
                if request and hasattr(request, 'user') and request.user.is_authenticated:
                    rate_key = f"rate_limit:{func.__name__}:{request.user.pk}"
                else:
                    rate_key = f"rate_limit:{func.__name__}:anonymous"
            
            # Check current count
            current_count = cache.get(rate_key) or 0
            
            if current_count >= limit:
                logger.warning(f"Rate limit exceeded for key: {rate_key}")
                
                # Raise appropriate error
                if error_class:
                    raise error_class()
                else:
                    raise ScanRateLimitError()
            
            # Increment count
            cache.set(rate_key, current_count + 1, window)
            
            # Execute function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_permissions(*permissions: str) -> Callable:
    """
    Decorator to check user permissions.
    
    Args:
        *permissions: Required permissions
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get user from request
            request = args[0] if args and hasattr(args[0], 'user') else None
            
            if not request or not hasattr(request, 'user'):
                return Response(
                    {"detail": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            user = request.user
            
            if not user.is_authenticated:
                return Response(
                    {"detail": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check permissions
            for permission in permissions:
                if not user.has_perm(permission):
                    logger.warning(f"Permission denied: {permission} for user {user.pk}")
                    return Response(
                        {"detail": f"Permission denied: {permission}"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_execution(log_level: int = logging.INFO, 
                  include_args: bool = False,
                  include_result: bool = False) -> Callable:
    """
    Log function execution.
    
    Args:
        log_level: Logging level
        include_args: Whether to include function arguments in log
        include_result: Whether to include function result in log
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Log function start
            log_data = {
                'function': func.__name__,
                'module': func.__module__
            }
            
            if include_args:
                log_data['args'] = str(args)
                log_data['kwargs'] = str(kwargs)
            
            logger.log(log_level, f"Function started: {log_data}")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log function completion
                duration = time.time() - start_time
                log_data['duration'] = duration
                
                if include_result:
                    log_data['result'] = str(result)[:500]  # Limit result length
                
                logger.log(log_level, f"Function completed: {log_data}")
                
                return result
                
            except Exception as exc:
                # Log function error
                duration = time.time() - start_time
                log_data['duration'] = duration
                log_data['error'] = str(exc)
                
                logger.error(f"Function failed: {log_data}")
                raise
        
        return wrapper
    return decorator


def atomic_transaction(isolation: str = None) -> Callable:
    """
    Atomic transaction decorator.
    
    Args:
        isolation: Transaction isolation level
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if isolation:
                with transaction.atomic(isolation=isolation):
                    return func(*args, **kwargs)
            else:
                with transaction.atomic():
                    return func(*args, **kwargs)
        
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, 
                    delay: float = 1.0,
                    backoff: float = 2.0,
                    exceptions: tuple = (Exception,)) -> Callable:
    """
    Retry decorator for functions that might fail.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay on each retry
        exceptions: Exception types to catch and retry on
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {exc}")
                        raise
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {exc}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # This should never be reached
            raise last_exception
        
        return wrapper
    return decorator


def validate_input(validator_func: Callable) -> Callable:
    """
    Input validation decorator.
    
    Args:
        validator_func: Function that validates input arguments
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Validate input
            validation_result = validator_func(*args, **kwargs)
            
            if not validation_result.get('valid', True):
                error_message = validation_result.get('error', 'Invalid input')
                logger.warning(f"Input validation failed for {func.__name__}: {error_message}")
                
                return Response(
                    {"detail": error_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def timing_threshold(max_duration: float) -> Callable:
    """
    Monitor function execution time and log warnings if threshold exceeded.
    
    Args:
        max_duration: Maximum allowed duration in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                if duration > max_duration:
                    logger.warning(
                        f"Function {func.__name__} exceeded threshold: "
                        f"{duration:.2f}s > {max_duration:.2f}s"
                    )
                
                return result
                
            except Exception as exc:
                duration = time.time() - start_time
                logger.error(
                    f"Function {func.__name__} failed after {duration:.2f}s: {exc}"
                )
                raise
        
        return wrapper
    return decorator


def conditional_cache(condition_func: Callable, 
                    cache_key_func: Callable, 
                    ttl: int = 300) -> Callable:
    """
    Conditional caching decorator.
    
    Args:
        condition_func: Function that determines if result should be cached
        cache_key_func: Function that generates cache key
        ttl: Cache time-to-live in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check if should cache
            should_cache = condition_func(*args, **kwargs)
            
            if not should_cache:
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = cache_key_func(*args, **kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Conditional cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl)
            logger.debug(f"Conditionally cached result for key: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


def audit_trail(action: str, include_args: bool = False) -> Callable:
    """
    Audit trail decorator for important operations.
    
    Args:
        action: Action description for audit log
        include_args: Whether to include function arguments in audit
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get user from request
            request = args[0] if args and hasattr(args[0], 'user') else None
            user = getattr(request, 'user', None) if request else None
            
            # Create audit entry
            audit_data = {
                'action': action,
                'function': func.__name__,
                'module': func.__module__,
                'timestamp': timezone.now().isoformat(),
                'user_id': user.pk if user else None,
                'user_username': user.username if user else None
            }
            
            if include_args:
                audit_data['args'] = str(args)
                audit_data['kwargs'] = str(kwargs)
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log successful audit
                audit_data['status'] = 'success'
                logger.info(f"Audit: {audit_data}")
                
                return result
                
            except Exception as exc:
                # Log failed audit
                audit_data['status'] = 'failed'
                audit_data['error'] = str(exc)
                logger.error(f"Audit: {audit_data}")
                raise
        
        return wrapper
    return decorator


# Specific decorators for auto moderation use cases

def cache_rules(ttl: int = CACHE_TTL_RULES) -> Callable:
    """Cache active rules decorator."""
    def cache_key(submission_type: str) -> str:
        return f"auto_mod:rules:active:{submission_type}"
    
    return cache_result(cache_key, ttl)


def cache_scan_results(ttl: int = CACHE_TTL_SCAN_RESULT) -> Callable:
    """Cache scan results decorator."""
    def cache_key(submission_id: str, scan_type: str) -> str:
        return f"auto_mod:scan:{submission_id}:{scan_type}"
    
    return cache_result(cache_key, ttl)


def cache_bot_status(ttl: int = CACHE_TTL_BOT_STATUS) -> Callable:
    """Cache bot status decorator."""
    def cache_key(bot_id: str) -> str:
        return f"auto_mod:bot:status:{bot_id}"
    
    return cache_result(cache_key, ttl)


def cache_model_version(ttl: int = CACHE_TTL_MODEL_VERSION) -> Callable:
    """Cache ML model version decorator."""
    def cache_key(model_name: str) -> str:
        return f"auto_mod:ml:version:{model_name}"
    
    return cache_result(cache_key, ttl)


def rate_limit_scans(limit: int = 10, window: int = 60) -> Callable:
    """Rate limit for scan operations."""
    def key_func(*args, **kwargs) -> str:
        request = args[0] if args and hasattr(args[0], 'user') else None
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return f"scan_rate:{request.user.pk}"
        return "scan_rate:anonymous"
    
    return rate_limit(limit, window, key_func, ScanRateLimitError)


def rate_limit_queue_assignments(limit: int = 20, window: int = 300) -> Callable:
    """Rate limit for queue assignment operations."""
    def key_func(*args, **kwargs) -> str:
        request = args[0] if args and hasattr(args[0], 'user') else None
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return f"queue_assign_rate:{request.user.pk}"
        return "queue_assign_rate:anonymous"
    
    return rate_limit(limit, window, key_func, QueueAssignmentRateLimitError)


def rate_limit_appeals(limit: int = 5, window: int = 3600) -> Callable:
    """Rate limit for appeal creation."""
    def key_func(*args, **kwargs) -> str:
        request = args[0] if args and hasattr(args[0], 'user') else None
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return f"appeal_rate:{request.user.pk}"
        return "appeal_rate:anonymous"
    
    return rate_limit(limit, window, key_func, AppealCreationRateLimitError)


def rate_limit_model_training(limit: int = 2, window: int = 86400) -> Callable:
    """Rate limit for model training."""
    def key_func(*args, **kwargs) -> str:
        request = args[0] if args and hasattr(args[0], 'user') else None
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return f"model_train_rate:{request.user.pk}"
        return "model_train_rate:anonymous"
    
    return rate_limit(limit, window, key_func, ModelTrainingRateLimitError)


def require_moderator_permissions() -> Callable:
    """Require moderator permissions decorator."""
    return require_permissions('auto_mod.moderate')


def require_admin_permissions() -> Callable:
    """Require admin permissions decorator."""
    return require_permissions('auto_mod.admin')


def require_model_management_permissions() -> Callable:
    """Require model management permissions decorator."""
    return require_permissions('auto_mod.manage_models')


def log_moderation_actions() -> Callable:
    """Log moderation actions decorator."""
    return log_execution(logging.INFO, include_args=True, include_result=False)


def audit_moderation_actions(action: str) -> Callable:
    """Audit moderation actions decorator."""
    return audit_trail(action, include_args=True)


def timing_critical_operations(max_duration: float = 30.0) -> Callable:
    """Monitor timing for critical operations."""
    return timing_threshold(max_duration)


def retry_ml_operations(max_retries: int = 3, delay: float = 2.0) -> Callable:
    """Retry decorator for ML operations."""
    return retry_on_failure(max_retries, delay, backoff=2.0, 
                          exceptions=(ConnectionError, TimeoutError))


def atomic_moderation_operations() -> Callable:
    """Atomic transaction for moderation operations."""
    return atomic_transaction()


# API view decorators
def api_moderation_view(methods: List[str] = None, 
                       permissions: List[str] = None) -> Callable:
    """
    Combined API view decorator for moderation endpoints.
    
    Args:
        methods: HTTP methods allowed
        permissions: Required permissions
        
    Returns:
        Decorated view function
    """
    if methods is None:
        methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    
    decorators = [api_view(methods)]
    
    if permissions:
        decorators.append(permission_classes([IsAuthenticated]))
        decorators.append(require_permissions(*permissions))
    
    def combined_decorator(func: Callable) -> Callable:
        for decorator in reversed(decorators):
            func = decorator(func)
        return func
    
    return combined_decorator
