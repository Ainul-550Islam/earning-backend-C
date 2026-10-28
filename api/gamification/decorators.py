"""
Gamification Decorators — Custom decorators for gamification functionality.

This module provides various decorators for caching, logging, validation,
rate limiting, and other cross-cutting concerns in the gamification system.
"""

from __future__ import annotations
import asyncio

import functools
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response

from api.gamification.exceptions import GamificationServiceError
from api.gamification.dependencies import get_service

logger = logging.getLogger(__name__)


def cache_result(key_prefix: str, timeout: int = 300, key_func: Optional[Callable] = None):
    """Decorator to cache function results."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                # Generate cache key
                if key_func:
                    cache_key = key_prefix + key_func(*args, **kwargs)
                else:
                    cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
                
                # Try to get from cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Cache result
                cache.set(cache_key, result, timeout)
                
                return result
                
            except Exception as e:
                logger.error(f"Error in cache_result decorator for {func.__name__}: {e}")
                # Execute function without caching on error
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def cache_result_async(key_prefix: str, timeout: int = 300, key_func: Optional[Callable] = None):
    """Decorator to cache async function results."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                # Generate cache key
                if key_func:
                    cache_key = key_prefix + key_func(*args, **kwargs)
                else:
                    cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
                
                # Try to get from cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result
                cache.set(cache_key, result, timeout)
                
                return result
                
            except Exception as e:
                logger.error(f"Error in cache_result_async decorator for {func.__name__}: {e}")
                # Execute function without caching on error
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_execution(level: str = "INFO", include_args: bool = False, include_result: bool = False):
    """Decorator to log function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            # Log start
            log_data = {
                'function': func.__name__,
                'module': func.__module__,
                'start_time': timezone.now().isoformat()
            }
            
            if include_args:
                log_data['args'] = str(args)
                log_data['kwargs'] = str(kwargs)
            
            getattr(logger, level.lower())(f"Starting {func.__name__}: {log_data}")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Log success
                log_data.update({
                    'status': 'success',
                    'execution_time': execution_time,
                    'end_time': timezone.now().isoformat()
                })
                
                if include_result:
                    log_data['result'] = str(result)
                
                getattr(logger, level.lower())(f"Completed {func.__name__}: {log_data}")
                
                return result
                
            except Exception as e:
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Log error
                log_data.update({
                    'status': 'error',
                    'error': str(e),
                    'execution_time': execution_time,
                    'end_time': timezone.now().isoformat()
                })
                
                getattr(logger, level.lower())(f"Failed {func.__name__}: {log_data}")
                raise
        
        return wrapper
    return decorator


def log_execution_async(level: str = "INFO", include_args: bool = False, include_result: bool = False):
    """Decorator to log async function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            # Log start
            log_data = {
                'function': func.__name__,
                'module': func.__module__,
                'start_time': timezone.now().isoformat()
            }
            
            if include_args:
                log_data['args'] = str(args)
                log_data['kwargs'] = str(kwargs)
            
            getattr(logger, level.lower())(f"Starting {func.__name__}: {log_data}")
            
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Log success
                log_data.update({
                    'status': 'success',
                    'execution_time': execution_time,
                    'end_time': timezone.now().isoformat()
                })
                
                if include_result:
                    log_data['result'] = str(result)
                
                getattr(logger, level.lower())(f"Completed {func.__name__}: {log_data}")
                
                return result
                
            except Exception as e:
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Log error
                log_data.update({
                    'status': 'error',
                    'error': str(e),
                    'execution_time': execution_time,
                    'end_time': timezone.now().isoformat()
                })
                
                getattr(logger, level.lower())(f"Failed {func.__name__}: {log_data}")
                raise
        
        return wrapper
    return decorator


