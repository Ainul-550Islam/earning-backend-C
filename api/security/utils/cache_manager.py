"""
Bulletproof Cache Manager with Comprehensive Defensive Coding Patterns
"""

from django.core.cache import cache
from typing import Any, Callable, Dict, Optional, Union, TypeVar, cast, List, Tuple
import logging
import functools
import traceback
from datetime import datetime, timedelta
import hashlib
import json
import time

logger = logging.getLogger(__name__)

# Type variables for better type hints
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')


class CacheManager:
    """
    Ultimate Bulletproof Cache Manager with All Defensive Patterns
    """
    
    # Cache key prefix for namespace isolation
    PREFIX = "bulletproof"
    
    # Sentinel values for special cache states
    CACHE_MISS = "__CACHE_MISS__"
    CACHE_EXPIRED = "__CACHE_EXPIRED__"
    CACHE_ERROR = "__CACHE_ERROR__"
    
    @staticmethod
    def generate_key(prefix: str, *args, **kwargs) -> str:
        """
        Generate consistent cache key with defensive error handling
        """
        try:
            # Build key parts
            parts = [CacheManager.PREFIX, prefix]
            
            # Add args safely
            for i, arg in enumerate(args):
                try:
                    if arg is None:
                        parts.append(f"arg{i}:None")
                    elif isinstance(arg, (int, float, str, bool)):
                        parts.append(f"arg{i}:{arg}")
                    else:
                        # Use repr with length limit
                        arg_str = repr(arg)[:50]
                        parts.append(f"arg{i}:{hashlib.md5(arg_str.encode()).hexdigest()[:8]}")
                except Exception:
                    parts.append(f"arg{i}:error")
            
            # Add kwargs safely
            if kwargs:
                sorted_keys = sorted(kwargs.keys())
                for key in sorted_keys:
                    try:
                        value = kwargs[key]
                        if value is None:
                            parts.append(f"{key}:None")
                        elif isinstance(value, (int, float, str, bool)):
                            parts.append(f"{key}:{value}")
                        else:
                            value_str = repr(value)[:50]
                            parts.append(f"{key}:{hashlib.md5(value_str.encode()).hexdigest()[:8]}")
                    except Exception:
                        parts.append(f"{key}:error")
            
            # Join and clean
            key = ":".join(parts)
            
            # Ensure key length is reasonable
            if len(key) > 250:
                key_hash = hashlib.md5(key.encode()).hexdigest()
                key = f"{CacheManager.PREFIX}:{prefix}:hash:{key_hash}"
            
            # Replace problematic characters
            safe_chars = []
            for char in key:
                if char.isalnum() or char in ":_-.":
                    safe_chars.append(char)
                else:
                    safe_chars.append("_")
            
            return "".join(safe_chars)
            
        except Exception as e:
            logger.error(f"Cache key generation failed: {str(e)}")
            # Fallback key
            return f"{CacheManager.PREFIX}:{prefix}:error:{int(time.time())}"
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        Safe cache get with Null Object Pattern and Graceful Degradation
        """
        try:
            value = cache.get(key)
            
            # Handle special sentinel values
            if value in [CacheManager.CACHE_MISS, CacheManager.CACHE_EXPIRED, CacheManager.CACHE_ERROR]:
                logger.debug(f"Cache sentinel value found for key '{key}': {value}")
                return default
            
            # Null Object Pattern: Return default if value is None
            if value is None:
                return default
            
            # Validate JSON if string
            if isinstance(value, str):
                # Check if it's JSON
                if value.startswith('{') or value.startswith('['):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in cache for key '{key}'")
                        # Graceful degradation - return string as-is
                        pass
            
            return value
            
        except Exception as e:
            # Graceful Degradation: Log but don't crash
            logger.debug(f"Cache get failed for key '{key}': {e}")
            return default
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> bool:
        """
        Safe cache set with comprehensive validation
        """
        try:
            # Validate input
            if value is None:
                logger.warning(f"Attempting to cache None for key '{key}'")
                # Still cache it, but log warning
            
            # Handle complex objects
            if not isinstance(value, (str, int, float, bool, list, dict, tuple)):
                try:
                    # Try to serialize
                    value = str(value)
                except Exception:
                    logger.error(f"Cannot serialize value for cache key '{key}'")
                    return False
            
            # Set in cache
            cache.set(key, value, timeout)
            
            # Optional: Verify write
            if logger.isEnabledFor(logging.DEBUG):
                cached = cache.get(key)
                if cached != value:
                    logger.warning(f"Cache write verification failed for key '{key}'")
            
            return True
            
        except Exception as e:
            # Graceful Degradation
            logger.error(f"Cache set failed for key '{key}': {e}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """
        Safe cache delete with error tolerance
        """
        try:
            cache.delete(key)
            return True
        except Exception as e:
            # Graceful Degradation: Don't crash if delete fails
            logger.debug(f"Cache delete failed for key '{key}': {e}")
            return False
    
    @staticmethod
    def get_or_set(
        key: str, 
        default_fn: Callable[[], Any], 
        timeout: int = 300,
        force_refresh: bool = False
    ) -> Any:
        """
        Ultimate get_or_set with retry logic and defensive coding
        """
        # Check cache first (unless forcing refresh)
        if not force_refresh:
            cached = CacheManager.get(key)
            if cached is not None:
                return cached
        
        # Generate new value
        try:
            # Use retry logic for default function
            value = CacheManager._safe_execute_with_retry(default_fn)
            
            # Cache the value
            if value is not None:
                CacheManager.set(key, value, timeout)
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get_or_set failed for key '{key}': {e}")
            
            # Try to get stale cache as fallback
            if not force_refresh:
                stale = CacheManager.get(key)
                if stale is not None:
                    logger.info(f"Using stale cache for key '{key}' after failure")
                    return stale
            
            # Return None as last resort (Null Object Pattern)
            return None
    
    @staticmethod
    def increment(key: str, delta: int = 1, default: int = 0) -> int:
        """
        Safe increment with defensive coding
        """
        try:
            return cache.incr(key, delta)
        except ValueError:  # Key doesn't exist or value isn't an integer
            try:
                cache.set(key, default, timeout=None)
                return default
            except Exception:
                return default
        except Exception as e:
            logger.debug(f"Cache increment failed for key '{key}': {e}")
            return default
    
    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """
        Delete keys matching pattern (safe implementation)
        """
        try:
            # Note: This requires Redis or similar backend
            # For Django's default cache, we can't do pattern deletion efficiently
            
            # Alternative: Use key namespace and manual tracking
            logger.warning("Pattern deletion not fully supported in default cache backend")
            return 0
            
        except Exception as e:
            logger.error(f"Cache pattern delete failed: {e}")
            return 0
    
    @staticmethod
    def get_many(keys: List[str]) -> Dict[str, Any]:
        """
        Safe batch get with defensive coding
        """
        try:
            values = cache.get_many(keys)
            
            # Apply Null Object Pattern for missing keys
            result = {}
            for key in keys:
                value = values.get(key)
                if value in [CacheManager.CACHE_MISS, CacheManager.CACHE_EXPIRED, CacheManager.CACHE_ERROR]:
                    result[key] = None
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            logger.error(f"Cache get_many failed: {e}")
            # Return empty dict as fallback
            return {key: None for key in keys}
    
    @staticmethod
    def set_many(data: Dict[str, Any], timeout: int = 300) -> bool:
        """
        Safe batch set
        """
        try:
            cache.set_many(data, timeout)
            return True
        except Exception as e:
            logger.error(f"Cache set_many failed: {e}")
            return False
    
    @staticmethod
    def _safe_execute_with_retry(func: Callable[[], Any], max_retries: int = 2) -> Any:
        """
        Execute function with retry logic (private helper)
        """
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Function execution failed after {max_retries} attempts: {e}")
                    raise
                
                # Wait before retry
                time.sleep(0.1 * (2 ** attempt))
        
        # Should never reach here
        return None


def handle_gracefully(
    default_return: Any = None,
    log_errors: bool = True,
    suppress_errors: bool = True,
    retry_count: int = 0,
    retry_delay: float = 0.1
) -> Callable[[F], F]:
    """
    Ultimate Bulletproof Decorator with all defensive patterns
    
    Args:
        default_return: Null Object Pattern - What to return on error
        log_errors: Whether to log errors (Graceful Degradation)
        suppress_errors: Whether to suppress errors or re-raise
        retry_count: Number of retry attempts
        retry_delay: Base delay between retries (exponential backoff)
    
    Returns:
        Decorated function that never crashes
    """
    
    def decorator(func: F) -> F:
        
        @functools.wraps(func)  # Preserves function name and metadata
        def wrapper(*args, **kwargs) -> Any:
            attempts = 0
            max_attempts = 1 + retry_count
            func_name = getattr(func, '__name__', 'unknown_function')
            
            while attempts < max_attempts:
                attempts += 1
                current_delay = retry_delay * (2 ** (attempts - 1))  # Exponential backoff
                
                try:
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Validate result with Null Object Pattern
                    if result is None and default_return is not None:
                        if log_errors and logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Function {func_name} returned None, using default")
                        return default_return
                    
                    # Success - log if retried
                    if attempts > 1 and log_errors:
                        logger.info(f"Function {func_name} succeeded on attempt {attempts}")
                    
                    return result
                    
                except Exception as e:
                    # Log error if enabled
                    if log_errors:
                        log_level = logging.ERROR if attempts == max_attempts else logging.WARNING
                        
                        # Build context info safely using getattr()
                        context_parts = []
                        
                        # Add class name if method
                        if args and len(args) > 0:
                            first_arg = args[0]
                            class_name = getattr(
                                getattr(first_arg, '__class__', type(first_arg)), 
                                '__name__', 
                                'unknown_class'
                            )
                            context_parts.append(f"Class: {class_name}")
                        
                        # Add function name
                        context_parts.append(f"Function: {func_name}")
                        
                        # Add attempt info
                        context_parts.append(f"Attempt: {attempts}/{max_attempts}")
                        
                        context = ", ".join(context_parts)
                        
                        logger.log(
                            log_level,
                            f"{context} - Error: {type(e).__name__}: {str(e)[:200]}"
                        )
                        
                        # Full traceback at debug level
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Traceback for {func_name}:\n{traceback.format_exc()}")
                    
                    # If this was the last attempt
                    if attempts == max_attempts:
                        if suppress_errors:
                            # Return default value (Null Object Pattern)
                            return default_return
                        else:
                            # Re-raise with additional context
                            error_msg = f"Failed after {max_attempts} attempts: {str(e)}"
                            raise type(e)(error_msg) from e
                    
                    # Wait before retry
                    if attempts < max_attempts:
                        time.sleep(current_delay)
            
            # Should never reach here, but defensive coding
            return default_return
        
        return cast(F, wrapper)
    
    return decorator


def handle_gracefully_method(
    default_return: Any = None,
    log_errors: bool = True,
    suppress_errors: bool = True,
    include_context: bool = True
) -> Callable[[F], F]:
    """
    Bulletproof decorator for class methods with enhanced context
    
    Args:
        default_return: Null Object Pattern default
        log_errors: Enable error logging
        suppress_errors: Suppress or re-raise errors
        include_context: Include method context in logs
    
    Returns:
        Decorated method
    """
    
    def decorator(func: F) -> F:
        
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> Any:
            func_name = getattr(func, '__name__', 'unknown_method')
            
            try:
                return func(self, *args, **kwargs)
                
            except Exception as e:
                if log_errors:
                    # Use getattr() for safe attribute access
                    class_name = getattr(
                        getattr(self, '__class__', type(self)), 
                        '__name__', 
                        'UnknownClass'
                    )
                    
                    # Build error message
                    error_parts = [f"Error in {class_name}.{func_name}: {type(e).__name__}: {str(e)[:200]}"]
                    
                    if include_context:
                        # Safely extract context
                        context_info = []
                        
                        # Add instance info
                        try:
                            instance_repr = repr(self)[:100]
                            context_info.append(f"Instance: {instance_repr}")
                        except Exception:
                            pass
                        
                        # Add args info
                        if args:
                            context_info.append(f"Args count: {len(args)}")
                        
                        # Add kwargs info
                        if kwargs:
                            kwargs_keys = list(kwargs.keys())
                            context_info.append(f"Kwargs keys: {kwargs_keys}")
                        
                        if context_info:
                            error_parts.append(f"Context: {'; '.join(context_info)}")
                    
                    logger.error("\n".join(error_parts))
                
                if suppress_errors:
                    return default_return
                else:
                    raise
        
        return cast(F, wrapper)
    
    return decorator


class BulletproofDecorator:
    """
    Base class for all bulletproof decorators
    Implements all defensive coding patterns
    """
    
    @staticmethod
    def safe_execute(
        func: Callable[..., T],
        *args,
        default: Any = None,
        log_prefix: str = "",
        max_retries: int = 1,
        **kwargs
    ) -> Union[T, Any]:
        """
        Ultimate safe execution with all defensive patterns
        
        Args:
            func: Function to execute safely
            default: Default value if execution fails (Null Object Pattern)
            log_prefix: Prefix for log messages
            max_retries: Number of retry attempts
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Function result or default value
        """
        func_name = getattr(func, '__name__', 'unknown_function')
        
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                
                # Validate result with Null Object Pattern
                if result is None and default is not None:
                    logger.debug(f"{log_prefix}Function {func_name} returned None, using default")
                    return default
                
                # Log success on retry
                if attempt > 0:
                    logger.info(f"{log_prefix}Function {func_name} succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                # Graceful Degradation: Log error but don't crash immediately
                if attempt == max_retries - 1:
                    logger.error(
                        f"{log_prefix}Safe execute failed for {func_name} "
                        f"after {max_retries} attempts: {type(e).__name__}: {e}"
                    )
                    
                    # Return default value (Null Object Pattern)
                    return default
                else:
                    logger.warning(
                        f"{log_prefix}Attempt {attempt + 1} failed for {func_name}: "
                        f"{type(e).__name__}: {e}"
                    )
                    
                    # Wait before retry
                    time.sleep(0.1 * (2 ** attempt))
        
        # Should never reach here
        return default
    
    @staticmethod
    def retry_on_failure(
        func: Callable[..., T],
        max_retries: int = 3,
        delay: float = 0.1,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,),
        default: Any = None,
        log_retries: bool = True
    ) -> Callable[..., Union[T, Any]]:
        """
        Create a retry wrapper for any function
        
        Args:
            func: Function to wrap with retry logic
            max_retries: Maximum number of retry attempts
            delay: Initial delay between retries
            backoff: Multiplier for delay
            exceptions: Exceptions to catch and retry
            default: Default value if all retries fail
            log_retries: Whether to log retry attempts
        
        Returns:
            Wrapped function with retry logic
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            mtries, mdelay = max_retries, delay
            func_name = getattr(func, '__name__', 'unknown_function')
            
            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    mtries -= 1
                    
                    if mtries == 0:
                        if log_retries:
                            logger.error(
                                f"All {max_retries} retries failed for {func_name}: "
                                f"{type(e).__name__}: {e}"
                            )
                        return default
                    
                    if log_retries:
                        logger.warning(
                            f"Retry {max_retries - mtries}/{max_retries} for "
                            f"{func_name}: {type(e).__name__}: {e}"
                        )
                    
                    time.sleep(mdelay)
                    mdelay *= backoff
            
            return default
        
        return wrapper
    
    @staticmethod
    def timeout(
        timeout_seconds: float = 30.0,
        default: Any = None
    ) -> Callable[[Callable[..., T]], Callable[..., Union[T, Any]]]:
        """
        Timeout decorator (requires signal module, Unix only)
        """
        def decorator(func: Callable[..., T]) -> Callable[..., Union[T, Any]]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
                
                # Set the timeout handler
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(timeout_seconds))
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except TimeoutError:
                    logger.error(f"Function {func.__name__} timed out")
                    return default
                finally:
                    # Cancel alarm
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            
            return wrapper
        
        return decorator


