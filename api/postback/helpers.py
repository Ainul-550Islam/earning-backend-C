"""
helpers.py – Helper functions and utilities for postback module.

Provides comprehensive helper functionality including:
- Data processing helpers
- Validation helpers
- Format helpers
- Utility functions
"""
from django.core.cache import cache
import logging
import json
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.core.validators import URLValidator, EmailValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus, RejectionReason
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class DataHelper:
    """Helper class for data processing operations."""
    
    @staticmethod
    def safe_json_loads(json_string: str, default: Any = None) -> Any:
        """
        Safely load JSON string.
        
        Args:
            json_string: JSON string to load
            default: Default value if loading fails
            
        Returns:
            Loaded JSON data or default
        """
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return default
    
    @staticmethod
    def safe_json_dumps(data: Any, default: str = "{}") -> str:
        """
        Safely dump data to JSON string.
        
        Args:
            data: Data to dump
            default: Default value if dumping fails
            
        Returns:
            JSON string or default
        """
        try:
            return json.dumps(data, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
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
                result[key] = DataHelper.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """
        Flatten nested dictionary.
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key for nested keys
            sep: Separator for keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(DataHelper.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    @staticmethod
    def extract_fields(data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """
        Extract specific fields from dictionary.
        
        Args:
            data: Source dictionary
            fields: Fields to extract
            
        Returns:
            Dictionary with extracted fields
        """
        return {field: data.get(field) for field in fields if field in data}
    
    @staticmethod
    def remove_null_values(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove null values from dictionary.
        
        Args:
            data: Dictionary to clean
            
        Returns:
            Cleaned dictionary
        """
        return {k: v for k, v in data.items() if v is not None}
    
    @staticmethod
    def convert_decimal_to_float(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Decimal fields to float for JSON serialization.
        
        Args:
            data: Dictionary to convert
            
        Returns:
            Converted dictionary
        """
        result = {}
        
        for key, value in data.items():
            if isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, dict):
                result[key] = DataHelper.convert_decimal_to_float(value)
            elif isinstance(value, list):
                result[key] = [
                    float(item) if isinstance(item, Decimal) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def batch_process(items: List[Any], batch_size: int, process_func: callable) -> List[Any]:
        """
        Process items in batches.
        
        Args:
            items: Items to process
            batch_size: Batch size
            process_func: Processing function
            
        Returns:
            List of processed results
        """
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_result = process_func(batch)
            results.extend(batch_result)
        
        return results


class ValidationHelper:
    """Helper class for validation operations."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid
        """
        try:
            EmailValidator()(email)
            return True
        except ValidationError:
            return False
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid
        """
        try:
            URLValidator()(url)
            return True
        except ValidationError:
            return False
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """
        Validate IP address.
        
        Args:
            ip: IP address to validate
            
        Returns:
            True if valid
        """
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """
        Validate UUID string.
        
        Args:
            uuid_string: UUID string to validate
            
        Returns:
            True if valid
        """
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_json_structure(data: Any, required_keys: List[str] = None) -> tuple:
        """
        Validate JSON structure.
        
        Args:
            data: Data to validate
            required_keys: Required keys
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(data, dict):
            return False, "Data must be a dictionary"
        
        if required_keys:
            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                return False, f"Missing required keys: {', '.join(missing_keys)}"
        
        return True, ""
    
    @staticmethod
    def validate_postback_data(data: Dict[str, Any]) -> tuple:
        """
        Validate postback data structure.
        
        Args:
            data: Postback data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ['network_key', 'lead_id']
        
        # Check required fields
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        
        # Validate network key format
        network_key = data.get('network_key')
        if not isinstance(network_key, str) or len(network_key) < 3:
            return False, "Invalid network_key format"
        
        # Validate lead ID format
        lead_id = data.get('lead_id')
        if not isinstance(lead_id, str) or len(lead_id) < 1:
            return False, "Invalid lead_id format"
        
        # Validate payout if present
        payout = data.get('payout')
        if payout is not None:
            try:
                payout_value = float(payout)
                if payout_value < 0:
                    return False, "Payout cannot be negative"
            except (ValueError, TypeError):
                return False, "Invalid payout format"
        
        return True, ""
    
    @staticmethod
    def validate_date_range(start_date: datetime, end_date: datetime) -> tuple:
        """
        Validate date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if start_date >= end_date:
            return False, "Start date must be before end date"
        
        if end_date > timezone.now():
            return False, "End date cannot be in the future"
        
        return True, ""


class FormatHelper:
    """Helper class for formatting operations."""
    
    @staticmethod
    def format_currency(amount: Union[float, Decimal, int], currency: str = 'USD') -> str:
        """
        Format amount as currency.
        
        Args:
            amount: Amount to format
            currency: Currency code
            
        Returns:
            Formatted currency string
        """
        try:
            amount_float = float(amount)
            return f"{currency} {amount_float:,.2f}"
        except (ValueError, TypeError):
            return f"{currency} 0.00"
    
    @staticmethod
    def format_percentage(value: Union[float, Decimal, int], decimals: int = 2) -> str:
        """
        Format value as percentage.
        
        Args:
            value: Value to format
            decimals: Number of decimal places
            
        Returns:
            Formatted percentage string
        """
        try:
            value_float = float(value)
            return f"{value_float:.{decimals}f}%"
        except (ValueError, TypeError):
            return f"0.{'0' * decimals}%"
    
    @staticmethod
    def format_number(value: Union[int, float, Decimal], decimals: int = 2) -> str:
        """
        Format number with thousands separator.
        
        Args:
            value: Value to format
            decimals: Number of decimal places
            
        Returns:
            Formatted number string
        """
        try:
            if isinstance(value, int):
                return f"{value:,}"
            else:
                value_float = float(value)
                return f"{value_float:,.{decimals}f}"
        except (ValueError, TypeError):
            return "0"
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted file size string
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
    
    @staticmethod
    def format_duration(seconds: Union[int, float]) -> str:
        """
        Format duration in human readable format.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h"
        else:
            days = seconds // 86400
            return f"{days}d"
    
    @staticmethod
    def format_datetime(dt: datetime, format_type: str = 'iso') -> str:
        """
        Format datetime.
        
        Args:
            dt: DateTime to format
            format_type: Format type ('iso', 'readable', 'date', 'time')
            
        Returns:
            Formatted datetime string
        """
        if format_type == 'iso':
            return dt.isoformat()
        elif format_type == 'readable':
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif format_type == 'date':
            return dt.strftime("%Y-%m-%d")
        elif format_type == 'time':
            return dt.strftime("%H:%M:%S")
        else:
            return dt.isoformat()
    
    @staticmethod
    def format_phone_number(phone: str) -> str:
        """
        Format phone number.
        
        Args:
            phone: Phone number to format
            
        Returns:
            Formatted phone number
        """
        # Remove non-digit characters
        digits = ''.join(filter(str.isdigit, phone))
        
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return phone


class SecurityHelper:
    """Helper class for security operations."""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate secure random token.
        
        Args:
            length: Token length
            
        Returns:
            Secure token string
        """
        import secrets
        import string
        
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def generate_uuid() -> str:
        """
        Generate UUID.
        
        Returns:
            UUID string
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def hash_string(text: str, salt: str = None) -> str:
        """
        Hash string with optional salt.
        
        Args:
            text: Text to hash
            salt: Optional salt
            
        Returns:
            Hashed string
        """
        if salt:
            text = f"{salt}{text}"
        
        return hashlib.sha256(text.encode()).hexdigest()
    
    @staticmethod
    def verify_hash(text: str, hashed: str, salt: str = None) -> bool:
        """
        Verify hash against original text.
        
        Args:
            text: Original text
            hashed: Hashed string
            salt: Optional salt
            
        Returns:
            True if hash matches
        """
        return SecurityHelper.hash_string(text, salt) == hashed
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """
        Mask sensitive data.
        
        Args:
            data: Data to mask
            mask_char: Character to use for masking
            visible_chars: Number of visible characters at end
            
        Returns:
            Masked data
        """
        if len(data) <= visible_chars:
            return data
        
        masked_length = len(data) - visible_chars
        return mask_char * masked_length + data[-visible_chars:]
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        Sanitize user input.
        
        Args:
            text: Input text
            
        Returns:
            Sanitized text
        """
        import re
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', text)
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized


class CacheHelper:
    """Helper class for cache operations."""
    
    @staticmethod
    def get_cache_key(prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key.
        
        Args:
            prefix: Key prefix
            *args: Key arguments
            **kwargs: Key keyword arguments
            
        Returns:
            Cache key string
        """
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        
        return ':'.join(key_parts)
    
    @staticmethod
    def cache_result(key: str, data: Any, timeout: int = 300):
        """
        Cache result with timeout.
        
        Args:
            key: Cache key
            data: Data to cache
            timeout: Cache timeout
        """
        cache.set(key, data, timeout)
    
    @staticmethod
    def get_cached_result(key: str, default: Any = None):
        """
        Get cached result.
        
        Args:
            key: Cache key
            default: Default value
            
        Returns:
            Cached data or default
        """
        return cache.get(key, default)
    
    @staticmethod
    def invalidate_cache(key_pattern: str):
        """
        Invalidate cache keys matching pattern.
        
        Args:
            key_pattern: Cache key pattern
        """
        # This is a simplified implementation
        # In production, you might use cache.delete_pattern()
        cache.delete(key_pattern)
    
    @staticmethod
    def cache_with_tags(key: str, data: Any, tags: List[str], timeout: int = 300):
        """
        Cache data with tags for easy invalidation.
        
        Args:
            key: Cache key
            data: Data to cache
            tags: Cache tags
            timeout: Cache timeout
        """
        # Store main data
        cache.set(key, data, timeout)
        
        # Store tag references
        for tag in tags:
            tag_key = f"tag:{tag}"
            tagged_keys = cache.get(tag_key, [])
            tagged_keys.append(key)
            cache.set(tag_key, tagged_keys, timeout)
    
    @staticmethod
    def invalidate_by_tags(tags: List[str]):
        """
        Invalidate cache by tags.
        
        Args:
            tags: Tags to invalidate
        """
        for tag in tags:
            tag_key = f"tag:{tag}"
            tagged_keys = cache.get(tag_key, [])
            
            for key in tagged_keys:
                cache.delete(key)
            
            cache.delete(tag_key)


class DatabaseHelper:
    """Helper class for database operations."""
    
    @staticmethod
    def bulk_create_with_integrity(queryset, objects: List[Any]):
        """
        Bulk create objects with integrity hash generation.
        
        Args:
            queryset: QuerySet
            objects: Objects to create
            
        Returns:
            Created objects
        """
        with transaction.atomic():
            # Generate integrity hashes
            for obj in objects:
                if hasattr(obj, 'generate_integrity_hash'):
                    obj.generate_integrity_hash()
            
            return queryset.bulk_create(objects)
    
    @staticmethod
    def safe_get_or_none(model_class, **kwargs):
        """
        Safely get object or return None.
        
        Args:
            model_class: Model class
            **kwargs: Filter parameters
            
        Returns:
            Model instance or None
        """
        try:
            return model_class.objects.get(**kwargs)
        except model_class.DoesNotExist:
            return None
    
    @staticmethod
    def safe_get_or_create(model_class, defaults: Dict[str, Any] = None, **kwargs):
        """
        Safely get or create object.
        
        Args:
            model_class: Model class
            defaults: Default values
            **kwargs: Filter parameters
            
        Returns:
            Tuple of (object, created)
        """
        try:
            return model_class.objects.get(**kwargs), False
        except model_class.DoesNotExist:
            create_kwargs = kwargs.copy()
            if defaults:
                create_kwargs.update(defaults)
            
            return model_class.objects.create(**create_kwargs), True
    
    @staticmethod
    def update_with_timestamp(queryset, **kwargs):
        """
        Update objects with timestamp.
        
        Args:
            queryset: QuerySet to update
            **kwargs: Update fields
            
        Returns:
            Number of updated rows
        """
        kwargs['updated_at'] = timezone.now()
        return queryset.update(**kwargs)
    
    @staticmethod
    def soft_delete(queryset):
        """
        Soft delete objects if they support it.
        
        Args:
            queryset: QuerySet to delete
            
        Returns:
            Number of deleted rows
        """
        if hasattr(queryset.model, 'deleted_at'):
            return queryset.update(deleted_at=timezone.now())
        else:
            return queryset.delete()


# Global helper functions
def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """Safely load JSON string."""
    return DataHelper.safe_json_loads(json_string, default)


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """Safely dump data to JSON string."""
    return DataHelper.safe_json_dumps(data, default)


def validate_postback_data(data: Dict[str, Any]) -> tuple:
    """Validate postback data structure."""
    return ValidationHelper.validate_postback_data(data)


def format_currency(amount: Union[float, Decimal, int], currency: str = 'USD') -> str:
    """Format amount as currency."""
    return FormatHelper.format_currency(amount, currency)


def generate_secure_token(length: int = 32) -> str:
    """Generate secure random token."""
    return SecurityHelper.generate_secure_token(length)


def generate_uuid() -> str:
    """Generate UUID."""
    return SecurityHelper.generate_uuid()


def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """Mask sensitive data."""
    return SecurityHelper.mask_sensitive_data(data, mask_char, visible_chars)


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate cache key."""
    return CacheHelper.get_cache_key(prefix, *args, **kwargs)


def cache_result(key: str, data: Any, timeout: int = 300):
    """Cache result with timeout."""
    return CacheHelper.cache_result(key, data, timeout)


def get_cached_result(key: str, default: Any = None):
    """Get cached result."""
    return CacheHelper.get_cached_result(key, default)


def safe_get_or_none(model_class, **kwargs):
    """Safely get object or return None."""
    return DatabaseHelper.safe_get_or_none(model_class, **kwargs)


def safe_get_or_create(model_class, defaults: Dict[str, Any] = None, **kwargs):
    """Safely get or create object."""
    return DatabaseHelper.safe_get_or_create(model_class, defaults, **kwargs)


# Utility functions for common operations
def extract_postback_fields(raw_data: Dict[str, Any], required_fields: List[str] = None) -> Dict[str, Any]:
    """
    Extract and validate postback fields from raw data.
    
    Args:
        raw_data: Raw postback data
        required_fields: Required fields list
        
    Returns:
        Extracted and validated fields
    """
    if required_fields is None:
        required_fields = ['network_key', 'lead_id']
    
    extracted = {}
    
    for field in required_fields:
        value = raw_data.get(field)
        if value is None:
            raise PostbackException(f"Missing required field: {field}")
        extracted[field] = value
    
    # Extract optional fields
    optional_fields = ['offer_id', 'payout', 'custom_fields']
    for field in optional_fields:
        if field in raw_data:
            extracted[field] = raw_data[field]
    
    return extracted


def calculate_conversion_rate(total_received: int, total_rewarded: int) -> float:
    """
    Calculate conversion rate.
    
    Args:
        total_received: Total received postbacks
        total_rewarded: Total rewarded postbacks
        
    Returns:
        Conversion rate as percentage
    """
    if total_received == 0:
        return 0.0
    
    return (total_rewarded / total_received) * 100


def calculate_health_score(insight_data: Dict[str, Any]) -> float:
    """
    Calculate health score for insight.
    
    Args:
        insight_data: Insight data
        
    Returns:
        Health score (0-100)
    """
    received_count = insight_data.get('received_count', 0)
    rewarded_count = insight_data.get('rewarded_count', 0)
    rejected_count = insight_data.get('rejected_count', 0)
    
    if received_count == 0:
        return 0.0
    
    # Base score from conversion rate
    conversion_rate = calculate_conversion_rate(received_count, rewarded_count)
    base_score = min(conversion_rate, 100.0)
    
    # Penalty for high rejection rate
    rejection_rate = (rejected_count / received_count) * 100
    rejection_penalty = min(rejection_rate * 0.5, 20.0)
    
    # Final health score
    health_score = max(0.0, base_score - rejection_penalty)
    
    return round(health_score, 2)


def detect_anomaly(current_value: float, historical_values: List[float], threshold: float = 2.0) -> bool:
    """
    Detect anomaly in data.
    
    Args:
        current_value: Current value
        historical_values: Historical values
        threshold: Anomaly threshold (standard deviations)
        
    Returns:
        True if anomaly detected
    """
    if len(historical_values) < 3:
        return False
    
    import statistics
    
    mean = statistics.mean(historical_values)
    std_dev = statistics.stdev(historical_values)
    
    if std_dev == 0:
        return False
    
    z_score = abs(current_value - mean) / std_dev
    return z_score > threshold


def format_postback_response(postback_log: PostbackLog, include_details: bool = False) -> Dict[str, Any]:
    """
    Format postback log for response.
    
    Args:
        postback_log: Postback log instance
        include_details: Whether to include detailed fields
        
    Returns:
        Formatted postback data
    """
    data = {
        'id': str(postback_log.id),
        'network_key': postback_log.network.network_key,
        'status': postback_log.status,
        'lead_id': postback_log.lead_id,
        'offer_id': postback_log.offer_id,
        'payout': float(postback_log.payout) if postback_log.payout else None,
        'received_at': postback_log.received_at.isoformat(),
        'processed_at': postback_log.processed_at.isoformat() if postback_log.processed_at else None,
    }
    
    if include_details:
        data.update({
            'source_ip': postback_log.source_ip,
            'user_agent': postback_log.user_agent,
            'rejection_reason': postback_log.rejection_reason,
            'raw_payload': postback_log.raw_payload,
            'extracted_fields': postback_log.extracted_fields,
            'integrity_hash': postback_log.integrity_hash,
        })
    
    return data


# Logging helper
def log_postback_event(event_type: str, postback_log: PostbackLog, extra_data: Dict[str, Any] = None):
    """
    Log postback event.
    
    Args:
        event_type: Type of event
        postback_log: Postback log instance
        extra_data: Additional data to log
    """
    log_data = {
        'event_type': event_type,
        'postback_id': str(postback_log.id),
        'network_key': postback_log.network.network_key,
        'status': postback_log.status,
        'lead_id': postback_log.lead_id,
        'timestamp': timezone.now().isoformat(),
    }
    
    if extra_data:
        log_data.update(extra_data)
    
    logger.info(f"Postback event: {event_type}", extra=log_data)
