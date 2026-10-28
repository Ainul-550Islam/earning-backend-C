"""
Utility functions for alerts app
"""
import json
import hashlib
import hmac
import uuid
import secrets
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.contrib.auth import get_user_model
from typing import Dict, List, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class AlertUtils:
    """General utility functions for alerts"""
    
    @staticmethod
    def generate_alert_id() -> str:
        """Generate unique alert ID"""
        return f"alert_{uuid.uuid4().hex[:16]}"
    
    @staticmethod
    def generate_notification_id() -> str:
        """Generate unique notification ID"""
        return f"notif_{uuid.uuid4().hex[:16]}"
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """Hash sensitive data for logging"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def mask_sensitive_info(value: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """Mask sensitive information"""
        if len(value) <= visible_chars:
            return value
        
        return value[:visible_chars] + mask_char * (len(value) - visible_chars)
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        import re
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:255-len(ext)-1] + '.' + ext
        
        return filename
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024 and i < len(size_names) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    
    @staticmethod
    def is_valid_json(json_string: str) -> bool:
        """Check if string is valid JSON"""
        try:
            json.loads(json_string)
            return True
        except (json.JSONDecodeError, ValueError):
            return False
    
    @staticmethod
    def safe_json_loads(json_string: str) -> Optional[Dict[str, Any]]:
        """Safely load JSON string"""
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, ValueError):
            return None
    
    @staticmethod
    def get_client_ip(request) -> str:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'unknown'
    
    @staticmethod
    def get_user_agent(request) -> str:
        """Get user agent string"""
        return request.META.get('HTTP_USER_AGENT', 'unknown')
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
        """Verify webhook signature"""
        expected_signature = AlertUtils._generate_signature(payload, secret)
        return secrets.compare_digest(expected_signature, signature)
    
    @staticmethod
    def _generate_signature(payload: str, secret: str) -> str:
        """Generate HMAC signature"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()


class TimeUtils:
    """Time-related utility functions"""
    
    @staticmethod
    def now_utc() -> datetime:
        """Get current UTC time"""
        return timezone.now()
    
    @staticmethod
    def utc_to_local(utc_datetime: datetime) -> datetime:
        """Convert UTC to local time"""
        return timezone.localtime(utc_datetime)
    
    @staticmethod
    def local_to_utc(local_datetime: datetime) -> datetime:
        """Convert local time to UTC"""
        return timezone.make_aware(local_datetime, timezone.utc)
    
    @staticmethod
    def format_datetime(dt: datetime, format_type: str = 'iso') -> str:
        """Format datetime"""
        if format_type == 'iso':
            return dt.isoformat()
        elif format_type == 'readable':
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        elif format_type == 'date':
            return dt.strftime('%Y-%m-%d')
        elif format_type == 'time':
            return dt.strftime('%H:%M:%S')
        else:
            return dt.isoformat()
    
    @staticmethod
    def parse_datetime(date_string: str, format_type: str = 'auto') -> Optional[datetime]:
        """Parse datetime string"""
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y'
        ]
        
        if format_type != 'auto':
            formats = [format_type]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def get_time_ago(dt: datetime) -> str:
        """Get human readable time ago string"""
        now = timezone.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return f"{diff.seconds} second{'s' if diff.seconds > 1 else ''} ago"
    
    @staticmethod
    def is_business_hour(dt: datetime) -> bool:
        """Check if datetime is during business hours"""
        hour = dt.hour
        return 9 <= hour <= 17  # 9 AM to 5 PM
    
    @staticmethod
    def add_business_days(dt: datetime, days: int) -> datetime:
        """Add business days to datetime"""
        result = dt
        business_days_added = 0
        
        while business_days_added < days:
            result += timedelta(days=1)
            if result.weekday() < 5:  # Monday-Friday
                business_days_added += 1
        
        return result


