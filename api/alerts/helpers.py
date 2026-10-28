"""
Helper functions and utilities for alerts app
"""
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import json
import logging
import re

logger = logging.getLogger(__name__)


class AlertHelper:
    """Helper class for alert operations"""
    
    @staticmethod
    def format_alert_message(rule, alert_log) -> str:
        """Format alert message with context"""
        context = {
            'rule_name': rule.name,
            'severity': rule.severity.upper(),
            'threshold_value': alert_log.threshold_value,
            'trigger_value': alert_log.trigger_value,
            'triggered_at': alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S'),
            'message': alert_log.message
        }
        
        try:
            return rule.message_template.format(**context)
        except (KeyError, AttributeError):
            # Fallback to default format
            return f"[{rule.severity.upper()}] {rule.name}: {alert_log.message}"
    
    @staticmethod
    def calculate_breach_percentage(trigger_value: float, threshold_value: float) -> float:
        """Calculate percentage by which threshold was breached"""
        if threshold_value == 0:
            return 0.0
        
        return ((trigger_value - threshold_value) / threshold_value) * 100
    
    @staticmethod
    def get_severity_color(severity: str) -> str:
        """Get color for severity level"""
        colors = {
            'low': '#28a745',      # Green
            'medium': '#ffc107',   # Yellow
            'high': '#fd7e14',    # Orange
            'critical': '#dc3545'  # Red
        }
        return colors.get(severity, '#6c757d')  # Gray default
    
    @staticmethod
    def get_severity_icon(severity: str) -> str:
        """Get icon for severity level"""
        icons = {
            'low': '🟢',
            'medium': '🟡',
            'high': '🟠',
            'critical': '🔴'
        }
        return icons.get(severity, '⚪')
    
    @staticmethod
    def get_alert_type_display(alert_type: str) -> str:
        """Get display name for alert type"""
        from .choices import ALERT_TYPES
        for choice in ALERT_TYPES:
            if choice[0] == alert_type:
                return choice[1]
        return alert_type.title()
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format"""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        return len(digits) >= 10 and len(digits) <= 15
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number format"""
        # Remove all non-digit characters
        return re.sub(r'\D', '', phone)
    
    @staticmethod
    def get_time_ago(timestamp) -> str:
        """Get human-readable time ago string"""
        now = timezone.now()
        diff = now - timestamp
        
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
    def format_duration(minutes: float) -> str:
        """Format duration in minutes to human readable format"""
        if minutes < 60:
            return f"{round(minutes, 1)} minutes"
        elif minutes < 1440:  # 24 hours
            hours = minutes // 60
            remaining_minutes = minutes % 60
            return f"{int(hours)}h {int(remaining_minutes)}m"
        else:
            days = minutes // 1440
            remaining_hours = (minutes % 1440) // 60
            return f"{int(days)}d {int(remaining_hours)}h"