# ============ USAGE EXAMPLES ============

# Example 1: Cache with defensive coding
@handle_gracefully(default_return={"error": "Service unavailable"})
def get_cached_user_data(user_id: int) -> Dict[str, Any]:
    """
    Get user data with caching and defensive coding
    Perfect example of dict.get() usage
    """
    cache_key = CacheManager.generate_key("user_data", user_id)
    
    # Try cache first
    cached = CacheManager.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for user {user_id}")
        return cached
    
    # Fetch from source (with dict.get() for safety)
    raw_data = fetch_from_source(user_id)  # Hypothetical function
    
    # Process with defensive coding
    if not isinstance(raw_data, dict):
        raise ValueError("Invalid data format")
    
    # Use dict.get() for all field accesses
    processed_data = {
        'id': user_id,
        'name': raw_data.get('name', 'Unknown User'),
        'email': raw_data.get('email', ''),
        'status': raw_data.get('status', 'inactive'),
        'metadata': raw_data.get('metadata', {}),  # Nested dict.get()
        'last_login': raw_data.get('last_login'),
        'cached_at': datetime.now().isoformat()
    }
    
    # Clean None values
    processed_data = {k: v for k, v in processed_data.items() if v is not None}
    
    # Cache the result
    CacheManager.set(cache_key, processed_data, timeout=600)
    
    return processed_data


