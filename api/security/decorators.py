# api/security/decorators.py
from functools import wraps
from django.utils.decorators import method_decorator
from django.db import DatabaseError
from django.core.cache import cache
from typing import Callable, Any, Dict, Optional, Union
import logging
import time
import functools

logger = logging.getLogger(__name__)


def safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    """
    Bulletproof attribute access using getattr with defensive coding
    """
    try:
        return getattr(obj, attr, default)
    except Exception as e:
        logger.debug(f"Safe getattr failed for {attr} on {type(obj)}: {e}")
        return default


def safe_dict_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Bulletproof dictionary access using dict.get with defensive coding
    """
    try:
        if not isinstance(data, dict):
            logger.debug(f"Expected dict but got {type(data)}")
            return default
        return data.get(key, default)
    except Exception as e:
        logger.debug(f"Safe dict.get failed for key {key}: {e}")
        return default


class BulletproofDecorator:
    """
    Base class for all bulletproof decorators
    Implements all defensive coding patterns
    """
    
    @staticmethod
    def log_error(func_name: str, error: Exception) -> None:
        """Graceful error logging"""
        try:
            logger.error(f"Error in {func_name}: {error}", exc_info=True)
        except Exception:
            # Even logging can fail - ultimate graceful degradation
            print(f"Critical: Failed to log error in {func_name}: {error}")


def audit_action(action_type: str, 
                 log_errors: bool = True,
                 default_response: Any = None) -> Callable:
    """
    Bulletproof audit action decorator with all defensive patterns
    
    Args:
        action_type: Type of action being audited
        log_errors: Whether to log errors (Graceful Degradation)
        default_response: What to return if everything fails (Null Object Pattern)
    """
    
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        def wrapper(request, *args, **kwargs) -> Any:
            # Null Object Pattern: Default values
            audit_data = {
                'user': None,
                'action_type': action_type,
                'ip_address': '',
                'user_agent': '',
                'metadata': {},
                'success': False,
                'errors': []
            }
            
            try:
                # 1. Safe request attribute access using getattr
                audit_data['user'] = safe_getattr(request, 'user')
                
                # Check if user is authenticated safely
                is_authenticated = False
                try:
                    if audit_data['user']:
                        is_authenticated = getattr(audit_data['user'], 'is_authenticated', False)
                except Exception:
                    is_authenticated = False
                
                # 2. Get IP address with defensive coding
                audit_data['ip_address'] = get_client_ip_safe(request)
                
                # 3. Get user agent using safe_dict_get on META (which is a dict)
                audit_data['user_agent'] = safe_dict_get(
                    safe_getattr(request, 'META', {}),
                    'HTTP_USER_AGENT',
                    ''
                )
                
                # 4. Execute the original function
                start_time = time.time()
                response = func(request, *args, **kwargs)
                execution_time = time.time() - start_time
                
                # 5. Build metadata safely
                metadata = {
                    'path': safe_getattr(request, 'path', ''),
                    'method': safe_getattr(request, 'method', ''),
                    'execution_time': execution_time,
                    'args_count': len(args),
                    'kwargs_count': len(kwargs)
                }
                
                # Try to get status code safely
                try:
                    if hasattr(response, 'status_code'):
                        metadata['status_code'] = response.status_code
                    elif isinstance(response, dict):
                        metadata['status_code'] = response.get('status', 200)
                    else:
                        metadata['status_code'] = 200
                except Exception:
                    metadata['status_code'] = 200
                
                audit_data['metadata'] = metadata
                audit_data['success'] = True
                
                # 6. Log to database (with graceful degradation)
                try:
                    from .models import AuditLog
                    
                    AuditLog.objects.create(
                        user=audit_data['user'] if is_authenticated else None,
                        action_type=audit_data['action_type'],
                        ip_address=audit_data['ip_address'],
                        user_agent=audit_data['user_agent'],
                        metadata=audit_data['metadata'],
                        success=audit_data['success']
                    )
                    
                except ImportError:
                    logger.warning("AuditLog model not available")
                except DatabaseError as db_error:
                    logger.error(f"Database error logging audit: {db_error}")
                    # Cache the audit data if DB fails
                    cache_key = f'failed_audit:{action_type}:{int(time.time())}'
                    try:
                        cache.set(cache_key, audit_data, timeout=3600)
                    except Exception:
                        pass
                except Exception as log_error:
                    if log_errors:
                        BulletproofDecorator.log_error('audit_action', log_error)
                
                return response
                
            except Exception as e:
                # Graceful Degradation: Execute function even if audit fails
                if log_errors:
                    BulletproofDecorator.log_error('audit_action', e)
                
                audit_data['errors'].append(str(e))
                
                # Try to execute original function anyway
                try:
                    return func(request, *args, **kwargs)
                except Exception as func_error:
                    if log_errors:
                        logger.error(f"Original function also failed: {func_error}")
                    
                    # Null Object Pattern: Return default response if everything fails
                    if default_response is not None:
                        return default_response
                    
                    # Create a safe error response
                    return {
                        'error': 'Request processing failed',
                        'action': action_type,
                        'timestamp': time.time(),
                        'success': False
                    }
        
        return wrapper
    
    return decorator


def method_audit_action(action_type: str, 
                        log_errors: bool = True,
                        fallback_to_super: bool = True) -> Callable:
    """
    Bulletproof method decorator for class-based views
    
    Args:
        action_type: Type of action
        log_errors: Whether to log errors
        fallback_to_super: Whether to call super method on failure
    """
    
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        def wrapper(self, request, *args, **kwargs) -> Any:
            # Default audit data (Null Object Pattern)
            audit_data = {
                'view_class': safe_getattr(self, '__class__', type(self)).__name__,
                'method_name': func.__name__,
                'action_type': action_type,
                'success': False,
                'errors': []
            }
            
            try:
                # Safe attribute access for view information
                audit_data['view_name'] = safe_getattr(self, 'get_view_name', lambda: 'Unknown')()
                audit_data['serializer_class'] = safe_getattr(
                    safe_getattr(self, 'get_serializer_class', lambda: None)(),
                    '__name__',
                    'Unknown'
                )
                
                # Get request data safely
                user = safe_getattr(request, 'user', None)
                ip_address = get_client_ip_safe(request)
                user_agent = safe_dict_get(
                    safe_getattr(request, 'META', {}),
                    'HTTP_USER_AGENT',
                    ''
                )
                
                # Execute original method
                start_time = time.time()
                response = func(self, request, *args, **kwargs)
                execution_time = time.time() - start_time
                
                # Build metadata
                metadata = {
                    'view': audit_data['view_class'],
                    'method': audit_data['method_name'],
                    'path': safe_getattr(request, 'path', ''),
                    'request_method': safe_getattr(request, 'method', ''),
                    'execution_time': execution_time,
                    'user_authenticated': safe_getattr(user, 'is_authenticated', False) if user else False
                }
                
                # Try to get additional response info
                try:
                    if hasattr(response, 'status_code'):
                        metadata['status_code'] = response.status_code
                    elif hasattr(response, 'data'):
                        metadata['has_data'] = True
                        metadata['data_type'] = type(response.data).__name__
                except Exception:
                    pass
                
                audit_data['metadata'] = metadata
                audit_data['success'] = True
                
                # Log to database with defensive coding
                try:
                    from .models import AuditLog
                    
                    AuditLog.objects.create(
                        user=user if user and getattr(user, 'is_authenticated', False) else None,
                        action_type=f"{action_type}_{audit_data['method_name'].upper()}",
                        ip_address=ip_address,
                        user_agent=user_agent,
                        metadata=audit_data['metadata'],
                        success=True
                    )
                    
                except Exception as log_error:
                    if log_errors:
                        BulletproofDecorator.log_error('method_audit_action', log_error)
                    # Cache failed audit
                    cache_failed_audit(audit_data)
                
                return response
                
            except Exception as e:
                # Graceful Degradation
                if log_errors:
                    BulletproofDecorator.log_error('method_audit_action', e)
                
                audit_data['errors'].append(str(e))
                
                # Try fallback strategies
                try:
                    # Strategy 1: Try original function again
                    return func(self, request, *args, **kwargs)
                except Exception:
                    try:
                        if fallback_to_super:
                            # Strategy 2: Call super method
                            view_class = safe_getattr(self, '__class__', None)
                            if view_class and hasattr(view_class, '__bases__'):
                                for base in view_class.__bases__:
                                    if hasattr(base, func.__name__):
                                        super_method = getattr(super(view_class, self), func.__name__)
                                        return super_method(request, *args, **kwargs)
                    except Exception:
                        pass
                    
                    # Strategy 3: Return safe error response
                    return create_safe_error_response(
                        action_type=action_type,
                        view_class=audit_data['view_class'],
                        error=e
                    )
        
        return wrapper
    
    return decorator


def rate_limit(max_requests: int = 100, 
               time_window: int = 3600,
               identifier_func: Optional[Callable] = None) -> Callable:
    """
    Bulletproof rate limiting decorator
    """
    
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        def wrapper(request, *args, **kwargs) -> Any:
            # Null Object Pattern: Default rate limit data
            rate_data = {
                'limited': False,
                'remaining': max_requests,
                'reset_time': time.time() + time_window,
                'identifier': 'unknown'
            }
            
            try:
                # Get identifier safely
                if identifier_func:
                    try:
                        rate_data['identifier'] = identifier_func(request)
                    except Exception:
                        rate_data['identifier'] = get_client_ip_safe(request)
                else:
                    rate_data['identifier'] = get_client_ip_safe(request)
                
                # Create cache key
                cache_key = f'rate_limit:{rate_data["identifier"]}:{func.__name__}'
                
                # Get current count safely
                try:
                    current_count = cache.get(cache_key, 0)
                    if not isinstance(current_count, int):
                        current_count = 0
                except Exception:
                    current_count = 0
                
                # Check if rate limited
                if current_count >= max_requests:
                    rate_data['limited'] = True
                    rate_data['remaining'] = 0
                    
                    # Return rate limit response
                    return {
                        'error': 'Rate limit exceeded',
                        'retry_after': int(rate_data['reset_time'] - time.time()),
                        'limit': max_requests,
                        'window': time_window,
                        'identifier': rate_data['identifier'][:10] + '...' if len(rate_data['identifier']) > 10 else rate_data['identifier']
                    }
                
                # Increment count safely
                try:
                    cache.set(cache_key, current_count + 1, timeout=time_window)
                except Exception:
                    pass  # Graceful degradation - skip rate limiting if cache fails
                
                rate_data['remaining'] = max_requests - (current_count + 1)
                
                # Add rate limit headers
                response = func(request, *args, **kwargs)
                
                # Try to add headers if response is HttpResponse
                try:
                    if hasattr(response, '__setitem__'):  # Check if it's a dict-like response
                        response['X-RateLimit-Limit'] = str(max_requests)
                        response['X-RateLimit-Remaining'] = str(rate_data['remaining'])
                        response['X-RateLimit-Reset'] = str(int(rate_data['reset_time']))
                    elif hasattr(response, '__setitem__'):  # For Django HttpResponse
                        response['X-RateLimit-Limit'] = str(max_requests)
                        response['X-RateLimit-Remaining'] = str(rate_data['remaining'])
                        response['X-RateLimit-Reset'] = str(int(rate_data['reset_time']))
                except Exception:
                    pass  # Graceful degradation - headers not critical
                
                return response
                
            except Exception as e:
                # If rate limiting fails, still execute the function
                BulletproofDecorator.log_error('rate_limit', e)
                return func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def cache_response(timeout: int = 300,
                   key_func: Optional[Callable] = None,
                   vary_on_headers: Optional[list] = None) -> Callable:
    """
    Bulletproof response caching decorator
    """
    
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        def wrapper(request, *args, **kwargs) -> Any:
            # Null Object Pattern: Default cache data
            cache_info = {
                'cached': False,
                'cache_key': None,
                'hit': False
            }
            
            try:
                # Generate cache key safely
                if key_func:
                    try:
                        cache_key = key_func(request, *args, **kwargs)
                    except Exception:
                        cache_key = default_cache_key(request, func.__name__)
                else:
                    cache_key = default_cache_key(request, func.__name__)
                
                # Add header variations
                if vary_on_headers:
                    try:
                        header_hash = hash(tuple(
                            safe_dict_get(request.META, f'HTTP_{hdr.upper().replace("-", "_")}', '')
                            for hdr in vary_on_headers
                        ))
                        cache_key = f"{cache_key}:headers:{header_hash}"
                    except Exception:
                        pass
                
                cache_info['cache_key'] = cache_key
                
                # Try to get from cache
                try:
                    cached_response = cache.get(cache_key)
                    if cached_response is not None:
                        cache_info['cached'] = True
                        cache_info['hit'] = True
                        return cached_response
                except Exception:
                    pass  # Cache failed, proceed without caching
                
                # Execute function
                response = func(request, *args, **kwargs)
                
                # Try to cache the response
                try:
                    # Only cache if response is successful
                    if (hasattr(response, 'status_code') and response.status_code == 200) or \
                       (isinstance(response, dict) and response.get('success', True)):
                        cache.set(cache_key, response, timeout=timeout)
                        cache_info['cached'] = True
                except Exception:
                    pass  # Graceful degradation - caching not critical
                
                # Add cache info to response if possible
                try:
                    if isinstance(response, dict):
                        response['_cache'] = cache_info
                except Exception:
                    pass
                
                return response
                
            except Exception as e:
                BulletproofDecorator.log_error('cache_response', e)
                # Execute without caching
                return func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def validate_request(required_params: Optional[list] = None,
                     allowed_methods: Optional[list] = None,
                     schema_validator: Optional[Callable] = None) -> Callable:
    """
    Bulletproof request validation decorator
    """
    
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        def wrapper(request, *args, **kwargs) -> Any:
            # Default validation result
            validation = {
                'valid': True,
                'errors': [],
                'missing_params': [],
                'invalid_method': False
            }
            
            try:
                # Validate HTTP method
                if allowed_methods:
                    request_method = safe_getattr(request, 'method', '').upper()
                    if request_method not in [m.upper() for m in allowed_methods]:
                        validation['valid'] = False
                        validation['invalid_method'] = True
                        validation['errors'].append(
                            f"Method {request_method} not allowed. Allowed: {allowed_methods}"
                        )
                
                # Validate required parameters
                if required_params and validation['valid']:
                    request_data = get_request_data_safe(request)
                    
                    for param in required_params:
                        if param not in request_data:
                            validation['missing_params'].append(param)
                    
                    if validation['missing_params']:
                        validation['valid'] = False
                        validation['errors'].append(
                            f"Missing parameters: {validation['missing_params']}"
                        )
                
                # Custom schema validation
                if schema_validator and validation['valid']:
                    try:
                        request_data = get_request_data_safe(request)
                        is_valid, schema_errors = schema_validator(request_data)
                        if not is_valid:
                            validation['valid'] = False
                            validation['errors'].extend(schema_errors)
                    except Exception as e:
                        BulletproofDecorator.log_error('schema_validator', e)
                        # Graceful degradation - skip schema validation on error
                
                # Return error response if validation failed
                if not validation['valid']:
                    return {
                        'error': 'Request validation failed',
                        'validation_errors': validation['errors'],
                        'missing_params': validation['missing_params'],
                        'allowed_methods': allowed_methods,
                        'success': False
                    }
                
                # Execute function if validation passed
                return func(request, *args, **kwargs)
                
            except Exception as e:
                BulletproofDecorator.log_error('validate_request', e)
                # Return validation error even on decorator failure
                return {
                    'error': 'Validation system error',
                    'validation_errors': [str(e)],
                    'success': False
                }
        
        return wrapper
    
    return decorator


# ============ HELPER FUNCTIONS ============

def get_client_ip_safe(request) -> str:
    """
    Bulletproof IP address extraction
    """
    try:
        # Try X-Forwarded-For first
        x_forwarded_for = safe_dict_get(
            safe_getattr(request, 'META', {}),
            'HTTP_X_FORWARDED_FOR'
        )
        if x_forwarded_for:
            # Take the first IP in the list
            ips = str(x_forwarded_for).split(',')
            return ips[0].strip() if ips else ''
        
        # Fall back to REMOTE_ADDR
        remote_addr = safe_dict_get(
            safe_getattr(request, 'META', {}),
            'REMOTE_ADDR',
            ''
        )
        return str(remote_addr)
        
    except Exception as e:
        logger.debug(f"Failed to get client IP: {e}")
        return '0.0.0.0'  # Null Object Pattern


def get_request_data_safe(request) -> Dict[str, Any]:
    """
    Bulletproof request data extraction
    """
    try:
        # Try different request data locations
        if hasattr(request, 'data'):
            return safe_getattr(request, 'data', {})
        elif hasattr(request, 'POST'):
            post_data = safe_getattr(request, 'POST', {})
            if post_data:
                return dict(post_data)
        elif hasattr(request, 'GET'):
            get_data = safe_getattr(request, 'GET', {})
            if get_data:
                return dict(get_data)
        
        # Try to parse JSON body
        try:
            import json
            body = safe_getattr(request, 'body', b'{}')
            if body:
                return json.loads(body)
        except Exception:
            pass
        
        return {}
        
    except Exception as e:
        logger.debug(f"Failed to get request data: {e}")
        return {}  # Null Object Pattern


def default_cache_key(request, func_name: str) -> str:
    """
    Generate default cache key
    """
    try:
        ip = get_client_ip_safe(request)
        path = safe_getattr(request, 'path', '')
        method = safe_getattr(request, 'method', '')
        user_id = ''
        
        user = safe_getattr(request, 'user', None)
        if user and safe_getattr(user, 'is_authenticated', False):
            user_id = str(safe_getattr(user, 'id', ''))
        
        return f"cache:{func_name}:{user_id}:{ip}:{path}:{method}"
        
    except Exception:
        return f"cache:{func_name}:{int(time.time())}"


def cache_failed_audit(audit_data: Dict[str, Any]) -> None:
    """
    Cache failed audit data for later recovery
    """
    try:
        cache_key = f'failed_audit:{int(time.time())}:{audit_data.get("action_type", "unknown")}'
        cache.set(cache_key, audit_data, timeout=86400)  # 24 hours
    except Exception:
        pass  # Ultimate graceful degradation


def create_safe_error_response(action_type: str, 
                               view_class: str, 
                               error: Exception) -> Dict[str, Any]:
    """
    Create a safe error response (Null Object Pattern)
    """
    return {
        'success': False,
        'error': 'Request processing failed',
        'action_type': action_type,
        'view_class': view_class,
        'error_message': str(error) if error else 'Unknown error',
        'timestamp': time.time(),
        'recovery_suggestion': 'Please try again or contact support',
        'support_code': f"ERR_{int(time.time())}_{hash(action_type) % 1000}"
    }


# ============ USAGE EXAMPLES ============

"""
Example usage in views.py:

