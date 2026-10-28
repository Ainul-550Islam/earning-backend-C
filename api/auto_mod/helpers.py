# =============================================================================
# auto_mod/helpers.py
# =============================================================================

"""
Helper functions and utilities for auto moderation system.
Provides common utility functions, data transformations, and convenience methods.
"""

import logging
import hashlib
import json
import uuid
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# String and Text Utilities
# =============================================================================

def clean_text(text: str, remove_extra_spaces: bool = True, 
               remove_special_chars: bool = False, max_length: int = None) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Input text to clean
        remove_extra_spaces: Whether to remove extra whitespace
        remove_special_chars: Whether to remove special characters
        max_length: Maximum length of output text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra spaces
    if remove_extra_spaces:
        text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove special characters
    if remove_special_chars:
        text = re.sub(r'[^\w\s\-.,!?;:]', '', text)
    
    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '...'
    
    return text


def extract_keywords(text: str, min_length: int = 3, max_keywords: int = 10) -> List[str]:
    """
    Extract keywords from text.
    
    Args:
        text: Input text
        min_length: Minimum keyword length
        max_keywords: Maximum number of keywords
        
    Returns:
        List of keywords
    """
    if not text:
        return []
    
    # Simple keyword extraction - can be enhanced with NLP
    words = re.findall(r'\b[a-zA-Z]{' + str(min_length) + ',}\b', text.lower())
    
    # Remove common stop words
    stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
    
    keywords = [word for word in words if word not in stop_words]
    
    # Return most frequent keywords
    from collections import Counter
    keyword_counts = Counter(keywords)
    
    return [word for word, _ in keyword_counts.most_common(max_keywords)]


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0
    
    # Simple Jaccard similarity - can be enhanced with more sophisticated methods
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0


def mask_sensitive_data(text: str, mask_char: str = '*', 
                       preserve_length: bool = True) -> str:
    """
    Mask sensitive data in text.
    
    Args:
        text: Input text
        mask_char: Character to use for masking
        preserve_length: Whether to preserve original length
        
    Returns:
        Masked text
    """
    if not text:
        return ""
    
    # Simple masking - can be enhanced with pattern matching
    if preserve_length:
        return mask_char * len(text)
    else:
        return mask_char * 4


# =============================================================================
# Data Validation and Sanitization
# =============================================================================

def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    
    pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
    return bool(re.match(pattern, url))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return ""
    
    # Remove dangerous characters
    sanitized = re.sub(r'[^\w\-_.]', '', filename)
    
    # Ensure it's not empty after sanitization
    if not sanitized:
        sanitized = "file"
    
    return sanitized


def validate_json(data: Union[str, Dict, List]) -> Tuple[bool, Optional[str]]:
    """
    Validate JSON data.
    
    Args:
        data: Data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if isinstance(data, (dict, list)):
        return True, None
    
    if isinstance(data, str):
        try:
            json.loads(data)
            return True, None
        except json.JSONDecodeError as e:
            return False, str(e)
    
    return False, "Invalid data type"


# =============================================================================
# Hashing and Security Utilities
# =============================================================================

def generate_hash(data: str, algorithm: str = 'sha256') -> str:
    """
    Generate hash of data.
    
    Args:
        data: Data to hash
        algorithm: Hash algorithm to use
        
    Returns:
        Hexadecimal hash
    """
    if not data:
        return ""
    
    try:
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(data.encode('utf-8'))
        return hash_obj.hexdigest()
    except ValueError:
        # Fallback to sha256 if algorithm not supported
        return hashlib.sha256(data.encode('utf-8')).hexdigest()


def generate_uuid() -> str:
    """
    Generate a UUID string.
    
    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """
    Generate a short unique ID.
    
    Args:
        length: Length of the ID
        
    Returns:
        Short ID string
    """
    import random
    import string
    
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# =============================================================================
# Date and Time Utilities
# =============================================================================

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
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


def get_time_ago(timestamp: datetime) -> str:
    """
    Get human readable "time ago" string.
    
    Args:
        timestamp: Timestamp to compare
        
    Returns:
        Time ago string
    """
    if not timestamp:
        return "Unknown"
    
    now = timezone.now()
    delta = now - timestamp
    
    if delta.total_seconds() < 60:
        return "Just now"
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.days < 7:
        days = delta.days
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif delta.days < 365:
        months = delta.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = delta.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"


