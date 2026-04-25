"""
api/ad_networks/helpers.py
Helper functions for ad networks module
SaaS-ready with tenant support
"""

import logging
import json
import hashlib
import uuid
import random
import string
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest
from django.core.exceptions import ValidationError

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, OfferClick, OfferTag
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== STRING HELPERS ====================

def generate_unique_id(prefix: str = '', length: int = 8) -> str:
    """
    Generate unique ID with prefix
    """
    unique_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}_{unique_id}" if prefix else unique_id


def generate_tracking_id() -> str:
    """
    Generate unique tracking ID for offers
    """
    timestamp = int(timezone.now().timestamp())
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"track_{timestamp}_{random_str}"


def generate_referral_code(user_id: int = None) -> str:
    """
    Generate unique referral code
    """
    base_str = str(user_id or random.randint(1000, 9999))
    random_str = ''.join(random.choices(string.ascii_uppercase, k=4))
    return f"{base_str}{random_str}"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for secure storage
    """
    # Remove special characters
    sanitized = ''.join(c for c in filename if c.isalnum() or c in '._-')
    
    # Limit length
    if len(sanitized) > 100:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:50] + f".{ext}" if ext else name[:50]
    
    return sanitized


def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """
    Mask sensitive data like API keys
    """
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    return data[:visible_chars] + mask_char * (len(data) - visible_chars)


# ==================== CURRENCY HELPERS ====================

def format_currency_amount(amount: Union[Decimal, float, int], currency: str = 'BDT') -> str:
    """
    Format currency amount with proper formatting
    """
    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    
    # Format with 2 decimal places
    formatted_amount = f"{amount:,.2f}"
    
    # Add currency symbol
    currency_symbols = {
        'BDT': 'BDT',
        'USD': '$',
        'EUR': 'EUR',
        'GBP': '£',
        'INR': 'INR',
    }
    
    symbol = currency_symbols.get(currency.upper(), currency)
    return f"{symbol} {formatted_amount}"


def calculate_commission(amount: Decimal, commission_rate: float) -> Decimal:
    """
    Calculate commission amount
    """
    return amount * Decimal(str(commission_rate))


def apply_tax(amount: Decimal, tax_rate: float) -> Decimal:
    """
    Apply tax to amount
    """
    return amount * (Decimal('1') + Decimal(str(tax_rate)))


# ==================== URL HELPERS ====================

def build_tracking_url(base_url: str, tracking_id: str, user_id: int = None, offer_id: int = None) -> str:
    """
    Build tracking URL with parameters
    """
    parsed_url = urlparse(base_url)
    
    # Get existing query parameters
    query_params = parse_qs(parsed_url.query)
    
    # Add tracking parameters
    query_params['tid'] = [tracking_id]
    if user_id:
        query_params['uid'] = [str(user_id)]
    if offer_id:
        query_params['oid'] = [str(offer_id)]
    
    # Build new query string
    new_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items()])
    
    # Rebuild URL
    new_url = urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        new_query,
        parsed_url.fragment
    ))
    
    return new_url


def validate_url(url: str) -> bool:
    """
    Validate URL format
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_domain_from_url(url: str) -> str:
    """
    Extract domain from URL
    """
    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc
    except Exception:
        return ''


# ==================== TIME HELPERS ====================

def get_time_ago_string(dt: datetime) -> str:
    """
    Get human readable time ago string
    """
    now = timezone.now()
    delta = now - dt
    
    if delta.days == 0:
        if delta.seconds < 60:
            return "just now"
        elif delta.seconds < 3600:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.days == 1:
        return "yesterday"
    elif delta.days < 30:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    elif delta.days < 365:
        months = delta.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = delta.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"


