"""
Backup Module Decorators
Custom decorators for backup operations and utilities
"""

import functools
import time
import logging
import traceback
from typing import Callable, Any, Optional, Dict, List
from django.core.cache import cache
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .exceptions import (
    BackupException,
    BackupTimeoutException,
    BackupLockException,
    InsufficientPermissionsException,
    DecoratorException
)
from .constants import CACHE_TIMEOUT_SECONDS, CACHE_KEY_PREFIX

logger = logging.getLogger(__name__)


def backup_operation(operation_type: str = 'backup'):
    """
    Decorator to mark and log backup operations
    
    Args:
        operation_type: Type of backup operation (backup, restore, verify, etc.)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_type}_{int(start_time)}"
            
            logger.info(f"Starting {operation_type} operation", extra={
                'operation_id': operation_id,
                'operation_type': operation_type,
                'function': func.__name__,
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            })
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(f"Completed {operation_type} operation", extra={
                    'operation_id': operation_id,
                    'operation_type': operation_type,
                    'function': func.__name__,
                    'duration': duration,
                    'success': True
                })
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(f"Failed {operation_type} operation", extra={
                    'operation_id': operation_id,
                    'operation_type': operation_type,
                    'function': func.__name__,
                    'duration': duration,
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                
                raise
                
        return wrapper
    return decorator


def timeout_handler(timeout_seconds: int, operation_name: Optional[str] = None):
    """
    Decorator to handle operation timeouts
    
    Args:
        timeout_seconds: Maximum allowed execution time
        operation_name: Name of the operation for logging
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            op_name = operation_name or func.__name__
            
            def check_timeout():
                if time.time() - start_time > timeout_seconds:
                    raise BackupTimeoutException(
                        f"Operation '{op_name}' timed out",
                        timeout_seconds=timeout_seconds,
                        elapsed_seconds=time.time() - start_time,
                        operation=op_name
                    )
            
            # For long-running operations, we need to check periodically
            # This is a simplified implementation
            try:
                result = func(*args, **kwargs)
                check_timeout()  # Final check
                return result
            except BackupTimeoutException:
                raise
            except Exception as e:
                check_timeout()  # Check if timeout occurred during exception
                raise
                
        return wrapper
    return decorator


def backup_lock(lock_key: Optional[str] = None, timeout: int = 300):
    """
    Decorator to prevent concurrent backup operations on the same resource
    
    Args:
        lock_key: Custom lock key (defaults to function name)
        timeout: Lock timeout in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = lock_key or f"backup_lock_{func.__name__}"
            lock_cache_key = f"{CACHE_KEY_PREFIX}lock_{key}"
            
            # Try to acquire lock
            if cache.get(lock_cache_key):
                raise BackupLockException(
                    f"Operation is already running",
                    lock_owner=cache.get(f"{lock_cache_key}_owner"),
                    lock_time=cache.get(f"{lock_cache_key}_time")
                )
            
            # Set lock
            cache.set(lock_cache_key, True, timeout)
            cache.set(f"{lock_cache_key}_owner", "system", timeout)
            cache.set(f"{lock_cache_key}_time", time.time(), timeout)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Release lock
                cache.delete(lock_cache_key)
                cache.delete(f"{lock_cache_key}_owner")
                cache.delete(f"{lock_cache_key}_time")
                
        return wrapper
    return decorator


def cache_result(cache_key: Optional[str] = None, timeout: int = CACHE_TIMEOUT_SECONDS):
    """
    Decorator to cache function results
    
    Args:
        cache_key: Custom cache key (defaults to function name + args hash)
        timeout: Cache timeout in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key:
                key = f"{CACHE_KEY_PREFIX}{cache_key}"
            else:
                # Create key from function name and arguments
                import hashlib
                args_str = str(args) + str(sorted(kwargs.items()))
                args_hash = hashlib.md5(args_str.encode()).hexdigest()
                key = f"{CACHE_KEY_PREFIX}cache_{func.__name__}_{args_hash}"
            
            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            try:
                result = func(*args, **kwargs)
                cache.set(key, result, timeout)
                logger.debug(f"Cached result for {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error caching result for {func.__name__}: {e}")
                raise
                
        return wrapper
    return decorator