1. Function-based view:
@audit_action('USER_LOGIN', log_errors=True)
def login_view(request):
    # Your login logic
    pass

2. Method-based view:
class UserViewSet(viewsets.ModelViewSet):
    
    @method_audit_action('USER_LIST')
    def list(self, request):
        return super().list(request)
    
    @rate_limit(max_requests=10, time_window=60)
    @cache_response(timeout=60)
    @validate_request(allowed_methods=['GET'])
    def public_api(self, request):
        return {'data': 'public'}

3. Combined decorators:
@audit_action('PAYMENT_PROCESS')
@rate_limit(max_requests=5, time_window=3600)
@validate_request(required_params=['amount', 'currency'])
def process_payment(request):
    # Payment logic
    pass
"""


# api/security/decorators.py - নিচের কোড যোগ করুন

def handle_gracefully(default_response: Any = None,
                      log_errors: bool = True,
                      retry_count: int = 0) -> Callable:
    """
    Ultimate Graceful Degradation Decorator
    Never lets any exception bubble up
    
    Args:
        default_response: What to return if all attempts fail (Null Object Pattern)
        log_errors: Whether to log errors
        retry_count: Number of retry attempts
    """
    
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempts = 0
            max_attempts = 1 + retry_count  # Original + retries
            
            while attempts < max_attempts:
                attempts += 1
                
                try:
                    # Try to execute the function
                    result = func(*args, **kwargs)
                    
                    # Validate result is not None if default_response provided
                    if result is None and default_response is not None:
                        logger.warning(f"Function {func.__name__} returned None, using default")
                        return default_response
                    
                    return result
                    
                except Exception as e:
                    # Log error if enabled
                    if log_errors:
                        logger.error(
                            f"Attempt {attempts}/{max_attempts} failed for {func.__name__}: {e}",
                            exc_info=True if attempts == max_attempts else False
                        )
                    
                    # If this was the last attempt
                    if attempts == max_attempts:
                        # Log final failure
                        if log_errors:
                            logger.critical(
                                f"All attempts failed for {func.__name__}. "
                                f"Args: {args}, Kwargs: {kwargs.keys() if kwargs else 'none'}"
                            )
                        
                        # Return default response or create a safe one
                        if default_response is not None:
                            return default_response
                        
                        # Create a bulletproof error response
                        return create_graceful_error_response(
                            func_name=func.__name__,
                            error=e,
                            attempts=attempts
                        )
                    
                    # Wait before retry (exponential backoff)
                    if attempts < max_attempts:
                        wait_time = min(2 ** (attempts - 1), 10)  # Max 10 seconds
                        time.sleep(wait_time)
            
            # Should never reach here, but just in case
            return create_graceful_error_response(
                func_name=func.__name__,
                error=Exception("Unknown failure"),
                attempts=attempts
            )
        
        return wrapper
    
    return decorator


def handle_gracefully_method(default_response: Any = None,
                             log_errors: bool = True,
                             retry_count: int = 0) -> Callable:
    """
    Graceful degradation decorator for class methods
    """
    
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        def wrapper(self, *args, **kwargs) -> Any:
            attempts = 0
            max_attempts = 1 + retry_count
            
            while attempts < max_attempts:
                attempts += 1
                
                try:
                    result = func(self, *args, **kwargs)
                    
                    # Validate result
                    if result is None and default_response is not None:
                        logger.warning(f"Method {func.__name__} returned None")
                        return default_response
                    
                    return result
                    
                except Exception as e:
                    if log_errors:
                        logger.error(
                            f"Method {func.__name__} attempt {attempts} failed: {e}",
                            exc_info=True if attempts == max_attempts else False
                        )
                    
                    if attempts == max_attempts:
                        # Try to get class name safely
                        class_name = safe_getattr(self, '__class__', type(self)).__name__
                        
                        if log_errors:
                            logger.critical(
                                f"All attempts failed for {class_name}.{func.__name__}"
                            )
                        
                        if default_response is not None:
                            return default_response
                        
                        return create_graceful_error_response(
                            func_name=f"{class_name}.{func.__name__}",
                            error=e,
                            attempts=attempts
                        )
                    
                    # Wait before retry
                    if attempts < max_attempts:
                        wait_time = min(2 ** (attempts - 1), 10)
                        time.sleep(wait_time)
            
            return create_graceful_error_response(
                func_name=func.__name__,
                error=Exception("Method execution failed"),
                attempts=attempts
            )
        
        return wrapper
    
    return decorator


def create_graceful_error_response(func_name: str,
                                   error: Exception,
                                   attempts: int) -> Dict[str, Any]:
    """
    Create a graceful error response (Null Object Pattern)
    """
    error_id = f"ERR_{int(time.time())}_{hash(func_name) % 10000:04d}"
    
    return {
        'success': False,
        'error': 'Operation failed gracefully',
        'function': func_name,
        'error_id': error_id,
        'attempts': attempts,
        'timestamp': time.time(),
        'recoverable': True,
        'suggestion': 'Please try again in a moment',
        'support_info': {
            'error_type': error.__class__.__name__,
            'error_message': str(error)[:100] if str(error) else 'No message'
        }
    }
    
    
   