def get_start_of_day(dt: datetime = None) -> datetime:
    """
    Get start of day for given datetime
    """
    if dt is None:
        dt = timezone.now()
    
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_end_of_day(dt: datetime = None) -> datetime:
    """
    Get end of day for given datetime
    """
    if dt is None:
        dt = timezone.now()
    
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def get_date_range(days: int) -> Tuple[datetime, datetime]:
    """
    Get date range for last N days
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    return start_date, end_date


# ==================== VALIDATION HELPERS ====================

def validate_email_format(email: str) -> bool:
    """
    Validate email format
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format
    """
    import re
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a valid phone number (10-15 digits)
    return 10 <= len(digits_only) <= 15


def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address format
    """
    try:
        from ipaddress import ip_address
        ip_address(ip)
        return True
    except ValueError:
        return False


def get_client_ip(request: HttpRequest) -> str:
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    return ip


# ==================== CACHE HELPERS ====================

def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate cache key with prefix and parameters
    """
    key_parts = [prefix]
    
    # Add args to key
    for arg in args:
        key_parts.append(str(arg))
    
    # Add sorted kwargs to key
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")
    
    return ':'.join(key_parts)


def cache_result(key: str, timeout: int = 300):
    """
    Decorator to cache function results
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_key = get_cache_key(key, *args, **kwargs)
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate cache keys matching pattern
    """
    from django.core.cache import cache
    
    # This is a simplified implementation
    # In production, you might use Redis pattern matching
    keys_to_delete = []
    
    # Get all keys (cache-specific implementation)
    try:
        if hasattr(cache, 'keys'):
            keys = cache.keys(f"*{pattern}*")
            keys_to_delete.extend(keys)
    except Exception:
        pass
    
    # Delete keys
    deleted_count = 0
    for key in keys_to_delete:
        try:
            cache.delete(key)
            deleted_count += 1
        except Exception:
            pass
    
    return deleted_count


# ==================== SECURITY HELPERS ====================

def generate_csrf_token() -> str:
    """
    Generate CSRF token
    """
    return hashlib.sha256(f"{uuid.uuid4()}{timezone.now()}".encode()).hexdigest()


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Verify webhook signature
    """
    expected_signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


def hash_password(password: str) -> str:
    """
    Hash password using secure method
    """
    from django.contrib.auth.hashers import make_password
    return make_password(password)


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify password against hash
    """
    from django.contrib.auth.hashers import check_password
    return check_password(password, hashed)


# ==================== DATA PROCESSING HELPERS ====================

def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """
    Split list into chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """
    Flatten nested dictionary
    """
    items = []
    
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    
    return dict(items)


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    Safely load JSON string
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = '{}') -> str:
    """
    Safely dump object to JSON string
    """
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return default


# ==================== STATISTICS HELPERS ====================

def calculate_percentage(part: Union[int, float], total: Union[int, float]) -> float:
    """
    Calculate percentage
    """
    if total == 0:
        return 0.0
    
    return (part / total) * 100


def calculate_growth_rate(current: Union[int, float], previous: Union[int, float]) -> float:
    """
    Calculate growth rate percentage
    """
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    
    return ((current - previous) / previous) * 100


def moving_average(data: List[float], window_size: int) -> List[float]:
    """
    Calculate moving average
    """
    if len(data) < window_size:
        return data
    
    averages = []
    for i in range(len(data) - window_size + 1):
        window = data[i:i + window_size]
        averages.append(sum(window) / window_size)
    
    return averages


# ==================== TENANT HELPERS ====================

def get_tenant_from_request(request: HttpRequest) -> Optional[str]:
    """
    Extract tenant ID from request
    """
    # Try subdomain
    host = request.get_host()
    if host:
        subdomain = host.split('.')[0]
        if subdomain and subdomain != 'www':
            return subdomain
    
    # Try header
    tenant_id = request.META.get('HTTP_X_TENANT_ID')
    if tenant_id:
        return tenant_id
    
    # Try query parameter
    tenant_id = request.GET.get('tenant_id')
    if tenant_id:
        return tenant_id
    
    # Try user's tenant
    if hasattr(request.user, 'tenant_id'):
        return request.user.tenant_id
    
    return None