def validate_points(min_value: int = 0, max_value: Optional[int] = None):
    """Decorator to validate points parameters."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Find points parameter
            points = None
            if 'points' in kwargs:
                points = kwargs['points']
            elif args:
                # Try to find points in positional arguments
                for arg in args:
                    if isinstance(arg, (int, float)):
                        points = arg
                        break
            
            if points is not None:
                if not isinstance(points, (int, float)):
                    raise GamificationServiceError("Points must be a number")
                
                if points < min_value:
                    raise GamificationServiceError(f"Points cannot be less than {min_value}")
                
                if max_value is not None and points > max_value:
                    raise GamificationServiceError(f"Points cannot exceed {max_value}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def rate_limit(max_calls: int, period: int, key_func: Optional[Callable] = None):
    """Decorator to rate limit function calls."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                # Generate rate limit key
                if key_func:
                    rate_key = f"rate_limit:{func.__name__}:{key_func(*args, **kwargs)}"
                else:
                    rate_key = f"rate_limit:{func.__name__}"
                
                # Get current count
                current_count = cache.get(rate_key, 0)
                
                if current_count >= max_calls:
                    raise GamificationServiceError(f"Rate limit exceeded: {max_calls} calls per {period} seconds")
                
                # Increment count
                cache.set(rate_key, current_count + 1, period)
                
                return func(*args, **kwargs)
                
            except GamificationServiceError:
                raise
            except Exception as e:
                logger.error(f"Error in rate_limit decorator for {func.__name__}: {e}")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def transactional(atomic: bool = True):
    """Decorator to wrap function in database transaction."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if atomic:
                with transaction.atomic():
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def transactional_async(atomic: bool = True):
    """Decorator to wrap async function in database transaction."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if atomic:
                with transaction.atomic():
                    return await func(*args, **kwargs)
            else:
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: Tuple = (Exception,)):
    """Decorator to retry function on failure."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_async(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: Tuple = (Exception,)):
    """Decorator to retry async function on failure."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    
                    if attempt < max_retries:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator


def require_permissions(*permissions: str):
    """Decorator to check user permissions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get user from first argument or kwargs
            user = None
            if args and hasattr(args[0], 'user'):
                user = args[0].user
            elif 'user' in kwargs:
                user = kwargs['user']
            elif 'request' in kwargs and hasattr(kwargs['request'], 'user'):
                user = kwargs['request'].user
            
            if not user or not user.is_authenticated:
                raise GamificationServiceError("Authentication required")
            
            # Check permissions
            for permission in permissions:
                if not user.has_perm(permission):
                    raise GamificationServiceError(f"Permission required: {permission}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_permissions_async(*permissions: str):
    """Decorator to check user permissions for async functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Get user from first argument or kwargs
            user = None
            if args and hasattr(args[0], 'user'):
                user = args[0].user
            elif 'user' in kwargs:
                user = kwargs['user']
            elif 'request' in kwargs and hasattr(kwargs['request'], 'user'):
                user = kwargs['request'].user
            
            if not user or not user.is_authenticated:
                raise GamificationServiceError("Authentication required")
            
            # Check permissions
            for permission in permissions:
                if not user.has_perm(permission):
                    raise GamificationServiceError(f"Permission required: {permission}")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def measure_performance(log_slow_calls: bool = True, slow_threshold: float = 1.0):
    """Decorator to measure and log function performance."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            if log_slow_calls and execution_time > slow_threshold:
                logger.warning(f"Slow call detected: {func.__name__} took {execution_time:.2f}s")
            
            return result
        
        return wrapper
    return decorator


def measure_performance_async(log_slow_calls: bool = True, slow_threshold: float = 1.0):
    """Decorator to measure and log async function performance."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            if log_slow_calls and execution_time > slow_threshold:
                logger.warning(f"Slow call detected: {func.__name__} took {execution_time:.2f}s")
            
            return result
        
        return wrapper
    return decorator


