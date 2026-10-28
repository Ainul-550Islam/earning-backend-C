# api/admin_panel/helpers.py
"""
Admin Panel Helpers — utility functions used across all 50 modules.
No business logic here — pure helpers: formatting, conversions,
IP utilities, date helpers, pagination, response builders, caching utils.

"Do not summarize or skip any logic. Provide the full code."
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta, date

from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.response import Response

logger = logging.getLogger(__name__)
User = get_user_model()


# ===========================================================================
# RESPONSE BUILDERS
# ===========================================================================

def ok(data: Any = None, message: str = '', meta: dict = None) -> Response:
    """Standard success response."""
    return Response({
        'success':   True,
        'message':   message,
        'data':      data,
        'meta':      meta or {},
        'timestamp': timezone.now().isoformat(),
    })


def err(message: str, errors: list = None, status_code: int = 400) -> Response:
    """Standard error response."""
    return Response({
        'success':   False,
        'message':   message,
        'errors':    errors or [],
        'timestamp': timezone.now().isoformat(),
    }, status=status_code)


def paginated_ok(items: list, total: int, page: int, page_size: int, extra: dict = None) -> Response:
    """Paginated success response."""
    data = {
        'items':     items,
        'total':     total,
        'page':      page,
        'page_size': page_size,
        'pages':     (total + page_size - 1) // page_size if page_size else 1,
        'has_next':  (page * page_size) < total,
        'has_prev':  page > 1,
    }
    if extra:
        data.update(extra)
    return ok(data=data)


# ===========================================================================
# IP ADDRESS HELPERS
# ===========================================================================

def get_client_ip(request) -> str:
    """
    Extract real client IP from request.
    Handles X-Forwarded-For, X-Real-IP, REMOTE_ADDR.
    """
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        # First IP in the chain is the client
        ip = x_forwarded.split(',')[0].strip()
        if is_valid_ip(ip):
            return ip

    x_real_ip = request.META.get('HTTP_X_REAL_IP', '')
    if x_real_ip and is_valid_ip(x_real_ip):
        return x_real_ip

    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def is_valid_ip(ip: str) -> bool:
    """Check if string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_private_ip(ip: str) -> bool:
    """Check if IP is private/loopback/reserved."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local
    except ValueError:
        return False


def ip_to_int(ip: str) -> int:
    """Convert IPv4 string to integer for range comparisons."""
    try:
        return int(ipaddress.IPv4Address(ip))
    except Exception:
        return 0


def get_ip_info(ip: str) -> dict:
    """
    Get IP geolocation info from proxy_intelligence app.
    Falls back to basic info if unavailable.
    """
    cache_key = f'admin_panel:ip_info:{ip}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    info = {'ip': ip, 'country': '', 'city': '', 'isp': '', 'is_vpn': False, 'is_proxy': False}
    try:
        from api.proxy_intelligence.models import IPIntelligence
        record = IPIntelligence.objects.filter(ip_address=ip).first()
        if record:
            info.update({
                'country':  record.country_code or '',
                'city':     record.city or '',
                'isp':      record.isp or '',
                'is_vpn':   bool(record.is_vpn),
                'is_proxy': bool(record.is_proxy),
                'fraud_score': record.fraud_score or 0,
            })
    except Exception:
        pass

    cache.set(cache_key, info, 3600)
    return info


def mask_ip(ip: str) -> str:
    """Mask last octet of IPv4 for privacy display. e.g. 1.2.3.4 → 1.2.3.xxx"""
    parts = ip.split('.')
    if len(parts) == 4:
        return '.'.join(parts[:3]) + '.xxx'
    return ip


# ===========================================================================
# DATE / TIME HELPERS
# ===========================================================================

def date_range(start: date, end: date) -> List[date]:
    """Generate list of dates from start to end (inclusive)."""
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def parse_date_param(value: str, default: date = None) -> Optional[date]:
    """Parse date string (YYYY-MM-DD) from query param. Returns default on failure."""
    if not value:
        return default
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return default


def parse_datetime_param(value: str, default=None):
    """Parse datetime string. Tries ISO format first, then date-only."""
    if not value:
        return default
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(value, fmt)
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except (ValueError, TypeError):
            continue
    return default


def period_to_date_range(period: str) -> Tuple[datetime, datetime]:
    """
    Convert period string to (start, end) datetime range.
    Periods: today, yesterday, last_7d, last_30d, this_month, last_month,
             this_year, last_24h, last_48h, last_hour
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    ranges = {
        'today':       (today_start, now),
        'yesterday':   (today_start - timedelta(days=1), today_start),
        'last_hour':   (now - timedelta(hours=1), now),
        'last_24h':    (now - timedelta(hours=24), now),
        'last_48h':    (now - timedelta(hours=48), now),
        'last_7d':     (now - timedelta(days=7), now),
        'last_30d':    (now - timedelta(days=30), now),
        'last_90d':    (now - timedelta(days=90), now),
        'this_month':  (today_start.replace(day=1), now),
        'last_month':  (
            (today_start.replace(day=1) - timedelta(days=1)).replace(day=1),
            today_start.replace(day=1)
        ),
        'this_year':   (today_start.replace(month=1, day=1), now),
    }
    return ranges.get(period, (now - timedelta(days=7), now))


