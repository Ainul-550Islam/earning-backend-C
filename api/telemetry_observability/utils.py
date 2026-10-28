"""
Utility functions for Telemetry Observability.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from datetime import timedelta
import secrets
import re


def generate_trace_id() -> str:
    """
    Generate a unique trace ID.
    
    Returns:
        Trace ID string
    """
    import uuid
    return str(uuid.uuid4())


def generate_span_id() -> str:
    """
    Generate a unique span ID.
    
    Returns:
        Span ID string
    """
    import uuid
    return str(uuid.uuid4())


def format_timestamp(timestamp: timezone.datetime) -> str:
    """
    Format a timestamp for display.
    
    Args:
        timestamp: Timestamp to format
        
    Returns:
        Formatted timestamp string
    """
    return timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')


def calculate_duration_ms(start_time: timezone.datetime, end_time: timezone.datetime) -> float:
    """
    Calculate duration in milliseconds.
    
    Args:
        start_time: Start time
        end_time: End time
        
    Returns:
        Duration in milliseconds
    """
    return (end_time - start_time).total_seconds() * 1000


def format_duration_ms(duration_ms: float) -> str:
    """
    Format duration in milliseconds for display.
    
    Args:
        duration_ms: Duration in milliseconds
        
    Returns:
        Formatted duration string
    """
    if duration_ms < 1000:
        return f"{duration_ms:.2f}ms"
    elif duration_ms < 60000:
        return f"{duration_ms / 1000:.2f}s"
    elif duration_ms < 3600000:
        return f"{duration_ms / 60000:.2f}m"
    else:
        return f"{duration_ms / 3600000:.2f}h"


def sanitize_log_message(message: str, max_length: int = 10000) -> str:
    """
    Sanitize a log message.
    
    Args:
        message: Log message to sanitize
        max_length: Maximum length
        
    Returns:
        Sanitized message
    """
    if not message:
        return ''
    
    # Remove potentially dangerous characters
    sanitized = message.replace('\x00', '').replace('\x1b', '')
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def parse_log_level(level: str) -> str:
    """
    Parse and normalize a log level.
    
    Args:
        level: Log level string
        
    Returns:
        Normalized log level
    """
    level_map = {
        'debug': 'debug',
        'info': 'info',
        'warn': 'warning',
        'warning': 'warning',
        'error': 'error',
        'err': 'error',
        'critical': 'critical',
        'crit': 'critical',
        'fatal': 'critical'
    }
    
    return level_map.get(level.lower(), 'info')


def extract_error_from_stack_trace(stack_trace: str) -> Optional[str]:
    """
    Extract error message from stack trace.
    
    Args:
        stack_trace: Stack trace string
        
    Returns:
        Error message or None
    """
    if not stack_trace:
        return None
    
    # Look for common error patterns
    error_patterns = [
        r'Error: (.+)',
        r'Exception: (.+)',
        r'(\w+Error):',
    ]
    
    for pattern in error_patterns:
        match = re.search(pattern, stack_trace)
        if match:
            return match.group(1)
    
    return None


def calculate_error_rate(total_requests: int, error_count: int) -> float:
    """
    Calculate error rate.
    
    Args:
        total_requests: Total number of requests
        error_count: Number of errors
        
    Returns:
        Error rate as percentage
    """
    if total_requests == 0:
        return 0.0
    
    return round((error_count / total_requests) * 100, 2)


def calculate_percentile(values: List[float], percentile: float) -> float:
    """
    Calculate a percentile value.
    
    Args:
        values: List of values
        percentile: Percentile to calculate (0-100)
        
    Returns:
        Percentile value
    """
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    index = int(len(sorted_values) * (percentile / 100))
    
    if index >= len(sorted_values):
        return sorted_values[-1]
    
    return sorted_values[index]


def calculate_average(values: List[float]) -> float:
    """
    Calculate average value.
    
    Args:
        values: List of values
        
    Returns:
        Average value
    """
    if not values:
        return 0.0
    
    return round(sum(values) / len(values), 2)


def calculate_percentile_50(values: List[float]) -> float:
    """
    Calculate 50th percentile (median).
    
    Args:
        values: List of values
        
    Returns:
        Median value
    """
    return calculate_percentile(values, 50)


def calculate_percentile_95(values: List[float]) -> float:
    """
    Calculate 95th percentile.
    
    Args:
        values: List of values
        
    Returns:
        95th percentile value
    """
    return calculate_percentile(values, 95)


def calculate_percentile_99(values: List[float]) -> float:
    """
    Calculate 99th percentile.
    
    Args:
        values: List of values
        
    Returns:
        99th percentile value
    """
    return calculate_percentile(values, 99)


def format_metric_value(value: float, unit: str = "") -> str:
    """
    Format a metric value with unit.
    
    Args:
        value: Metric value
        unit: Unit string
        
    Returns:
        Formatted value string
    """
    if unit:
        return f"{value:.2f} {unit}"
    return f"{value:.2f}"


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes to human-readable format.
    
    Args:
        bytes_value: Value in bytes
        
    Returns:
        Formatted string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def parse_time_window(window: str) -> timedelta:
    """
    Parse a time window string.
    
    Args:
        window: Time window string (e.g., "1h", "30m", "7d")
        
    Returns:
        Timedelta object
    """
    window = window.lower()
    
    if window.endswith('s'):
        return timedelta(seconds=int(window[:-1]))
    elif window.endswith('m'):
        return timedelta(minutes=int(window[:-1]))
    elif window.endswith('h'):
        return timedelta(hours=int(window[:-1]))
    elif window.endswith('d'):
        return timedelta(days=int(window[:-1]))
    elif window.endswith('w'):
        return timedelta(weeks=int(window[:-1]))
    else:
        return timedelta(minutes=int(window))


def get_time_range(window: str) -> tuple:
    """
    Get start and end time for a time window.
    
    Args:
        window: Time window string
        
    Returns:
        Tuple of (start_time, end_time)
    """
    end_time = timezone.now()
    delta = parse_time_window(window)
    start_time = end_time - delta
    
    return start_time, end_time


def truncate_string(value: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        value: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(value) <= max_length:
        return value
    
    return value[:max_length - len(suffix)] + suffix


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    Safely load JSON string.
    
    Args:
        json_str: JSON string
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default value
    """
    import json
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = '{}') -> str:
    """
    Safely dump object to JSON string.
    
    Args:
        obj: Object to dump
        default: Default string if serialization fails
        
    Returns:
        JSON string or default value
    """
    import json
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return default


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks.
    
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    chunks = []
    for i in range(0, len(items), chunk_size):
        chunks.append(items[i:i + chunk_size])
    return chunks