def get_date_range(period: str) -> Tuple[datetime, datetime]:
    """
    Get date range for a given period.
    
    Args:
        period: Period ('today', 'week', 'month', 'year')
        
    Returns:
        Tuple of (start_date, end_date)
    """
    now = timezone.now()
    
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == 'week':
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=31)
    elif period == 'year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=now.year + 1)
    else:
        # Default to last 30 days
        start = now - timedelta(days=30)
        end = now
    
    return start, end


# =============================================================================
# Cache Utilities
# =============================================================================

def cache_key(*args, prefix: str = 'auto_mod') -> str:
    """
    Generate cache key from arguments.
    
    Args:
        *args: Arguments to include in key
        prefix: Key prefix
        
    Returns:
        Cache key string
    """
    key_parts = [prefix] + [str(arg) for arg in args]
    return ':'.join(key_parts)


def get_or_set_cache(key: str, getter_func, timeout: int = 300, **kwargs) -> Any:
    """
    Get value from cache or set using getter function.
    
    Args:
        key: Cache key
        getter_func: Function to get value if not in cache
        timeout: Cache timeout in seconds
        **kwargs: Arguments for getter function
        
    Returns:
        Cached value
    """
    value = cache.get(key)
    if value is None:
        value = getter_func(**kwargs)
        cache.set(key, value, timeout)
    return value


def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate cache keys matching pattern.
    
    Args:
        pattern: Pattern to match (supports wildcards)
        
    Returns:
        Number of keys invalidated
    """
    if hasattr(cache, 'delete_pattern'):
        # Redis backend supports pattern deletion
        return cache.delete_pattern(pattern)
    else:
        # Fallback for other backends
        # This is a simplified implementation
        logger.warning(f"Cache pattern deletion not supported for backend: {type(cache)}")
        return 0


# =============================================================================
# Database Utilities
# =============================================================================

def bulk_create_with_signal(model_class, instances: List, batch_size: int = 1000) -> List:
    """
    Bulk create instances with signal support.
    
    Args:
        model_class: Model class
        instances: List of instances to create
        batch_size: Batch size for creation
        
    Returns:
        List of created instances
    """
    created_instances = []
    
    for i in range(0, len(instances), batch_size):
        batch = instances[i:i + batch_size]
        
        # Use transaction for each batch
        with transaction.atomic():
            for instance in batch:
                instance.save()
                created_instances.append(instance)
    
    return created_instances


def get_or_create_with_cache(model_class, defaults: Dict = None, **kwargs) -> Tuple[Any, bool]:
    """
    Get or create model instance with caching.
    
    Args:
        model_class: Model class
        defaults: Default values for creation
        **kwargs: Lookup fields
        
    Returns:
        Tuple of (instance, created)
    """
    cache_key_suffix = ':'.join([f"{k}:{v}" for k, v in kwargs.items()])
    cache_key = cache_key('get_or_create', model_class.__name__, cache_key_suffix)
    
    # Try to get from cache first
    instance = cache.get(cache_key)
    if instance:
        return instance, False
    
    # Get or create from database
    instance, created = model_class.objects.get_or_create(defaults=defaults or {}, **kwargs)
    
    # Cache the result
    cache.set(cache_key, instance, timeout=300)
    
    return instance, created


# =============================================================================
# File and Media Utilities
# =============================================================================

def get_file_size_display(size_bytes: int) -> str:
    """
    Get human readable file size.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human readable size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def is_image_file(filename: str) -> bool:
    """
    Check if file is an image.
    
    Args:
        filename: Filename to check
        
    Returns:
        True if image file, False otherwise
    """
    if not filename:
        return False
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
    return any(filename.lower().endswith(ext) for ext in image_extensions)


def is_document_file(filename: str) -> bool:
    """
    Check if file is a document.
    
    Args:
        filename: Filename to check
        
    Returns:
        True if document file, False otherwise
    """
    if not filename:
        return False
    
    doc_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'}
    return any(filename.lower().endswith(ext) for ext in doc_extensions)