class ConfigUtils:
    """Configuration-related utility functions"""
    
    @staticmethod
    def get_setting(key: str, default: Any = None) -> Any:
        """Get setting value with default"""
        return getattr(settings, key, default)
    
    @staticmethod
    def get_alert_config() -> Dict[str, Any]:
        """Get alert configuration"""
        return {
            'default_severity': ConfigUtils.get_setting('ALERT_DEFAULT_SEVERITY', 'medium'),
            'default_cooldown': ConfigUtils.get_setting('ALERT_DEFAULT_COOLDOWN', 30),
            'max_alerts_per_hour': ConfigUtils.get_setting('ALERT_MAX_PER_HOUR', 100),
            'notification_timeout': ConfigUtils.get_setting('ALERT_NOTIFICATION_TIMEOUT', 30),
            'retry_attempts': ConfigUtils.get_setting('ALERT_RETRY_ATTEMPTS', 3),
            'cache_timeout': ConfigUtils.get_setting('ALERT_CACHE_TIMEOUT', 300),
            'webhook_timeout': ConfigUtils.get_setting('ALERT_WEBHOOK_TIMEOUT', 30),
            'webhook_retries': ConfigUtils.get_setting('ALERT_WEBHOOK_RETRIES', 3)
        }
    
    @staticmethod
    def get_pagination_config() -> Dict[str, Any]:
        """Get pagination configuration"""
        return {
            'default_page_size': ConfigUtils.get_setting('PAGINATION_DEFAULT_PAGE_SIZE', 20),
            'max_page_size': ConfigUtils.get_setting('PAGINATION_MAX_PAGE_SIZE', 100),
            'page_size_query_param': ConfigUtils.get_setting('PAGINATION_PAGE_SIZE_PARAM', 'page_size'),
            'page_query_param': ConfigUtils.get_setting('PAGINATION_PAGE_PARAM', 'page')
        }
    
    @staticmethod
    def get_cache_config() -> Dict[str, Any]:
        """Get cache configuration"""
        return {
            'default_timeout': ConfigUtils.get_setting('CACHE_DEFAULT_TIMEOUT', 300),
            'alert_stats_timeout': ConfigUtils.get_setting('CACHE_ALERT_STATS_TIMEOUT', 60),
            'user_prefs_timeout': ConfigUtils.get_setting('CACHE_USER_PREFS_TIMEOUT', 3600),
            'system_health_timeout': ConfigUtils.get_setting('CACHE_SYSTEM_HEALTH_TIMEOUT', 60)
        }
    
    @staticmethod
    def get_security_config() -> Dict[str, Any]:
        """Get security configuration"""
        return {
            'api_key_length': ConfigUtils.get_setting('SECURITY_API_KEY_LENGTH', 32),
            'webhook_secret_length': ConfigUtils.get_setting('SECURITY_WEBHOOK_SECRET_LENGTH', 32),
            'max_login_attempts': ConfigUtils.get_setting('SECURITY_MAX_LOGIN_ATTEMPTS', 5),
            'lockout_duration': ConfigUtils.get_setting('SECURITY_LOCKOUT_DURATION', 300),
            'session_timeout': ConfigUtils.get_setting('SECURITY_SESSION_TIMEOUT', 3600)
        }


class ValidationUtils:
    """Validation utility functions"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        """Validate phone number format"""
        import re
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        return len(digits) >= 10 and len(digits) <= 15
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validate URL format"""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(url))
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            value = str(value)
        
        # Remove HTML tags
        import re
        value = re.sub(r'<[^>]+>', '', value)
        
        # Remove extra whitespace
        value = ' '.join(value.split())
        
        # Truncate if too long
        if len(value) > max_length:
            value = value[:max_length-3] + '...'
        
        return value
    
    @staticmethod
    def validate_json_schema(data: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against JSON schema"""
        errors = []
        
        # Check required fields
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Check field types
        properties = schema.get('properties', {})
        for field, field_schema in properties.items():
            if field in data:
                expected_type = field_schema.get('type')
                actual_value = data[field]
                
                if expected_type == 'string' and not isinstance(actual_value, str):
                    errors.append(f"Field {field} must be a string")
                elif expected_type == 'number' and not isinstance(actual_value, (int, float)):
                    errors.append(f"Field {field} must be a number")
                elif expected_type == 'boolean' and not isinstance(actual_value, bool):
                    errors.append(f"Field {field} must be a boolean")
                elif expected_type == 'array' and not isinstance(actual_value, list):
                    errors.append(f"Field {field} must be an array")
                elif expected_type == 'object' and not isinstance(actual_value, dict):
                    errors.append(f"Field {field} must be an object")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate secure API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_webhook_secret() -> str:
        """Generate webhook secret"""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using Django's default hasher"""
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        from django.contrib.auth.hashers import check_password
        return check_password(password, hashed)
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def encrypt_sensitive_data(data: str, key: str) -> str:
        """Encrypt sensitive data"""
        try:
            from cryptography.fernet import Fernet
            f = Fernet(key.encode())
            return f.encrypt(data.encode()).decode()
        except ImportError:
            logger.warning("cryptography not available, using simple encoding")
            return data
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_data: str, key: str) -> str:
        """Decrypt sensitive data"""
        try:
            from cryptography.fernet import Fernet
            f = Fernet(key.encode())
            return f.decrypt(encrypted_data.encode()).decode()
        except ImportError:
            logger.warning("cryptography not available, using simple decoding")
            return encrypted_data