def require_backup_permissions(permission: str = 'backup.add_backup'):
    """
    Decorator to check backup-specific permissions
    
    Args:
        permission: Required permission string
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check if user has required permission
            from django.contrib.auth.decorators import user_passes_test
            
            def has_permission(user):
                return user.has_perm(permission)
            
            permission_decorator = user_passes_test(has_permission)
            wrapped_func = permission_decorator(func)
            
            try:
                return wrapped_func(*args, **kwargs)
            except Exception as e:
                raise InsufficientPermissionsException(
                    f"Permission denied: {permission}",
                    required_permission=permission,
                    user_id=getattr(args[0], 'id', None) if args else None
                )
                
        return wrapper
    return decorator


def atomic_backup_transaction(using: Optional[str] = None, savepoint: bool = True):
    """
    Decorator to ensure atomic database transactions for backup operations
    
    Args:
        using: Database to use (defaults to default)
        savepoint: Whether to use savepoints
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with transaction.atomic(using=using, savepoint=savepoint):
                    return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Transaction failed for {func.__name__}: {e}")
                raise BackupException(
                    f"Database transaction failed for {func.__name__}",
                    details={'error': str(e), 'function': func.__name__}
                )
                
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry failed operations with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for exponential backoff
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Final attempt failed for {func.__name__} after {max_retries} retries")
                        raise
                    
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {current_delay}s")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # This should never be reached
            raise last_exception
            
        return wrapper
    return decorator


def log_performance(threshold: float = 1.0):
    """
    Decorator to log performance metrics for functions
    
    Args:
        threshold: Minimum execution time to log (in seconds)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            memory_before = None
            
            try:
                # Try to get memory usage (optional)
                import psutil
                process = psutil.Process()
                memory_before = process.memory_info().rss
            except ImportError:
                pass
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if duration >= threshold:
                    log_data = {
                        'function': func.__name__,
                        'duration': duration,
                        'args_count': len(args),
                        'kwargs_count': len(kwargs)
                    }
                    
                    if memory_before:
                        try:
                            import psutil
                            memory_after = psutil.Process().memory_info().rss
                            memory_diff = memory_after - memory_before
                            log_data['memory_before'] = memory_before
                            log_data['memory_after'] = memory_after
                            log_data['memory_diff'] = memory_diff
                        except:
                            pass
                    
                    logger.info(f"Performance log for {func.__name__}", extra=log_data)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Performance error for {func.__name__}", extra={
                    'function': func.__name__,
                    'duration': duration,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                raise
                
        return wrapper
    return decorator


def validate_backup_input(validator_func: Callable):
    """
    Decorator to validate input parameters for backup operations
    
    Args:
        validator_func: Function to validate input parameters
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Validate input
                validator_func(*args, **kwargs)
                return func(*args, **kwargs)
            except Exception as e:
                raise DecoratorException(
                    f"Input validation failed for {func.__name__}",
                    decorator_name='validate_backup_input',
                    function_name=func.__name__,
                    details={'validation_error': str(e)}
                )
                
        return wrapper
    return decorator


def backup_api_view(methods: List[str], **kwargs):
    """
    Combined decorator for backup API views
    
    Args:
        methods: Allowed HTTP methods
        **kwargs: Additional arguments for api_view decorator
    """
    def decorator(func: Callable) -> Callable:
        # Apply api_view decorator
        func = api_view(methods, **kwargs)(func)
        
        # Apply backup operation decorator
        func = backup_operation('api_call')(func)
        
        # Apply performance logging
        func = log_performance()(func)
        
        return func
        
    return decorator