# Example 2: Class with comprehensive defensive patterns
class UserService:
    """
    Service class with bulletproof method decorators
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.cache_prefix = f"user_{user_id}"
    
    @handle_gracefully_method(default_return=[], log_errors=True)
    def get_user_devices(self) -> List[Dict[str, Any]]:
        """
        Get user devices with safe attribute access using getattr()
        """
        # Hypothetical database query
        devices = self._fetch_devices_from_db()
        
        result = []
        for device in devices:
            # Safe attribute access with getattr()
            device_info = {
                'id': getattr(device, 'id', 0),
                'name': getattr(device, 'name', 'Unknown Device'),
                'type': getattr(device, 'device_type', 'unknown'),
                'status': getattr(device, 'status', 'inactive'),
                'last_seen': getattr(device, 'last_seen'),
                # Optional fields - could be None
                'ip_address': getattr(device, 'ip_address', None),
                'user_agent': getattr(device, 'user_agent', None)
            }
            
            # Clean None values
            device_info = {k: v for k, v in device_info.items() if v is not None}
            result.append(device_info)
        
        return result
    
    @handle_gracefully_method(default_return={})
    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get user profile with defensive coding
        """
        cache_key = CacheManager.generate_key(f"{self.cache_prefix}_profile")
        
        # Try cache
        cached = CacheManager.get(cache_key)
        if cached:
            return cached
        
        # Fetch and process
        profile_data = self._fetch_profile()
        
        if not isinstance(profile_data, dict):
            return {}
        
        # Process with dict.get()
        processed = {
            'user_id': self.user_id,
            'username': profile_data.get('username', ''),
            'full_name': profile_data.get('full_name', ''),
            'email': profile_data.get('email', ''),
            'phone': profile_data.get('phone'),
            'address': profile_data.get('address', {}),  # Nested dict
            'preferences': profile_data.get('preferences', {}),
            'stats': {
                'login_count': profile_data.get('login_count', 0),
                'last_active': profile_data.get('last_active'),
                'created_at': profile_data.get('created_at')
            }
        }
        
        # Cache
        CacheManager.set(cache_key, processed, timeout=300)
        
        return processed
    
    def _fetch_devices_from_db(self):
        """Mock method - implement actual database query"""
        # This would be your actual database query
        return []
    
    def _fetch_profile(self):
        """Mock method - implement actual profile fetch"""
        return {}