def human_timedelta(dt) -> str:
    """Return human-readable time difference. e.g. '2 hours ago', '3 days ago'"""
    if not dt:
        return 'never'
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f'{seconds}s ago'
    elif seconds < 3600:
        return f'{seconds // 60}m ago'
    elif seconds < 86400:
        return f'{seconds // 3600}h ago'
    elif seconds < 86400 * 30:
        return f'{diff.days}d ago'
    elif seconds < 86400 * 365:
        return f'{diff.days // 30}mo ago'
    return f'{diff.days // 365}y ago'


def format_datetime(dt, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime to string safely."""
    if not dt:
        return ''
    try:
        return dt.strftime(fmt)
    except Exception:
        return str(dt)


# ===========================================================================
# NUMBER / CURRENCY HELPERS
# ===========================================================================

def format_currency(amount: Any, currency: str = 'BDT', symbol: str = '৳') -> str:
    """Format amount as currency string. e.g. '৳1,234.56'"""
    try:
        d = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return f"{symbol}{d:,.2f}"
    except Exception:
        return f"{symbol}0.00"


def format_number(n: Any, decimals: int = 0) -> str:
    """Format number with commas. e.g. 1234567 → '1,234,567'"""
    try:
        if decimals:
            return f"{float(n):,.{decimals}f}"
        return f"{int(n):,}"
    except Exception:
        return str(n)


def percentage(part: Any, whole: Any, decimals: int = 2) -> float:
    """Safe percentage calculation. Returns 0.0 if whole is 0."""
    try:
        w = float(whole)
        if w == 0:
            return 0.0
        return round((float(part) / w) * 100, decimals)
    except Exception:
        return 0.0


def safe_divide(numerator: Any, denominator: Any, default: float = 0.0) -> float:
    """Safe division — returns default if denominator is 0."""
    try:
        d = float(denominator)
        if d == 0:
            return default
        return float(numerator) / d
    except Exception:
        return default


def round_to(value: Any, places: int = 2) -> float:
    """Round to N decimal places safely."""
    try:
        return round(float(value), places)
    except Exception:
        return 0.0


def clamp(value: Any, min_val: Any, max_val: Any) -> Any:
    """Clamp value between min and max."""
    try:
        return max(min_val, min(max_val, type(min_val)(value)))
    except Exception:
        return min_val


# ===========================================================================
# STRING HELPERS
# ===========================================================================

def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = unicodedata.normalize('NFKD', str(text))
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)


def truncate(text: str, max_len: int = 100, suffix: str = '…') -> str:
    """Truncate string to max_len chars."""
    if not text:
        return ''
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix


def mask_email(email: str) -> str:
    """Mask email for privacy display. e.g. jo***@ex***.com"""
    try:
        local, domain = email.split('@')
        domain_parts = domain.split('.')
        masked_local  = local[:2] + '***'
        masked_domain = domain_parts[0][:2] + '***'
        return f"{masked_local}@{masked_domain}.{domain_parts[-1]}"
    except Exception:
        return '***@***.***'


def mask_phone(phone: str) -> str:
    """Mask phone number. e.g. +880 1*** ***789"""
    if not phone:
        return ''
    cleaned = re.sub(r'[^\d+]', '', phone)
    if len(cleaned) >= 6:
        return cleaned[:3] + '****' + cleaned[-3:]
    return '****'


def sanitize_string(text: str, max_length: int = 500) -> str:
    """Remove dangerous characters and trim."""
    if not text:
        return ''
    text = str(text).strip()
    # Remove null bytes and control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text[:max_length]


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def extract_numbers(text: str) -> List[float]:
    """Extract all numbers from a string."""
    return [float(x) for x in re.findall(r'-?\d+\.?\d*', str(text))]


# ===========================================================================
# CACHE HELPERS
# ===========================================================================

def cached(key: str, ttl: int = 300, version: int = 1):
    """
    Decorator to cache function return value.
    Usage:
        @cached('my_key', ttl=60)
        def expensive_function():
            ...
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            full_key = f'admin_panel:{key}:{version}'
            result = cache.get(full_key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(full_key, result, ttl)
            return result
        return wrapper
    return decorator


def get_or_set_cache(key: str, callable_fn, ttl: int = 300) -> Any:
    """Get from cache or compute and cache result."""
    full_key = f'admin_panel:{key}'
    result = cache.get(full_key)
    if result is not None:
        return result
    result = callable_fn()
    if result is not None:
        cache.set(full_key, result, ttl)
    return result


def batch_delete_cache(patterns: List[str]) -> int:
    """Delete multiple cache keys. Returns count deleted."""
    count = 0
    for key in patterns:
        cache.delete(key)
        count += 1
    return count


def cache_increment(key: str, amount: int = 1, ttl: int = 3600) -> int:
    """Increment a cache counter atomically."""
    full_key = f'admin_panel:counter:{key}'
    try:
        return cache.incr(full_key, amount)
    except ValueError:
        cache.set(full_key, amount, ttl)
        return amount


# ===========================================================================
# HASHING / SECURITY HELPERS
# ===========================================================================

def hash_value(value: str, salt: str = '') -> str:
    """SHA-256 hash a value with optional salt."""
    data = f"{salt}{value}".encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    import secrets
    return secrets.token_urlsafe(length)


def mask_api_key(key: str) -> str:
    """Mask API key for display. Shows first 4 and last 4 chars."""
    if not key or len(key) < 8:
        return '****'
    return key[:4] + '****' + key[-4:]


def is_safe_redirect_url(url: str, allowed_hosts: List[str] = None) -> bool:
    """Check if a redirect URL is safe (no open redirect vulnerability)."""
    from urllib.parse import urlparse
    if not url:
        return False
    if url.startswith('/'):
        return True
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return True
        if allowed_hosts and parsed.netloc in allowed_hosts:
            return True
    except Exception:
        pass
    return False


# ===========================================================================
# QUERYSET / DB HELPERS
# ===========================================================================

def qs_to_list(queryset, fields: List[str]) -> List[Dict]:
    """Convert queryset to list of dicts with specified fields."""
    return list(queryset.values(*fields))


def paginate_queryset(queryset, page: int = 1, page_size: int = 25):
    """
    Simple queryset pagination.
    Returns (items, total, has_next, has_prev)
    """
    page = max(1, page)
    page_size = min(200, max(1, page_size))
    total = queryset.count()
    offset = (page - 1) * page_size
    items = queryset[offset:offset + page_size]
    return (
        list(items),
        total,
        (offset + page_size) < total,
        page > 1,
    )


def bulk_update_or_create(model_class, items: List[Dict], key_field: str) -> Tuple[int, int]:
    """
    Bulk update existing records, create new ones.
    Returns (created_count, updated_count)
    """
    created = updated = 0
    for item in items:
        key_val = item.get(key_field)
        if not key_val:
            continue
        _, was_created = model_class.objects.update_or_create(
            **{key_field: key_val},
            defaults={k: v for k, v in item.items() if k != key_field}
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def get_object_or_none(model_class, **kwargs):
    """Get object or return None (never raises DoesNotExist)."""
    try:
        return model_class.objects.get(**kwargs)
    except model_class.DoesNotExist:
        return None
    except Exception:
        return None


# ===========================================================================
# JSON HELPERS
# ===========================================================================

def safe_json_loads(text: str, default: Any = None) -> Any:
    """Parse JSON safely, returns default on error."""
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: Any = '') -> str:
    """Serialize to JSON safely, returns default on error."""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return default


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """Flatten nested dict. {'a': {'b': 1}} → {'a.b': 1}"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dicts. override wins on conflicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ===========================================================================
# USER HELPERS (calls api.users — never duplicates)
# ===========================================================================

def get_user_display_name(user) -> str:
    """Get best display name for a user."""
    if not user:
        return 'Unknown'
    if hasattr(user, 'get_full_name') and user.get_full_name():
        return user.get_full_name()
    return user.username


def get_user_or_none(user_id: Any):
    """Get user by PK, return None if not found."""
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None


def is_user_active(user_id: Any) -> bool:
    """Check if user is active."""
    try:
        return User.objects.filter(pk=user_id, is_active=True).exists()
    except Exception:
        return False


def get_online_users_count() -> int:
    """Get approximate count of online users from cache."""
    return cache.get('admin:users_online', 0)


# ===========================================================================
# ADMIN-SPECIFIC HELPERS
# ===========================================================================

def build_audit_payload(request, extra: Dict = None) -> Dict:
    """Build standardised audit payload from request."""
    payload = {
        'method':     request.method,
        'path':       request.path,
        'ip':         get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        'user_id':    request.user.pk if request.user.is_authenticated else None,
        'username':   request.user.username if request.user.is_authenticated else None,
        'timestamp':  timezone.now().isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload


def log_admin_action(actor, action: str, model_name: str = '',
                     object_id: str = '', changes: Dict = None,
                     status: str = 'success', ip: str = '') -> None:
    """Log admin action to AdminActivity — central helper."""
    try:
        from api.admin_panel.models.activity import AdminActivity
        AdminActivity.log(
            actor=actor, action=action, model_name=model_name,
            object_id=object_id, changes=changes or {}, status=status, ip=ip,
        )
    except Exception as e:
        logger.debug(f"[helpers.log_admin_action] {e}")


def get_admin_role(user) -> str:
    """Get admin role string for a user."""
    try:
        return user.admin_profile.role
    except Exception:
        if user.is_superuser:
            return 'superadmin'
        if user.is_staff:
            return 'admin'
        return 'viewer'


def is_maintenance_active() -> bool:
    """Check if maintenance mode is active."""
    return bool(cache.get('admin_panel:maintenance_mode_active'))


def get_maintenance_message() -> str:
    """Get current maintenance message."""
    return cache.get('admin_panel:maintenance_message', 'System maintenance in progress.')


def is_feature_enabled(flag_key: str, default: bool = False) -> bool:
    """Check feature flag from cache."""
    val = cache.get(f'admin_panel:feature_flag:{flag_key}')
    if val is not None:
        return bool(val)
    try:
        from api.admin_panel.services.FeatureFlagService import FeatureFlagService
        return FeatureFlagService.is_enabled(flag_key, default=default)
    except Exception:
        return default


def get_system_config(key: str, default: Any = None) -> Any:
    """Get system config value from cache or DB."""
    cached = cache.get(f'admin_panel:config:{key}')
    if cached is not None:
        return cached
    try:
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        return SystemConfigService.get(key, default=default)
    except Exception:
        return default


# ===========================================================================
# FILE / EXPORT HELPERS
# ===========================================================================

def get_file_extension(filename: str) -> str:
    """Get lowercase file extension."""
    import os
    _, ext = os.path.splitext(filename)
    return ext.lower().lstrip('.')


def format_file_size(size_bytes: int) -> str:
    """Format file size to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def generate_export_filename(model_name: str, fmt: str = 'csv') -> str:
    """Generate timestamped export filename."""
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    return f"{model_name.lower()}_{timestamp}.{fmt}"


# ===========================================================================
# STATS AGGREGATION HELPERS
# ===========================================================================

def compute_growth(current: float, previous: float) -> Dict:
    """Compute growth rate between two periods."""
    if previous == 0:
        return {'value': current, 'growth': None, 'trend': 'neutral'}
    growth = safe_divide(current - previous, previous) * 100
    return {
        'value':   current,
        'previous': previous,
        'growth':  round(growth, 2),
        'trend':   'up' if growth > 0 else 'down' if growth < 0 else 'neutral',
    }


def build_trend_data(queryset, date_field: str, value_field: str,
                     group_by: str = 'day') -> List[Dict]:
    """
    Build trend data (date → value) from a queryset.
    group_by: 'minute' | 'hour' | 'day' | 'week' | 'month'
    """
    from django.db.models import Count, Sum
    from django.db.models.functions import (
        TruncMinute, TruncHour, TruncDate, TruncWeek, TruncMonth
    )

    trunc_map = {
        'minute': TruncMinute,
        'hour':   TruncHour,
        'day':    TruncDate,
        'week':   TruncWeek,
        'month':  TruncMonth,
    }
    TruncFn = trunc_map.get(group_by, TruncDate)

    try:
        return list(
            queryset.annotate(period=TruncFn(date_field))
            .values('period')
            .annotate(
                count=Count('id'),
                total=Sum(value_field) if value_field != 'id' else Count('id'),
            )
            .order_by('period')
        )
    except Exception as e:
        logger.debug(f"[helpers.build_trend_data] {e}")
        return []


def summarise_queryset(queryset) -> Dict:
    """Quick summary: count, first, last created dates."""
    from django.db.models import Min, Max, Count
    try:
        agg = queryset.aggregate(
            total=Count('id'),
            first=Min('created_at'),
            last=Max('created_at'),
        )
        return {
            'total': agg['total'] or 0,
            'first': format_datetime(agg.get('first')),
            'last':  format_datetime(agg.get('last')),
        }
    except Exception:
        return {'total': queryset.count()}