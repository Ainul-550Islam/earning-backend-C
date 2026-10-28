# api/admin_panel/utils.py
"""
Utility functions for admin_panel app.
CPAlead-style earning platform admin utilities.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ==================== Cache Helpers ====================

def get_cached(key: str, timeout: int = 300) -> Optional[Any]:
    """Get a value from cache."""
    return cache.get(key)


def set_cached(key: str, value: Any, timeout: int = 300) -> None:
    """Set a value in cache."""
    cache.set(key, value, timeout)


def delete_cached(key: str) -> None:
    """Delete a value from cache."""
    cache.delete(key)


def clear_cache_prefix(prefix: str) -> None:
    """
    Delete all cache keys starting with a prefix.
    Only works if the cache backend supports key listing (Redis).
    """
    try:
        # For Django Redis cache backend
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        keys = conn.keys(f"*{prefix}*")
        if keys:
            conn.delete(*keys)
    except Exception:
        # Fallback: just log
        logger.warning(f"Could not clear cache prefix: {prefix}")


# ==================== IP Address ====================

def get_client_ip(request) -> str:
    """Extract real client IP from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first (leftmost) IP which is the client's real IP
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def get_user_agent(request) -> str:
    """Extract User-Agent string from request."""
    return request.META.get('HTTP_USER_AGENT', '')[:500]


# ==================== Pagination Helpers ====================

def paginate_queryset(queryset, page: int = 1, page_size: int = 25):
    """
    Simple in-memory paginator for querysets.
    Returns (items, total_count, total_pages, current_page).
    """
    total = queryset.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    items = queryset[offset: offset + page_size]
    return items, total, total_pages, page


# ==================== Date/Time Helpers ====================

def get_date_range(period: str):
    """
    Return (start_dt, end_dt) for a named period.
    Periods: 1h, 24h, 7d, 30d, 90d, 1y
    """
    now = timezone.now()
    mapping = {
        '1h': timedelta(hours=1),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
        '1y': timedelta(days=365),
    }
    delta = mapping.get(period, timedelta(days=7))
    return now - delta, now


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


def format_file_size(bytes_size: int) -> str:
    """Format bytes into human-readable file size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"


# ==================== JSON Helpers ====================

def safe_json_loads(value: str, default=None) -> Any:
    """Safely parse JSON string, return default on failure."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(value: Any, default='{}') -> str:
    """Safely serialize to JSON string, return default on failure."""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return default


# ==================== Hashing ====================

def generate_export_token(user_id: int, timestamp: Optional[str] = None) -> str:
    """Generate a unique token for export file access."""
    ts = timestamp or timezone.now().isoformat()
    raw = f"{user_id}:{ts}:export"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def generate_report_id() -> str:
    """Generate a short unique report ID."""
    import uuid
    return f"REP-{uuid.uuid4().hex[:8].upper()}"


# ==================== Number/Currency ====================

def format_currency(amount: Union[int, float], symbol: str = '৳') -> str:
    """Format a number as currency string."""
    return f"{symbol}{amount:,.2f}"


def percentage_change(old_val: float, new_val: float) -> Optional[float]:
    """Calculate percentage change between two values."""
    if old_val == 0:
        return None
    return round(((new_val - old_val) / abs(old_val)) * 100, 2)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(value, max_val))


# ==================== Diff / Changelog ====================

def compute_model_diff(old_data: Dict, new_data: Dict) -> Dict:
    """
    Compute the difference between two dicts (old → new).
    Returns dict of {field: {'old': ..., 'new': ...}}.
    """
    diff = {}
    all_keys = set(list(old_data.keys()) + list(new_data.keys()))
    for key in all_keys:
        old_val = old_data.get(key)
        new_val = new_data.get(key)
        if old_val != new_val:
            diff[key] = {'old': old_val, 'new': new_val}
    return diff


def serialize_model_instance(instance) -> Dict:
    """
    Serialize a model instance to a plain dict for change tracking.
    Skips non-serializable fields gracefully.
    """
    from django.forms.models import model_to_dict
    try:
        data = model_to_dict(instance)
        # Convert non-JSON-serializable types
        for k, v in data.items():
            if hasattr(v, 'isoformat'):
                data[k] = v.isoformat()
            elif hasattr(v, '__str__') and not isinstance(v, (str, int, float, bool, type(None))):
                data[k] = str(v)
        return data
    except Exception:
        return {}


# ==================== Permission Helpers ====================

def user_has_admin_role(user, *roles) -> bool:
    """
    Check if a user's admin profile has one of the given roles.
    Falls back to is_staff/is_superuser check if no profile.
    """
    if user.is_superuser:
        return True
    try:
        profile = user.admin_profile
        return profile.role in roles
    except Exception:
        return user.is_staff


def get_admin_role(user) -> str:
    """Return the admin role of a user."""
    if user.is_superuser:
        return 'superadmin'
    try:
        return user.admin_profile.role
    except Exception:
        return 'admin' if user.is_staff else 'viewer'


# ==================== Celery Helpers ====================

def run_task_async(task_path: str, *args, **kwargs):
    """
    Dynamically call a Celery task by its dotted path.
    Falls back to synchronous execution if Celery is unavailable.
    """
    try:
        from celery import current_app
        task = current_app.tasks.get(task_path)
        if task:
            return task.delay(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Celery unavailable, running task sync: {task_path} — {e}")
    # Sync fallback: import and call
    try:
        module_path, func_name = task_path.rsplit('.', 1)
        import importlib
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Task execution failed: {task_path} — {e}")


# ==================== Health Check ====================

def check_db_connection() -> Dict:
    """Check if database connection is alive."""
    try:
        from django.db import connection
        connection.ensure_connection()
        return {'status': 'healthy', 'latency_ms': None}
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_cache_connection() -> Dict:
    """Check if cache backend is alive."""
    try:
        key = 'admin_panel:health_check'
        cache.set(key, '1', 5)
        val = cache.get(key)
        if val == '1':
            return {'status': 'healthy'}
        return {'status': 'degraded', 'error': 'Cache read/write mismatch'}
    except Exception as e:
        return {'status': 'down', 'error': str(e)}


def check_celery_status() -> Dict:
    """Check if Celery workers are running."""
    try:
        from celery import current_app
        i = current_app.control.inspect(timeout=2)
        active = i.active()
        if active:
            worker_count = len(active)
            return {'status': 'healthy', 'workers': worker_count}
        return {'status': 'degraded', 'error': 'No active workers'}
    except Exception as e:
        return {'status': 'unknown', 'error': str(e)}


def get_full_system_health() -> Dict:
    """Aggregate system health from all checks."""
    checks = {
        'database': check_db_connection(),
        'cache': check_cache_connection(),
        'celery': check_celery_status(),
    }
    statuses = [v['status'] for v in checks.values()]
    if all(s == 'healthy' for s in statuses):
        overall = 'healthy'
    elif any(s == 'down' for s in statuses):
        overall = 'down'
    else:
        overall = 'degraded'
    return {
        'overall': overall,
        'checks': checks,
        'checked_at': timezone.now().isoformat(),
    }


# ==================== Notification Helpers ====================

def send_admin_email_notification(
    subject: str,
    message: str,
    recipient_list: List[str],
    html_message: Optional[str] = None,
):
    """Send an email notification to admin users."""
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Admin email send failed: {e}")
        return False


# ==================== Text Helpers ====================

def truncate_text(text: str, max_length: int = 100, ellipsis: str = '…') -> str:
    """Truncate text to max_length characters."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(ellipsis)] + ellipsis


def slugify_key(text: str) -> str:
    """Convert a string to a valid snake_case config key."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9_]', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')