def get_nested_value(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Get a nested value from a dictionary.
    
    Args:
        data: Dictionary
        *keys: Keys to traverse
        default: Default value if key not found
        
    Returns:
        Nested value or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def set_nested_value(data: Dict[str, Any], *keys: str, value: Any) -> None:
    """
    Set a nested value in a dictionary.
    
    Args:
        data: Dictionary
        *keys: Keys to traverse
        value: Value to set
    """
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries.
    
    Args:
        *dicts: Dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary
        
    Returns:
        Deep merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def generate_random_string(length: int = 32) -> str:
    """
    Generate a random string.
    
    Args:
        length: Length of the string
        
    Returns:
        Random string
    """
    return secrets.token_hex(length)


def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """
    Mask sensitive data.
    
    Args:
        data: Data to mask
        mask_char: Character to use for masking
        visible_chars: Number of characters to leave visible
        
    Returns:
        Masked data
    """
    if len(data) <= visible_chars:
        return data
    
    visible = data[:visible_chars]
    masked = mask_char * (len(data) - visible_chars)
    return visible + masked


def is_valid_email(email: str) -> bool:
    """
    Validate an email address.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def is_valid_url(url: str) -> bool:
    """
    Validate a URL.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid
    """
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return re.match(pattern, url) is not None


def get_client_ip(request) -> str:
    """
    Get client IP address from request.
    
    Args:
        request: HTTP request object
        
    Returns:
        IP address string
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip


def get_user_agent(request) -> str:
    """
    Get user agent from request.
    
    Args:
        request: HTTP request object
        
    Returns:
        User agent string
    """
    return request.META.get('HTTP_USER_AGENT', 'unknown')


def calculate_health_score(
    uptime: float,
    response_time: float,
    error_rate: float,
    weights: Optional[Dict[str, float]] = None
) -> int:
    """
    Calculate a health score based on metrics.
    
    Args:
        uptime: Uptime percentage (0-100)
        response_time: Response time in ms
        error_rate: Error rate percentage (0-100)
        weights: Optional weights for each metric
        
    Returns:
        Health score (0-100)
    """
    if weights is None:
        weights = {
            'uptime': 0.4,
            'response_time': 0.3,
            'error_rate': 0.3
        }
    
    # Normalize metrics to 0-100 scale
    uptime_score = uptime
    response_time_score = max(0, 100 - (response_time / 10))  # 10ms = 0 score
    error_rate_score = max(0, 100 - error_rate * 10)  # 10% error = 0 score
    
    # Calculate weighted score
    score = (
        uptime_score * weights['uptime'] +
        response_time_score * weights['response_time'] +
        error_rate_score * weights['error_rate']
    )
    
    return int(round(score))