class NotificationHelper:
    """Helper class for notification operations"""
    
    @staticmethod
    def format_email_subject(rule, alert_log) -> str:
        """Format email subject"""
        severity_emoji = AlertHelper.get_severity_icon(rule.severity)
        return f"{severity_emoji} [{rule.severity.upper()}] {rule.name}"
    
    @staticmethod
    def format_email_body(rule, alert_log) -> str:
        """Format email body"""
        breach_percentage = AlertHelper.calculate_breach_percentage(
            alert_log.trigger_value, 
            alert_log.threshold_value
        )
        
        body = f"""
Alert Details:
===============
Rule: {rule.name}
Severity: {rule.severity.upper()}
Message: {alert_log.message}
Triggered At: {alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
Threshold: {alert_log.threshold_value}
Triggered Value: {alert_log.trigger_value}
Breach Percentage: {breach_percentage:.1f}%

Description:
{rule.description}

Details:
{json.dumps(alert_log.details, indent=2)}
        """.strip()
        
        return body
    
    @staticmethod
    def format_telegram_message(rule, alert_log) -> str:
        """Format Telegram message"""
        severity_emoji = AlertHelper.get_severity_icon(rule.severity)
        breach_percentage = AlertHelper.calculate_breach_percentage(
            alert_log.trigger_value, 
            alert_log.threshold_value
        )
        
        message = f"""
{severity_emoji} *{rule.severity.upper()} Alert*

🔹 *Rule:* {rule.name}
🔹 *Severity:* {rule.severity.upper()}
🔹 *Message:* {alert_log.message}
🔹 *Triggered:* {alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
🔹 *Threshold:* {alert_log.threshold_value}
🔹 *Value:* {alert_log.trigger_value} ({breach_percentage:.1f}% over)

{alert_log.message}
        """.strip()
        
        return message
    
    @staticmethod
    def format_sms_message(rule, alert_log) -> str:
        """Format SMS message"""
        return f"[{rule.severity.upper()}] {rule.name}: {alert_log.message[:100]}"
    
    @staticmethod
    def get_notification_rate_limit(notification_type: str) -> int:
        """Get rate limit for notification type"""
        rate_limits = {
            'email': 100,      # 100 per hour
            'sms': 50,         # 50 per hour
            'telegram': 200,    # 200 per hour
            'webhook': 1000,   # 1000 per hour
            'push': 500         # 500 per hour
        }
        return rate_limits.get(notification_type, 100)
    
    @staticmethod
    def should_retry_notification(notification, max_retries: int = 3) -> bool:
        """Check if notification should be retried"""
        if notification.status != 'failed':
            return False
        
        if notification.retry_count >= max_retries:
            return False
        
        # Exponential backoff
        if notification.last_retry_at:
            time_since_retry = (timezone.now() - notification.last_retry_at).total_seconds()
            retry_delay = 2 ** notification.retry_count * 60  # 1min, 2min, 4min, 8min
            
            return time_since_retry >= retry_delay
        
        return True


class CacheHelper:
    """Helper class for cache operations"""
    
    @staticmethod
    def get_cache_key(prefix: str, *args) -> str:
        """Generate cache key"""
        key_parts = [prefix] + [str(arg) for arg in args]
        return ':'.join(key_parts)
    
    @staticmethod
    def cache_alert_stats(alert_rule_id: int, timeout: int = 300) -> Optional[Dict[str, Any]]:
        """Cache alert statistics for rule"""
        cache_key = CacheHelper.get_cache_key('alert_stats', alert_rule_id)
        return cache.get(cache_key)
    
    @staticmethod
    def set_alert_stats(alert_rule_id: int, stats: Dict[str, Any], timeout: int = 300):
        """Set alert statistics cache"""
        cache_key = CacheHelper.get_cache_key('alert_stats', alert_rule_id)
        cache.set(cache_key, stats, timeout)
    
    @staticmethod
    def invalidate_alert_stats(alert_rule_id: int):
        """Invalidate alert statistics cache"""
        cache_key = CacheHelper.get_cache_key('alert_stats', alert_rule_id)
        cache.delete(cache_key)
    
    @staticmethod
    def cache_system_health(timeout: int = 60) -> Optional[Dict[str, Any]]:
        """Cache system health status"""
        cache_key = CacheHelper.get_cache_key('system_health')
        return cache.get(cache_key)
    
    @staticmethod
    def set_system_health(health_data: Dict[str, Any], timeout: int = 60):
        """Set system health cache"""
        cache_key = CacheHelper.get_cache_key('system_health')
        cache.set(cache_key, health_data, timeout)
    
    @staticmethod
    def invalidate_system_health():
        """Invalidate system health cache"""
        cache_key = CacheHelper.get_cache_key('system_health')
        cache.delete(cache_key)
    
    @staticmethod
    def cache_user_preferences(user_id: int, timeout: int = 3600) -> Optional[Dict[str, Any]]:
        """Cache user preferences"""
        cache_key = CacheHelper.get_cache_key('user_prefs', user_id)
        return cache.get(cache_key)
    
    @staticmethod
    def set_user_preferences(user_id: int, preferences: Dict[str, Any], timeout: int = 3600):
        """Set user preferences cache"""
        cache_key = CacheHelper.get_cache_key('user_prefs', user_id)
        cache.set(cache_key, preferences, timeout)
    
    @staticmethod
    def invalidate_user_preferences(user_id: int):
        """Invalidate user preferences cache"""
        cache_key = CacheHelper.get_cache_key('user_prefs', user_id)
        cache.delete(cache_key)