class CacheUtils:
    """Cache utility functions"""
    
    @staticmethod
    def get_cache_key(prefix: str, *args) -> str:
        """Generate cache key"""
        key_parts = [prefix] + [str(arg) for arg in args]
        return ':'.join(key_parts)
    
    @staticmethod
    def set_cache(key: str, value: Any, timeout: int = 300) -> bool:
        """Set cache value"""
        try:
            cache.set(key, value, timeout)
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    @staticmethod
    def get_cache(key: str, default: Any = None) -> Any:
        """Get cache value"""
        try:
            return cache.get(key, default)
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return default
    
    @staticmethod
    def delete_cache(key: str) -> bool:
        """Delete cache key"""
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    @staticmethod
    def clear_cache_pattern(pattern: str) -> int:
        """Clear cache keys matching pattern"""
        try:
            # This is a simplified implementation
            # In production, you might want to use redis pattern matching
            keys_to_delete = []
            # Implementation depends on cache backend
            for key in keys_to_delete:
                cache.delete(key)
            return len(keys_to_delete)
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {e}")
            return 0


class ExportUtils:
    """Export utility functions"""
    
    @staticmethod
    def escape_csv_value(value: Any) -> str:
        """Escape value for CSV"""
        if value is None:
            return ''
        
        value_str = str(value)
        
        # Escape quotes and commas
        if '"' in value_str or ',' in value_str or '\n' in value_str:
            value_str = f'"{value_str.replace('"', '""')}"'
        
        return value_str
    
    @staticmethod
    def generate_csv_filename(prefix: str, extension: str = 'csv') -> str:
        """Generate CSV filename"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{timestamp}.{extension}"
    
    @staticmethod
    def generate_excel_filename(prefix: str) -> str:
        """Generate Excel filename"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{timestamp}.xlsx"
    
    @staticmethod
    def format_currency(amount: float, currency: str = 'USD') -> str:
        """Format currency amount"""
        return f"{currency} {amount:,.2f}"
    
    @staticmethod
    def format_percentage(value: float, decimal_places: int = 2) -> str:
        """Format percentage"""
        return f"{value:.{decimal_places}f}%"


# Decorators
def cache_result(timeout: int = 300, key_prefix: str = ''):
    """Decorator to cache function results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheUtils.get_cache_key(
                key_prefix or func.__name__,
                *args,
                *[f"{k}:{v}" for k, v in sorted(kwargs.items())]
            )
            
            # Try to get from cache
            cached_result = CacheUtils.get_cache(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            CacheUtils.set_cache(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def rate_limit(max_requests: int = 100, window_minutes: int = 60, key_func=None):
    """Decorator for rate limiting"""
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Generate rate limit key
            if key_func:
                rate_key = key_func(request)
            else:
                rate_key = CacheUtils.get_cache_key(
                    'rate_limit',
                    AlertUtils.get_client_ip(request),
                    func.__name__
                )
            
            # Get current count
            current_count = CacheUtils.get_cache(rate_key, 0)
            
            # Check if rate limit exceeded
            if current_count >= max_requests:
                from django.http import JsonResponse
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {max_requests} requests per {window_minutes} minutes'
                }, status=429)
            
            # Increment counter
            CacheUtils.set_cache(rate_key, current_count + 1, window_minutes * 60)
            
            # Execute function
            return func(request, *args, **kwargs)
        return wrapper
    return decorator
