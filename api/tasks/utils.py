"""
tasks/utils.py
Comprehensive utility functions for the task management system.
Enhanced to 85% completion with missing helper functions.
"""
import os

import logging
import hashlib
import secrets
import uuid
import time
import json
import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from django.utils import timezone as django_timezone
from django.core.cache import cache
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


# ==================== SECURITY UTILITIES ====================

def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def hash_sensitive_data(data: str, salt: str = None) -> str:
    """Hash sensitive data with optional salt"""
    if salt is None:
        salt = settings.SECRET_KEY[:16]
    
    return hashlib.sha256(f"{salt}{data}".encode()).hexdigest()


def validate_email_format(email: str) -> bool:
    """Validate email format with comprehensive regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_phone_number(phone: str) -> str:
    """Sanitize phone number to standard format"""
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Remove leading + if present
    if digits.startswith('1') and len(digits) == 11:
        digits = digits[1:]
    
    return digits


def mask_sensitive_info(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """Mask sensitive information showing only last few characters"""
    if len(data) <= visible_chars:
        return data
    
    return mask_char * (len(data) - visible_chars) + data[-visible_chars:]


# ==================== DATA VALIDATION UTILITIES ====================

def safe_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """Safely convert value to Decimal"""
    try:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer"""
    try:
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float"""
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Safely convert value to boolean"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', 'yes', '1', 'on', 'enabled')
    return bool(value)


def safe_json_loads(data: str, default: Any = None) -> Any:
    """Safely load JSON string"""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(data: Any, default: str = '{}') -> str:
    """Safely dump data to JSON string"""
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError):
        return default


# ==================== DATE/TIME UTILITIES ====================

def parse_iso_datetime(date_string: str) -> Optional[datetime]:
    """Parse ISO datetime string with multiple format support"""
    if not date_string:
        return None
    
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            # Add timezone if missing and string ends with Z
            if date_string.endswith('Z') and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    return None


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"


def get_time_range(period: str) -> Tuple[datetime, datetime]:
    """Get datetime range for common periods"""
    now = django_timezone.now()
    
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif period == 'yesterday':
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start, end
    elif period == 'week':
        start = now - timedelta(days=7)
        return start, now
    elif period == 'month':
        start = now - timedelta(days=30)
        return start, now
    elif period == 'year':
        start = now - timedelta(days=365)
        return start, now
    else:
        # Default to last 30 days
        start = now - timedelta(days=30)
        return start, now


def is_business_hours(dt: datetime = None) -> bool:
    """Check if datetime is within business hours (9 AM - 6 PM, Mon-Fri)"""
    if dt is None:
        dt = django_timezone.now()
    
    # Check weekend
    if dt.weekday() >= 5:  # Saturday, Sunday
        return False
    
    # Check hours (9 AM - 6 PM)
    return 9 <= dt.hour < 18


# ==================== STRING UTILITIES ====================

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().replace(' ', '-')
    # Remove special characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text to specified length with suffix"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text"""
    # Remove punctuation and convert to lowercase
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Filter out short words and common stop words
    stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    keywords = [word for word in words if len(word) >= min_length and word not in stop_words]
    
    return list(set(keywords))  # Remove duplicates


def format_currency(amount: Union[Decimal, float, int], currency: str = 'USD') -> str:
    """Format amount as currency"""
    try:
        amount = Decimal(str(amount))
        if currency == 'USD':
            return f"${amount:,.2f}"
        elif currency == 'EUR':
            return f"€{amount:,.2f}"
        elif currency == 'GBP':
            return f"£{amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"
    except (InvalidOperation, ValueError):
        return f"0.00 {currency}"


# ==================== CACHE UTILITIES ====================

def cache_get(key: str, default: Any = None, timeout: int = None) -> Any:
    """Get value from cache with error handling"""
    try:
        return cache.get(key, default)
    except Exception as e:
        logger.error(f"Cache get error for key {key}: {e}")
        return default


def cache_set(key: str, value: Any, timeout: int = None) -> bool:
    """Set value in cache with error handling"""
    try:
        cache.set(key, value, timeout)
        return True
    except Exception as e:
        logger.error(f"Cache set error for key {key}: {e}")
        return False


def cache_delete(key: str) -> bool:
    """Delete key from cache with error handling"""
    try:
        cache.delete(key)
        return True
    except Exception as e:
        logger.error(f"Cache delete error for key {key}: {e}")
        return False


def cache_get_or_set(key: str, default_func: Callable, timeout: int = None) -> Any:
    """Get from cache or set using function"""
    value = cache_get(key)
    if value is None:
        value = default_func()
        cache_set(key, value, timeout)
    return value


# ==================== PERFORMANCE UTILITIES ====================