# =============================================================================
# API and Response Utilities
# =============================================================================

def create_api_response(data: Any = None, message: str = None, 
                      status: str = 'success', code: int = 200, 
                      meta: Dict = None) -> Dict[str, Any]:
    """
    Create standardized API response.
    
    Args:
        data: Response data
        message: Response message
        status: Response status
        code: HTTP status code
        meta: Additional metadata
        
    Returns:
        Standardized response dictionary
    """
    response = {
        'status': status,
        'code': code,
        'timestamp': timezone.now().isoformat(),
    }
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    if meta:
        response['meta'] = meta
    
    return response


def create_error_response(message: str, code: int = 400, 
                        errors: Dict = None, meta: Dict = None) -> Dict[str, Any]:
    """
    Create standardized error response.
    
    Args:
        message: Error message
        code: HTTP status code
        errors: Detailed errors
        meta: Additional metadata
        
    Returns:
        Standardized error response
    """
    return create_api_response(
        status='error',
        message=message,
        code=code,
        data=errors,
        meta=meta
    )


# =============================================================================
# User and Permission Utilities
# =============================================================================

def get_user_by_id(user_id: str) -> Optional[Any]:
    """
    Get user by ID with caching.
    
    Args:
        user_id: User ID
        
    Returns:
        User instance or None
    """
    if not user_id:
        return None
    
    User = get_user_model()
    cache_key = cache_key('user', user_id)
    
    user = cache.get(cache_key)
    if user is None:
        try:
            user = User.objects.get(pk=user_id)
            cache.set(cache_key, user, timeout=300)
        except User.DoesNotExist:
            return None
    
    return user


def user_has_permission(user: Any, permission: str) -> bool:
    """
    Check if user has specific permission.
    
    Args:
        user: User instance
        permission: Permission string
        
    Returns:
        True if user has permission, False otherwise
    """
    if not user or not hasattr(user, 'has_perm'):
        return False
    
    return user.has_perm(permission)


def get_user_moderation_stats(user_id: str, days: int = 30) -> Dict[str, int]:
    """
    Get moderation statistics for a user.
    
    Args:
        user_id: User ID
        days: Number of days to look back
        
    Returns:
        Dictionary with moderation stats
    """
    from .models import ModerationDecision, ModerationAppeal
    
    start_date = timezone.now() - timedelta(days=days)
    
    # Get decisions made by user
    decisions_count = ModerationDecision.objects.filter(
        decider_id=user_id,
        decided_at__gte=start_date
    ).count()
    
    # Get appeals reviewed by user
    appeals_count = ModerationAppeal.objects.filter(
        reviewer_id=user_id,
        reviewed_at__gte=start_date
    ).count()
    
    return {
        'decisions_made': decisions_count,
        'appeals_reviewed': appeals_count,
        'total_actions': decisions_count + appeals_count
    }


# =============================================================================
# Metrics and Analytics Utilities
# =============================================================================

def calculate_percentile(values: List[float], percentile: float) -> float:
    """
    Calculate percentile of values.
    
    Args:
        values: List of values
        percentile: Percentile to calculate (0-100)
        
    Returns:
        Percentile value
    """
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    index = (percentile / 100) * (len(sorted_values) - 1)
    
    if index.is_integer():
        return sorted_values[int(index)]
    else:
        lower = sorted_values[int(index)]
        upper = sorted_values[int(index) + 1]
        return lower + (upper - lower) * (index - int(index))


def calculate_moving_average(values: List[float], window: int) -> List[float]:
    """
    Calculate moving average of values.
    
    Args:
        values: List of values
        window: Window size
        
    Returns:
        List of moving averages
    """
    if not values or window <= 0:
        return []
    
    moving_averages = []
    
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_values = values[start:i + 1]
        avg = sum(window_values) / len(window_values)
        moving_averages.append(avg)
    
    return moving_averages