def validate_user_exists():
    """Decorator to validate user exists."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get user_id from arguments
            user_id = None
            if 'user_id' in kwargs:
                user_id = kwargs['user_id']
            elif args:
                # Try to find user_id in positional arguments
                for arg in args:
                    if isinstance(arg, str) and len(arg) == 36:  # UUID length
                        user_id = arg
                        break
            
            if user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                if not User.objects.filter(id=user_id).exists():
                    raise GamificationServiceError(f"User not found: {user_id}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_user_exists_async():
    """Decorator to validate user exists for async functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Get user_id from arguments
            user_id = None
            if 'user_id' in kwargs:
                user_id = kwargs['user_id']
            elif args:
                # Try to find user_id in positional arguments
                for arg in args:
                    if isinstance(arg, str) and len(arg) == 36:  # UUID length
                        user_id = arg
                        break
            
            if user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                if not await User.objects.filter(id=user_id).aexists():
                    raise GamificationServiceError(f"User not found: {user_id}")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def feature_flag_enabled(flag_name: str):
    """Decorator to check if feature flag is enabled."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                feature_flag_service = get_service('feature_flag_service')
                if not feature_flag_service.is_enabled(flag_name):
                    raise GamificationServiceError(f"Feature flag not enabled: {flag_name}")
            except Exception as e:
                logger.warning(f"Error checking feature flag {flag_name}: {e}")
                # Continue execution if feature flag service is not available
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def feature_flag_enabled_async(flag_name: str):
    """Decorator to check if feature flag is enabled for async functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                feature_flag_service = get_service('feature_flag_service')
                if not await feature_flag_service.is_enabled_async(flag_name):
                    raise GamificationServiceError(f"Feature flag not enabled: {flag_name}")
            except Exception as e:
                logger.warning(f"Error checking feature flag {flag_name}: {e}")
                # Continue execution if feature flag service is not available
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def api_response(format_func: Optional[Callable] = None):
    """Decorator to standardize API responses."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Response:
            try:
                result = func(*args, **kwargs)
                
                if format_func:
                    formatted_result = format_func(result)
                else:
                    formatted_result = result
                
                return Response({
                    'success': True,
                    'data': formatted_result,
                    'timestamp': timezone.now().isoformat()
                })
                
            except GamificationServiceError as e:
                return Response({
                    'success': False,
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }, status=400)
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                return Response({
                    'success': False,
                    'error': 'Internal server error',
                    'timestamp': timezone.now().isoformat()
                }, status=500)
        
        return wrapper
    return decorator


def api_response_async(format_func: Optional[Callable] = None):
    """Decorator to standardize async API responses."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Response:
            try:
                result = await func(*args, **kwargs)
                
                if format_func:
                    formatted_result = format_func(result)
                else:
                    formatted_result = result
                
                return Response({
                    'success': True,
                    'data': formatted_result,
                    'timestamp': timezone.now().isoformat()
                })
                
            except GamificationServiceError as e:
                return Response({
                    'success': False,
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }, status=400)
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                return Response({
                    'success': False,
                    'error': 'Internal server error',
                    'timestamp': timezone.now().isoformat()
                }, status=500)
        
        return wrapper
    return decorator


# Utility decorators
def deprecated(reason: str = ""):
    """Decorator to mark deprecated functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            message = f"Function {func.__name__} is deprecated"
            if reason:
                message += f": {reason}"
            
            logger.warning(message)
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def deprecated_async(reason: str = ""):
    """Decorator to mark deprecated async functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            message = f"Function {func.__name__} is deprecated"
            if reason:
                message += f": {reason}"
            
            logger.warning(message)
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def timeout(seconds: float):
    """Decorator to add timeout to function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            # Set timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                signal.alarm(0)  # Cancel timeout
        
        return wrapper
    return decorator


def timeout_async(seconds: float):
    """Decorator to add timeout to async function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            import asyncio
            
            try:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
                return result
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
        
        return wrapper
    return decorator