def measure_execution_time(func: Callable) -> Callable:
    """Decorator to measure function execution time"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
        return result
    
    return wrapper


def chunk_queryset(queryset, chunk_size: int = 1000):
    """Yield chunks of queryset for memory-efficient processing"""
    start = 0
    while True:
        chunk = list(queryset[start:start + chunk_size])
        if not chunk:
            break
        yield chunk
        start += chunk_size


def batch_process(items: List, batch_size: int = 100, process_func: Callable = None):
    """Process items in batches to avoid memory issues"""
    if process_func is None:
        raise ValueError("process_func is required")
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        yield process_func(batch)


# ==================== CALCULATION UTILITIES ====================

def calculate_percentage(part: Union[int, float], total: Union[int, float], decimal_places: int = 2) -> float:
    """Calculate percentage safely"""
    try:
        if total == 0:
            return 0.0
        return round((part / total) * 100, decimal_places)
    except (ZeroDivisionError, TypeError):
        return 0.0


def calculate_growth_rate(current: Union[int, float], previous: Union[int, float]) -> float:
    """Calculate growth rate percentage"""
    try:
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return ((current - previous) / previous) * 100
    except (ZeroDivisionError, TypeError):
        return 0.0


def calculate_compound_interest(principal: Decimal, rate: Decimal, periods: int) -> Decimal:
    """Calculate compound interest"""
    try:
        return principal * (1 + rate) ** periods
    except (InvalidOperation, TypeError):
        return principal


def moving_average(data: List[float], window_size: int) -> List[float]:
    """Calculate moving average for data points"""
    if not data or window_size <= 0:
        return []
    
    result = []
    for i in range(len(data)):
        start = max(0, i - window_size + 1)
        window = data[start:i + 1]
        avg = sum(window) / len(window)
        result.append(avg)
    
    return result


# ==================== API UTILITIES ====================

def build_api_response(data: Any = None, message: str = 'Success', status_code: int = 200, 
                     meta: Dict = None) -> Dict:
    """Build standardized API response"""
    response = {
        'status': 'success' if 200 <= status_code < 300 else 'error',
        'message': message,
        'data': data,
        'timestamp': django_timezone.now().isoformat()
    }
    
    if meta:
        response['meta'] = meta
    
    return response


def paginate_response(queryset, page: int = 1, page_size: int = 20):
    """Paginate queryset and return pagination info"""
    try:
        total_count = queryset.count()
        total_pages = math.ceil(total_count / page_size)
        
        start = (page - 1) * page_size
        end = start + page_size
        
        items = list(queryset[start:end])
        
        return {
            'items': items,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1
            }
        }
    except Exception as e:
        logger.error(f"Pagination error: {e}")
        return {
            'items': [],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': 0,
                'total_pages': 0,
                'has_next': False,
                'has_previous': False
            }
        }


def validate_request_params(params: Dict, required_fields: List[str]) -> Tuple[bool, List[str]]:
    """Validate required request parameters"""
    missing_fields = [field for field in required_fields if field not in params or params[field] is None]
    return len(missing_fields) == 0, missing_fields


# ==================== NOTIFICATION UTILITIES ====================

def send_notification(user_id: int, message: str, notification_type: str = 'info', 
                   channels: List[str] = None) -> bool:
    """Send notification through multiple channels"""
    try:
        if channels is None:
            channels = ['database']
        
        success = True
        
        for channel in channels:
            if channel == 'database':
                success &= _save_database_notification(user_id, message, notification_type)
            elif channel == 'email':
                success &= _send_email_notification(user_id, message, notification_type)
            elif channel == 'push':
                success &= _send_push_notification(user_id, message, notification_type)
            elif channel == 'sms':
                success &= _send_sms_notification(user_id, message, notification_type)
        
        return success
    except Exception as e:
        logger.error(f"Notification send error: {e}")
        return False


def _save_database_notification(user_id: int, message: str, notification_type: str) -> bool:
    """Save notification to database"""
    try:
        # This would integrate with your notification model
        # For now, just log it
        logger.info(f"DB notification for user {user_id}: {message}")
        return True
    except Exception as e:
        logger.error(f"Database notification error: {e}")
        return False


def _send_email_notification(user_id: int, message: str, notification_type: str) -> bool:
    """Send email notification"""
    try:
        # This would integrate with your email service
        logger.info(f"Email notification for user {user_id}: {message}")
        return True
    except Exception as e:
        logger.error(f"Email notification error: {e}")
        return False


def _send_push_notification(user_id: int, message: str, notification_type: str) -> bool:
    """Send push notification"""
    try:
        # This would integrate with your push service
        logger.info(f"Push notification for user {user_id}: {message}")
        return True
    except Exception as e:
        logger.error(f"Push notification error: {e}")
        return False


def _send_sms_notification(user_id: int, message: str, notification_type: str) -> bool:
    """Send SMS notification"""
    try:
        # This would integrate with your SMS service
        logger.info(f"SMS notification for user {user_id}: {message}")
        return True
    except Exception as e:
        logger.error(f"SMS notification error: {e}")
        return False


# ==================== RATE LIMITING UTILITIES ====================

def check_rate_limit(identifier: str, limit: int, window: int = 3600) -> Tuple[bool, int]:
    """Check rate limit for identifier"""
    try:
        cache_key = f"rate_limit:{identifier}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return False, window - cache.ttl(cache_key)
        
        # Increment counter
        cache.set(cache_key, current_count + 1, window)
        return True, window - cache.ttl(cache_key)
    except Exception as e:
        logger.error(f"Rate limit check error: {e}")
        return True, window


def reset_rate_limit(identifier: str) -> bool:
    """Reset rate limit for identifier"""
    try:
        cache_key = f"rate_limit:{identifier}"
        cache.delete(cache_key)
        return True
    except Exception as e:
        logger.error(f"Rate limit reset error: {e}")
        return False


# ==================== FILE UTILITIES ====================

def generate_unique_filename(original_name: str) -> str:
    """Generate unique filename preserving extension"""
    import os
    name, ext = os.path.splitext(original_name)
    timestamp = int(time.time())
    random_str = secrets.token_hex(4)
    return f"{name}_{timestamp}_{random_str}{ext}"


def get_file_size_mb(file_size_bytes: int) -> float:
    """Convert file size from bytes to MB"""
    return round(file_size_bytes / (1024 * 1024), 2)


def is_valid_image_extension(filename: str) -> bool:
    """Check if filename has valid image extension"""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    return os.path.splitext(filename.lower())[1] in valid_extensions


def is_valid_document_extension(filename: str) -> bool:
    """Check if filename has valid document extension"""
    valid_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf'}
    return os.path.splitext(filename.lower())[1] in valid_extensions


# ==================== GEOLOCATION UTILITIES ====================

def get_client_ip_from_request(request) -> str:
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """Get location information from IP address"""
    try:
        # This would integrate with a geolocation service
        # For now, return dummy data
        return {
            'ip': ip_address,
            'country': 'Unknown',
            'city': 'Unknown',
            'latitude': 0.0,
            'longitude': 0.0
        }
    except Exception as e:
        logger.error(f"Geolocation error: {e}")
        return {}


# ==================== EXPORT UTILITIES ====================

def export_to_csv(data: List[Dict], filename: str) -> bool:
    """Export data to CSV file"""
    try:
        import csv
        
        if not data:
            return False
        
        fieldnames = data[0].keys()
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        return True
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        return False


def export_to_json(data: Any, filename: str) -> bool:
    """Export data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"JSON export error: {e}")
        return False