# Example 3: Admin panel overview (perfect for getattr/dict.get)
@handle_gracefully(default_return={
    "timestamp": datetime.now().isoformat(),
    "error": "Overview generation failed",
    "stats": {},
    "alerts": []
})
def get_admin_overview() -> Dict[str, Any]:
    """
    Admin panel overview with comprehensive defensive coding
    Excellent example of where to use getattr() and dict.get()
    """
    overview = {
        'timestamp': datetime.now().isoformat(),
        'stats': {},
        'alerts': [],
        'system_status': 'unknown',
        'last_updated': None
    }
    
    try:
        # Collect data from multiple sources with defensive coding
        user_stats = BulletproofDecorator.safe_execute(
            get_user_statistics,  # Hypothetical function
            default={'total': 0, 'active': 0, 'new_today': 0}
        )
        
        system_metrics = BulletproofDecorator.safe_execute(
            get_system_metrics,  # Hypothetical function
            default={'cpu': 0.0, 'memory': 0.0, 'disk': 0.0}
        )
        
        security_alerts = BulletproofDecorator.safe_execute(
            get_security_alerts,  # Hypothetical function
            default=[]
        )
        
        # Use dict.get() for safe dictionary access
        overview['stats'] = {
            'users': {
                'total': user_stats.get('total', 0),
                'active': user_stats.get('active', 0),
                'new_today': user_stats.get('new_today', 0),
                'growth_rate': user_stats.get('growth_rate', 0.0)
            },
            'system': {
                'cpu_usage': system_metrics.get('cpu', 0.0),
                'memory_usage': system_metrics.get('memory', 0.0),
                'disk_usage': system_metrics.get('disk', 0.0),
                'uptime_days': system_metrics.get('uptime_days', 0)
            },
            'performance': {
                'response_time_ms': system_metrics.get('response_time', 0.0),
                'requests_per_second': system_metrics.get('rps', 0.0),
                'error_rate': system_metrics.get('error_rate', 0.0)
            }
        }
        
        # Process alerts with defensive coding
        if isinstance(security_alerts, list):
            # Limit and format alerts
            overview['alerts'] = [
                {
                    'id': alert.get('id', f"alert_{i}"),
                    'type': alert.get('type', 'unknown'),
                    'severity': alert.get('severity', 'medium'),
                    'message': alert.get('message', '')[:100],
                    'timestamp': alert.get('timestamp')
                }
                for i, alert in enumerate(security_alerts[:10])  # Limit to 10
                if isinstance(alert, dict)
            ]
        
        # Determine system status using dict.get()
        cpu = overview['stats']['system'].get('cpu_usage', 0.0)
        memory = overview['stats']['system'].get('memory_usage', 0.0)
        error_rate = overview['stats']['performance'].get('error_rate', 0.0)
        
        if cpu > 90 or memory > 90 or error_rate > 10:
            overview['system_status'] = 'critical'
        elif cpu > 70 or memory > 70 or error_rate > 5:
            overview['system_status'] = 'warning'
        else:
            overview['system_status'] = 'healthy'
        
        overview['last_updated'] = datetime.now().isoformat()
        
    except Exception as e:
        # Graceful Degradation: Record error but don't crash
        logger.error(f"Admin overview generation failed: {e}")
        overview['error'] = str(e)[:200]
        overview['system_status'] = 'error'
    
    return overview