# Enhanced decorators for new gamification models
def validate_points_transaction():
    """Decorator to validate points transaction parameters."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Validate amount
            amount = kwargs.get('amount')
            if amount is None:
                raise GamificationServiceError("Amount is required for points transaction")
            
            if not isinstance(amount, (int, float)):
                raise GamificationServiceError("Amount must be a number")
            
            if amount == 0:
                raise GamificationServiceError("Amount cannot be zero")
            
            # Validate source
            source = kwargs.get('source')
            if source is None:
                raise GamificationServiceError("Source is required for points transaction")
            
            from api.gamification.choices import PointsTransactionSource
            valid_sources = [choice.value for choice in PointsTransactionSource]
            if source not in valid_sources:
                raise GamificationServiceError(f"Invalid source: {source}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_streak_freeze():
    """Decorator to validate streak freeze parameters."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Validate reason
            reason = kwargs.get('reason')
            if reason is None:
                raise GamificationServiceError("Reason is required for streak freeze")
            
            from api.gamification.choices import StreakFreezeReason
            valid_reasons = [choice.value for choice in StreakFreezeReason]
            if reason not in valid_reasons:
                raise GamificationServiceError(f"Invalid reason: {reason}")
            
            # Validate duration
            duration_hours = kwargs.get('duration_hours')
            if duration_hours is not None:
                if not isinstance(duration_hours, int) or duration_hours <= 0:
                    raise GamificationServiceError("Duration hours must be a positive integer")
                
                from api.gamification.constants import MAX_STREAK_FREEZE_DURATION
                if duration_hours > MAX_STREAK_FREEZE_DURATION:
                    raise GamificationServiceError(f"Duration cannot exceed {MAX_STREAK_FREEZE_DURATION} hours")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_contest_participant():
    """Decorator to validate contest participant parameters."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Validate contest cycle
            contest_cycle_id = kwargs.get('contest_cycle_id')
            if contest_cycle_id is None:
                raise GamificationServiceError("Contest cycle ID is required")
            
            # Check if contest exists and is active
            from api.gamification.models import ContestCycle
            try:
                contest = ContestCycle.objects.get(id=contest_cycle_id)
                if not contest.is_active:
                    raise GamificationServiceError("Contest is not active")
            except ContestCycle.DoesNotExist:
                raise GamificationServiceError("Contest cycle not found")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_gamification_config():
    """Decorator to validate gamification configuration parameters."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Validate tenant
            tenant_id = kwargs.get('tenant_id')
            if tenant_id is None:
                raise GamificationServiceError("Tenant ID is required")
            
            # Validate feature
            feature = kwargs.get('feature')
            if feature is None:
                raise GamificationServiceError("Feature is required")
            
            from api.gamification.choices import GamificationFeature
            valid_features = [choice.value for choice in GamificationFeature]
            if feature not in valid_features:
                raise GamificationServiceError(f"Invalid feature: {feature}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_gamification_insight():
    """Decorator to validate gamification insight parameters."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Validate date
            date = kwargs.get('date')
            if date is None:
                raise GamificationServiceError("Date is required for insight")
            
            # Validate metric type
            metric_type = kwargs.get('metric_type')
            if metric_type is None:
                raise GamificationServiceError("Metric type is required")
            
            from api.gamification.choices import InsightMetricType
            valid_types = [choice.value for choice in InsightMetricType]
            if metric_type not in valid_types:
                raise GamificationServiceError(f"Invalid metric type: {metric_type}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_user_points_balance(minimum_points: int = 0):
    """Decorator to check if user has sufficient points balance."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            user_id = kwargs.get('user_id')
            if user_id is None:
                raise GamificationServiceError("User ID is required")
            
            from api.gamification.models import UserPoints
            try:
                user_points = UserPoints.objects.get(user_id=user_id)
                if user_points.total_points < minimum_points:
                    raise GamificationServiceError(f"Insufficient points balance. Required: {minimum_points}, Available: {user_points.total_points}")
            except UserPoints.DoesNotExist:
                raise GamificationServiceError("User points record not found")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def track_points_transaction():
    """Decorator to automatically track points transactions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Execute function
            result = func(*args, **kwargs)
            
            # Log transaction if it was successful
            try:
                user_id = kwargs.get('user_id')
                amount = kwargs.get('amount')
                source = kwargs.get('source')
                
                if all([user_id, amount, source]):
                    logger.info(f"Points transaction tracked: user={user_id}, amount={amount}, source={source}")
                    
                    # Trigger WebSocket update if available
                    try:
                        from api.gamification.consumers import broadcast_points_update
                        broadcast_points_update(user_id, {
                            'amount': amount,
                            'source': source,
                            'timestamp': timezone.now().isoformat()
                        })
                    except ImportError:
                        pass  # WebSocket not available
                        
            except Exception as e:
                logger.warning(f"Failed to track points transaction: {e}")
            
            return result
        
        return wrapper
    return decorator


def prevent_concurrent_points_transactions():
    """Decorator to prevent concurrent points transactions for the same user."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            user_id = kwargs.get('user_id')
            if user_id is None:
                raise GamificationServiceError("User ID is required")
            
            # Use cache lock to prevent concurrent transactions
            lock_key = f"points_transaction_lock:{user_id}"
            
            # Try to acquire lock
            if cache.get(lock_key):
                raise GamificationServiceError("Another points transaction is in progress")
            
            # Set lock with short timeout
            cache.set(lock_key, True, timeout=30)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Release lock
                cache.delete(lock_key)
        
        return wrapper
    return decorator


def cache_user_points(timeout: int = 300):
    """Decorator to cache user points after operations."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            # Invalidate and update cache for user points
            try:
                user_id = kwargs.get('user_id')
                if user_id:
                    cache_key = f"user_points:{user_id}"
                    cache.delete(cache_key)  # Invalidate old cache
                    
                    # Update cache with fresh data
                    from api.gamification.models import UserPoints
                    try:
                        user_points = UserPoints.objects.get(user_id=user_id)
                        cache.set(cache_key, {
                            'total_points': user_points.total_points,
                            'available_points': user_points.available_points,
                            'points_expiry_date': user_points.points_expiry_date.isoformat() if user_points.points_expiry_date else None,
                            'last_updated': user_points.updated_at.isoformat()
                        }, timeout)
                    except UserPoints.DoesNotExist:
                        pass
                        
            except Exception as e:
                logger.warning(f"Failed to cache user points: {e}")
            
            return result
        
        return wrapper
    return decorator