class ValidationHelper:
    """Helper class for validation operations"""
    
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
        
        # Check field constraints
        for field, field_schema in properties.items():
            if field in data:
                actual_value = data[field]
                
                # Check minimum
                if 'minimum' in field_schema and actual_value < field_schema['minimum']:
                    errors.append(f"Field {field} must be at least {field_schema['minimum']}")
                
                # Check maximum
                if 'maximum' in field_schema and actual_value > field_schema['maximum']:
                    errors.append(f"Field {field} must be at most {field_schema['maximum']}")
                
                # Check pattern
                if 'pattern' in field_schema:
                    pattern = field_schema['pattern']
                    if not re.match(pattern, str(actual_value)):
                        errors.append(f"Field {field} does not match required pattern")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string value"""
        if not isinstance(value, str):
            return str(value)
        
        # Remove HTML tags
        value = re.sub(r'<[^>]+>', '', value)
        
        # Remove extra whitespace
        value = ' '.join(value.split())
        
        # Truncate if too long
        if len(value) > max_length:
            value = value[:max_length-3] + '...'
        
        return value
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        
        return bool(url_pattern.match(url))
    
    @staticmethod
    def validate_webhook_secret(secret: str) -> bool:
        """Validate webhook secret format"""
        if len(secret) < 16:
            return False
        
        # Should contain at least one letter and one number
        has_letter = bool(re.search(r'[a-zA-Z]', secret))
        has_number = bool(re.search(r'[0-9]', secret))
        
        return has_letter and has_number


class DateHelper:
    """Helper class for date operations"""
    
    @staticmethod
    def get_date_range(days: int = 7) -> tuple:
        """Get date range for specified days"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date
    
    @staticmethod
    def get_hour_range(hours: int = 24) -> tuple:
        """Get hour range for specified hours"""
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=hours)
        return start_time, end_time
    
    @staticmethod
    def parse_date_string(date_string: str) -> Optional[datetime]:
        """Parse date string in various formats"""
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%m/%d/%Y',
            '%d/%m/%Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def is_business_day(date: datetime) -> bool:
        """Check if date is a business day"""
        return date.weekday() < 5  # Monday-Friday
    
    @staticmethod
    def add_business_days(date: datetime, days: int) -> datetime:
        """Add business days to date"""
        result = date
        business_days_added = 0
        
        while business_days_added < days:
            result += timedelta(days=1)
            if DateHelper.is_business_day(result):
                business_days_added += 1
        
        return result

    @staticmethod
    def format_datetime(dt: datetime, format_type: str = 'iso') -> str:
        """Format a datetime as 'iso', 'readable', 'date', or 'time'"""
        if format_type == 'readable':
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        elif format_type == 'date':
            return dt.strftime('%Y-%m-%d')
        elif format_type == 'time':
            return dt.strftime('%H:%M:%S')
        return dt.isoformat()

    @staticmethod
    def get_period_range(period: str = 'today') -> tuple:
        """Get (start, end) datetime range for a named period"""
        now = timezone.now()
        if period == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, now
        elif period == 'week':
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            return start, now
        elif period == 'month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, now
        return DateHelper.get_date_range(7)