# Example 4: API response processing
def process_api_response(
    api_response: Dict[str, Any],
    required_fields: List[str] = None
) -> Dict[str, Any]:
    """
    Process API response with comprehensive defensive coding
    Excellent example of dict.get() and validation
    """
    # Null Object Pattern: Default structure
    result = {
        'success': False,
        'data': {},
        'errors': [],
        'warnings': [],
        'metadata': {},
        'processed_at': datetime.now().isoformat(),
        'raw_response': None  # Store raw for debugging
    }
    
    try:
        # Store raw response (limited size)
        if isinstance(api_response, dict):
            result['raw_response'] = {k: v for k, v in list(api_response.items())[:5]}  # First 5 items
        
        # Validate input
        if not isinstance(api_response, dict):
            result['errors'].append('Invalid API response format')
            return result
        
        # Extract with dict.get()
        status = api_response.get('status', 'error')
        data = api_response.get('data', {})
        metadata = api_response.get('metadata', {})
        errors = api_response.get('errors', [])
        
        # Check status
        if status != 'success':
            result['errors'].extend(
                [str(e) for e in errors] if isinstance(errors, list) else [str(errors)]
            )
            return result
        
        # Validate required fields
        if required_fields:
            missing_fields = [
                field for field in required_fields 
                if field not in data or data.get(field) is None
            ]
            
            if missing_fields:
                result['warnings'].append(f"Missing fields: {missing_fields}")
        
        # Process data with dict.get()
        processed_data = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None:
                    continue  # Skip None values
                
                if isinstance(value, dict):
                    # Recursively process nested dicts
                    processed_data[key] = {
                        k: v for k, v in value.items() 
                        if v is not None
                    }
                elif isinstance(value, list):
                    # Process list items
                    processed_data[key] = value
                else:
                    processed_data[key] = value
        
        # Build result
        result.update({
            'success': True,
            'data': processed_data,
            'metadata': {
                'response_time': metadata.get('response_time_ms', 0),
                'api_version': metadata.get('version', '1.0'),
                'source': metadata.get('source', 'unknown'),
                'request_id': metadata.get('request_id')
            }
        })
        
    except Exception as e:
        # Graceful Degradation
        logger.error(f"API response processing error: {e}")
        result['errors'].append(f'Processing error: {str(e)}')
    
    return result