def detect_anomalies(values: List[float], threshold: float = 2.0) -> List[int]:
    """
    Detect anomalies in values using z-score.
    
    Args:
        values: List of values
        threshold: Z-score threshold for anomaly detection
        
    Returns:
        List of indices of anomalous values
    """
    if len(values) < 2:
        return []
    
    import statistics
    
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    
    if stdev == 0:
        return []
    
    anomalies = []
    
    for i, value in enumerate(values):
        z_score = abs(value - mean) / stdev
        if z_score > threshold:
            anomalies.append(i)
    
    return anomalies


# =============================================================================
# Configuration and Settings Utilities
# =============================================================================

def get_setting(key: str, default: Any = None) -> Any:
    """
    Get setting value with fallback.
    
    Args:
        key: Setting key
        default: Default value
        
    Returns:
        Setting value
    """
    return getattr(settings, key, default)


def is_debug_mode() -> bool:
    """
    Check if application is in debug mode.
    
    Returns:
        True if debug mode, False otherwise
    """
    return get_setting('DEBUG', False)


def get_cache_timeout(timeout_key: str, default_timeout: int = 300) -> int:
    """
    Get cache timeout from settings.
    
    Args:
        timeout_key: Key for timeout setting
        default_timeout: Default timeout
        
    Returns:
        Cache timeout in seconds
    """
    cache_settings = get_setting('CACHE_TIMEOUTS', {})
    return cache_settings.get(timeout_key, default_timeout)


# =============================================================================
# Logging and Debugging Utilities
# =============================================================================

def log_performance(func_name: str, start_time: float, **kwargs) -> None:
    """
    Log performance metrics.
    
    Args:
        func_name: Function name
        start_time: Start time
        **kwargs: Additional metrics
    """
    duration = time.time() - start_time
    
    logger.info(
        f"Performance: {func_name} took {duration:.3f}s",
        extra={
            'function': func_name,
            'duration': duration,
            **kwargs
        }
    )


def debug_context(context: Dict[str, Any]) -> str:
    """
    Create debug context string.
    
    Args:
        context: Context dictionary
        
    Returns:
        Formatted context string
    """
    if not context:
        return ""
    
    context_parts = []
    for key, value in context.items():
        context_parts.append(f"{key}={value}")
    
    return f"[{' '.join(context_parts)}]"


# =============================================================================
# Validation Utilities
# =============================================================================

def validate_confidence(confidence: float) -> bool:
    """
    Validate confidence score.
    
    Args:
        confidence: Confidence score
        
    Returns:
        True if valid, False otherwise
    """
    return 0.0 <= confidence <= 1.0


def validate_risk_score(risk_score: float) -> bool:
    """
    Validate risk score.
    
    Args:
        risk_score: Risk score
        
    Returns:
        True if valid, False otherwise
    """
    return 0.0 <= risk_score <= 1.0


def validate_priority(priority: int) -> bool:
    """
    Validate priority value.
    
    Args:
        priority: Priority value
        
    Returns:
        True if valid, False otherwise
    """
    return 1 <= priority <= 10


# =============================================================================
# Data Transformation Utilities
# =============================================================================

def normalize_score(score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Normalize score to 0-1 range.
    
    Args:
        score: Score to normalize
        min_val: Minimum value
        max_val: Maximum value
        
    Returns:
        Normalized score
    """
    if max_val == min_val:
        return 0.0
    
    normalized = (score - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def round_to_decimal(value: float, decimal_places: int = 2) -> float:
    """
    Round value to specified decimal places.
    
    Args:
        value: Value to round
        decimal_places: Number of decimal places
        
    Returns:
        Rounded value
    """
    return round(value, decimal_places)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safe division with default value for division by zero.
    
    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value
        
    Returns:
        Division result or default
    """
    if denominator == 0:
        return default
    
    return numerator / denominator


# =============================================================================
# Miscellaneous Utilities
# =============================================================================

def generate_random_color() -> str:
    """
    Generate random hex color.
    
    Returns:
        Hex color string
    """
    import random
    return f"#{random.randint(0, 0xFFFFFF):06x}"


def parse_boolean(value: Any) -> bool:
    """
    Parse boolean value from various input types.
    
    Args:
        value: Value to parse
        
    Returns:
        Boolean value
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    return False


def deep_merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """
    Deep merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result