def is_tenant_valid(tenant_id: str) -> bool:
    """
    Check if tenant is valid
    """
    try:
        from api.tenants.models import Tenant
        return Tenant.objects.filter(tenant_id=tenant_id, is_active=True).exists()
    except Exception:
        return False


# ==================== EXPORT HELPERS ====================

def export_to_csv(data: List[Dict], filename: str) -> str:
    """
    Export data to CSV format
    """
    import csv
    from io import StringIO
    
    if not data:
        return ''
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    return output.getvalue()


def export_to_json(data: List[Dict], indent: int = 2) -> str:
    """
    Export data to JSON format
    """
    return json.dumps(data, indent=indent, default=str)


# ==================== NOTIFICATION HELPERS ====================

def send_push_notification(user_id: int, title: str, message: str, data: Dict = None) -> bool:
    """
    Send push notification to user
    """
    try:
        # This is a placeholder implementation
        # In production, integrate with push notification service
        logger.info(f"Push notification sent to user {user_id}: {title}")
        return True
    except Exception as e:
        logger.error(f"Error sending push notification: {str(e)}")
        return False


def send_email_notification(user_email: str, subject: str, message: str) -> bool:
    """
    Send email notification
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False


# ==================== DEBUG HELPERS ====================

def log_request_info(request: HttpRequest, level: str = 'info') -> None:
    """
    Log request information for debugging
    """
    log_data = {
        'method': request.method,
        'path': request.path,
        'user': request.user.username if request.user.is_authenticated else 'anonymous',
        'ip': get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'referer': request.META.get('HTTP_REFERER', ''),
    }
    
    if level == 'debug':
        logger.debug(f"Request info: {log_data}")
    elif level == 'info':
        logger.info(f"Request info: {log_data}")
    elif level == 'warning':
        logger.warning(f"Request info: {log_data}")
    elif level == 'error':
        logger.error(f"Request info: {log_data}")


def debug_model_instance(instance, fields: List[str] = None) -> Dict:
    """
    Debug model instance by returning field values
    """
    if fields is None:
        fields = [field.name for field in instance._meta.fields]
    
    debug_data = {}
    for field in fields:
        try:
            value = getattr(instance, field)
            debug_data[field] = str(value)
        except Exception:
            debug_data[field] = 'ERROR'
    
    return debug_data


# ==================== EXPORTS ====================

__all__ = [
    # String helpers
    'generate_unique_id',
    'generate_tracking_id',
    'generate_referral_code',
    'sanitize_filename',
    'mask_sensitive_data',
    
    # Currency helpers
    'format_currency_amount',
    'calculate_commission',
    'apply_tax',
    
    # URL helpers
    'build_tracking_url',
    'validate_url',
    'get_domain_from_url',
    
    # Time helpers
    'get_time_ago_string',
    'get_start_of_day',
    'get_end_of_day',
    'get_date_range',
    
    # Validation helpers
    'validate_email_format',
    'validate_phone_number',
    'validate_ip_address',
    'get_client_ip',
    
    # Cache helpers
    'get_cache_key',
    'cache_result',
    'invalidate_cache_pattern',
    
    # Security helpers
    'generate_csrf_token',
    'verify_webhook_signature',
    'hash_password',
    'verify_password',
    
    # Data processing helpers
    'chunk_list',
    'flatten_dict',
    'safe_json_loads',
    'safe_json_dumps',
    
    # Statistics helpers
    'calculate_percentage',
    'calculate_growth_rate',
    'moving_average',
    
    # Tenant helpers
    'get_tenant_from_request',
    'is_tenant_valid',
    
    # Export helpers
    'export_to_csv',
    'export_to_json',
    
    # Notification helpers
    'send_push_notification',
    'send_email_notification',
    
    # Debug helpers
    'log_request_info',
    'debug_model_instance',
]