# Example 5: Configuration loader with defensive patterns
@handle_gracefully(default_return={})
def load_configuration(config_path: str) -> Dict[str, Any]:
    """
    Load configuration with comprehensive error handling
    """
    import os
    import yaml  # Requires PyYAML
    
    # Default config
    default_config = {
        'database': {
            'host': 'localhost',
            'port': 5432,
            'name': 'default_db'
        },
        'cache': {
            'timeout': 300,
            'max_entries': 1000
        },
        'security': {
            'max_login_attempts': 5,
            'session_timeout': 3600
        }
    }
    
    try:
        # Check if file exists
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return default_config
        
        # Load file
        with open(config_path, 'r') as f:
            loaded_config = yaml.safe_load(f)
        
        if not isinstance(loaded_config, dict):
            logger.error(f"Invalid config format in {config_path}")
            return default_config
        
        # Merge with defaults using dict.get()
        merged = default_config.copy()
        
        for section, section_config in loaded_config.items():
            if isinstance(section_config, dict) and section in merged:
                # Merge section configs
                merged[section].update(section_config)
            elif section not in merged:
                # Add new section
                merged[section] = section_config
        
        return merged
        
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in {config_path}: {e}")
        return default_config
    except Exception as e:
        logger.error(f"Config loading failed: {e}")
        return default_config


# Export everything
__all__ = [
    'CacheManager',
    'handle_gracefully',
    'handle_gracefully_method',
    'BulletproofDecorator',
    'get_admin_overview',
    'process_api_response',
    'load_configuration',
    'UserService',
    'get_cached_user_data'
]