class ConfigHelper:
    """Helper class for configuration operations"""
    
    @staticmethod
    def get_setting(key: str, default: Any = None) -> Any:
        """Get setting value with default"""
        return getattr(settings, key, default)
    
    @staticmethod
    def get_alert_config() -> Dict[str, Any]:
        """Get alert configuration"""
        return {
            'default_severity': ConfigHelper.get_setting('ALERT_DEFAULT_SEVERITY', 'medium'),
            'default_cooldown': ConfigHelper.get_setting('ALERT_DEFAULT_COOLDOWN', 30),
            'max_alerts_per_hour': ConfigHelper.get_setting('ALERT_MAX_PER_HOUR', 100),
            'notification_timeout': ConfigHelper.get_setting('ALERT_NOTIFICATION_TIMEOUT', 30),
            'retry_attempts': ConfigHelper.get_setting('ALERT_RETRY_ATTEMPTS', 3),
            'cache_timeout': ConfigHelper.get_setting('ALERT_CACHE_TIMEOUT', 300)
        }
    
    @staticmethod
    def get_webhook_config() -> Dict[str, Any]:
        """Get webhook configuration"""
        return {
            'timeout': ConfigHelper.get_setting('WEBHOOK_TIMEOUT', 30),
            'max_retries': ConfigHelper.get_setting('WEBHOOK_MAX_RETRIES', 3),
            'retry_delay': ConfigHelper.get_setting('WEBHOOK_RETRY_DELAY', 60),
            'signature_header': ConfigHelper.get_setting('WEBHOOK_SIGNATURE_HEADER', 'X-Signature'),
            'allowed_events': ConfigHelper.get_setting('WEBHOOK_ALLOWED_EVENTS', ['*'])
        }
    
    @staticmethod
    def get_pagination_config() -> Dict[str, Any]:
        """Get pagination configuration"""
        return {
            'default_page_size': ConfigHelper.get_setting('PAGINATION_DEFAULT_PAGE_SIZE', 20),
            'max_page_size': ConfigHelper.get_setting('PAGINATION_MAX_PAGE_SIZE', 100),
            'page_size_query_param': ConfigHelper.get_setting('PAGINATION_PAGE_SIZE_PARAM', 'page_size'),
            'page_query_param': ConfigHelper.get_setting('PAGINATION_PAGE_PARAM', 'page')
        }


class SecurityHelper:
    """Helper class for security operations"""
    
    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate secure API key"""
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
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
    def generate_webhook_secret(length: int = 32) -> str:
        """Generate webhook secret"""
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def sanitize_input(value: str) -> str:
        """Sanitize user input"""
        if not isinstance(value, str):
            return str(value)
        
        # Remove potential XSS
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        value = value.replace('"', '&quot;')
        value = value.replace("'", '&#x27;')
        value = value.replace('&', '&amp;')
        
        return value.strip()


class LogHelper:
    """Helper class for logging operations"""
    
    @staticmethod
    def log_alert_event(event_type: str, alert_id: int, details: Dict[str, Any] = None):
        """Log alert-related event"""
        log_data = {
            'event_type': event_type,
            'alert_id': alert_id,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        
        logger.info(f"Alert Event: {json.dumps(log_data)}")
    
    @staticmethod
    def log_notification_event(event_type: str, notification_id: int, details: Dict[str, Any] = None):
        """Log notification-related event"""
        log_data = {
            'event_type': event_type,
            'notification_id': notification_id,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        
        logger.info(f"Notification Event: {json.dumps(log_data)}")
    
    @staticmethod
    def log_system_event(event_type: str, details: Dict[str, Any] = None):
        """Log system-related event"""
        log_data = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
            'details': details or {}
        }
        
        logger.info(f"System Event: {json.dumps(log_data)}")
    
    @staticmethod
    def log_error(error: Exception, context: Dict[str, Any] = None):
        """Log error with context"""
        log_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': timezone.now().isoformat(),
            'context': context or {}
        }
        
        logger.error(f"Error: {json.dumps(log_data)}")


# Utility functions
def get_client_ip(request) -> str:
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or 'unknown'


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


def truncate_string(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate string to specified length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def deep_merge_dict(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result


def is_json_serializable(obj: Any) -> bool:
    """Check if object is JSON serializable"""
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


def safe_json_loads(json_string: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON string"""
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return None