# ==================== CONSTANTS ====================

class Constants:
    """Application constants"""
    
    # Time periods
    SECOND = 1
    MINUTE = 60
    HOUR = 3600
    DAY = 86400
    WEEK = 604800
    MONTH = 2592000
    YEAR = 31536000
    
    # File size limits (in bytes)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Rate limiting
    DEFAULT_RATE_LIMIT = 100  # requests per hour
    AUTHENTICATED_RATE_LIMIT = 1000  # requests per hour
    
    # Cache timeouts
    CACHE_TTL_SHORT = 300  # 5 minutes
    CACHE_TTL_MEDIUM = 1800  # 30 minutes
    CACHE_TTL_LONG = 3600  # 1 hour
    
    # Notification types
    NOTIFICATION_TYPES = ['info', 'success', 'warning', 'error']
    
    # Task statuses
    TASK_STATUSES = ['pending', 'started', 'completed', 'failed', 'cancelled']
    
    # User levels
    USER_LEVELS = ['beginner', 'intermediate', 'advanced', 'expert']


# ==================== EXCEPTION HANDLING ====================

class UtilError(Exception):
    """Base utility exception"""
    pass


class ValidationError(UtilError):
    """Validation error"""
    pass


class CacheError(UtilError):
    """Cache operation error"""
    pass


class RateLimitError(UtilError):
    """Rate limit exceeded error"""
    pass


# ==================== MAIN EXPORTS ====================

__all__ = [
    # Security
    'generate_secure_token', 'hash_sensitive_data', 'validate_email_format',
    'sanitize_phone_number', 'mask_sensitive_info',
    
    # Data validation
    'safe_decimal', 'safe_int', 'safe_float', 'safe_bool',
    'safe_json_loads', 'safe_json_dumps',
    
    # Date/time
    'parse_iso_datetime', 'format_duration', 'get_time_range', 'is_business_hours',
    
    # String
    'slugify', 'truncate_text', 'extract_keywords', 'format_currency',
    
    # Cache
    'cache_get', 'cache_set', 'cache_delete', 'cache_get_or_set',
    
    # Performance
    'measure_execution_time', 'chunk_queryset', 'batch_process',
    
    # Calculation
    'calculate_percentage', 'calculate_growth_rate', 'calculate_compound_interest',
    'moving_average',
    
    # API
    'build_api_response', 'paginate_response', 'validate_request_params',
    
    # Notification
    'send_notification',
    
    # Rate limiting
    'check_rate_limit', 'reset_rate_limit',
    
    # File
    'generate_unique_filename', 'get_file_size_mb',
    'is_valid_image_extension', 'is_valid_document_extension',
    
    # Geolocation
    'get_client_ip_from_request', 'get_location_from_ip',
    
    # Export
    'export_to_csv', 'export_to_json',
    
    # Constants and exceptions
    'Constants', 'UtilError', 'ValidationError', 'CacheError', 'RateLimitError'
]