def backup_admin_action(action_name: Optional[str] = None):
    """
    Decorator for backup admin actions
    
    Args:
        action_name: Name of the admin action
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(modeladmin, request, queryset):
            name = action_name or func.__name__
            
            logger.info(f"Admin action '{name}' started", extra={
                'action_name': name,
                'model': modeladmin.model.__name__,
                'user_id': request.user.id if request.user else None,
                'queryset_count': queryset.count()
            })
            
            try:
                result = func(modeladmin, request, queryset)
                
                logger.info(f"Admin action '{name}' completed", extra={
                    'action_name': name,
                    'model': modeladmin.model.__name__,
                    'user_id': request.user.id if request.user else None,
                    'success': True
                })
                
                return result
                
            except Exception as e:
                logger.error(f"Admin action '{name}' failed", extra={
                    'action_name': name,
                    'model': modeladmin.model.__name__,
                    'user_id': request.user.id if request.user else None,
                    'success': False,
                    'error': str(e)
                })
                
                modeladmin.message_user(request, f"Error in {name}: {str(e)}", level='error')
                return None
                
        return wrapper
    return decorator


def backup_task(retry: bool = True, retry_policy: Optional[Dict] = None):
    """
    Decorator for backup Celery tasks
    
    Args:
        retry: Whether to retry on failure
        retry_policy: Custom retry policy
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            task_name = f"backup_task_{func.__name__}"
            
            logger.info(f"Starting backup task '{task_name}'", extra={
                'task_name': task_name,
                'args_count': len(args),
                'kwargs_count': len(kwargs)
            })
            
            try:
                result = func(*args, **kwargs)
                
                logger.info(f"Completed backup task '{task_name}'", extra={
                    'task_name': task_name,
                    'success': True
                })
                
                return result
                
            except Exception as e:
                logger.error(f"Failed backup task '{task_name}'", extra={
                    'task_name': task_name,
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                
                if retry:
                    # Implement retry logic based on policy
                    policy = retry_policy or {'max_retries': 3, 'countdown': 60}
                    # This would integrate with Celery's retry mechanism
                    # For now, just re-raise the exception
                    pass
                
                raise
                
        return wrapper
    return decorator


def backup_signal_handler(signal_name: Optional[str] = None):
    """
    Decorator for backup signal handlers
    
    Args:
        signal_name: Name of the signal being handled
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(sender, **kwargs):
            name = signal_name or f"signal_{func.__name__}"
            
            logger.debug(f"Signal handler '{name}' triggered", extra={
                'signal_name': name,
                'sender': str(sender),
                'kwargs_keys': list(kwargs.keys())
            })
            
            try:
                result = func(sender, **kwargs)
                
                logger.debug(f"Signal handler '{name}' completed", extra={
                    'signal_name': name,
                    'sender': str(sender),
                    'success': True
                })
                
                return result
                
            except Exception as e:
                logger.error(f"Signal handler '{name}' failed", extra={
                    'signal_name': name,
                    'sender': str(sender),
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                
                # Signal handlers should not raise exceptions
                # Log the error and continue
                
        return wrapper
    return decorator


# Combined decorators for common use cases
def backup_creation_operation(func: Callable) -> Callable:
    """Combined decorator for backup creation operations"""
    return backup_operation('backup_creation')(
        atomic_backup_transaction()(
            backup_lock('backup_creation')(
                log_performance(2.0)(func)
            )
        )
    )


def backup_restoration_operation(func: Callable) -> Callable:
    """Combined decorator for backup restoration operations"""
    return backup_operation('backup_restoration')(
        atomic_backup_transaction()(
            backup_lock('backup_restoration')(
                log_performance(5.0)(func)
            )
        )
    )


def backup_verification_operation(func: Callable) -> Callable:
    """Combined decorator for backup verification operations"""
    return backup_operation('backup_verification')(
        backup_lock('backup_verification')(
            log_performance(1.0)(func)
        )
    )


def backup_api_endpoint(methods: List[str] = ['GET', 'POST']) -> Callable:
    """Combined decorator for backup API endpoints"""
    return lambda func: backup_api_view(methods)(
        require_backup_permissions()(
            log_performance(1.0)(func)
        )
    )
