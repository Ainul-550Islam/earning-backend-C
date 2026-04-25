# earning_backend/api/notifications/helpers.py
"""
Helpers — Utility helper functions for the notification system.

Pure utility functions used across models, services, tasks and views.
No heavy Django dependencies — fast to import anywhere.
"""

import hashlib
import html
import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def truncate(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if not text:
        return ''
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)].rstrip() + suffix


def truncate_push(text: str, channel: str = 'push') -> str:
    """Truncate text to channel-appropriate length for push notifications."""
    limits = {'push': 100, 'sms': 160, 'email': 998, 'in_app': 500, 'slack': 3000}
    return truncate(text, limits.get(channel, 200))


def sanitize_html(text: str) -> str:
    """Escape HTML entities and strip script tags from notification content."""
    if not text:
        return ''
    # Remove script and style tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Escape remaining HTML
    return html.escape(text.strip())


def slugify_notification_type(notification_type: str) -> str:
    """Convert 'task_approved' → 'task-approved' for URL usage."""
    return notification_type.replace('_', '-').lower()


def render_template(template: str, context: Dict) -> str:
    """
    Render a simple {variable} template string with context dict.
    Falls back gracefully if variables are missing.
    """
    try:
        return template.format(**context)
    except (KeyError, ValueError, IndexError):
        # Replace missing variables with empty string
        def replace_missing(m):
            key = m.group(1)
            return str(context.get(key, ''))
        return re.sub(r'\{(\w+)\}', replace_missing, template)


def format_amount(amount: Union[int, float], currency: str = 'BDT') -> str:
    """Format an amount with currency symbol for notification messages."""
    currency_symbols = {
        'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£',
        'INR': '₹', 'SAR': '﷼', 'AED': 'د.إ',
    }
    symbol = currency_symbols.get(currency.upper(), currency)
    if isinstance(amount, float):
        formatted = f'{amount:,.2f}'
    else:
        formatted = f'{int(amount):,}'
    return f'{symbol}{formatted}'


def generate_idempotency_key(*args) -> str:
    """Generate a deterministic idempotency key from input arguments."""
    content = ':'.join(str(a) for a in args)
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def generate_notification_id() -> str:
    """Generate a unique notification reference ID."""
    return f'NID-{uuid.uuid4().hex[:12].upper()}'


def obfuscate_phone(phone: str) -> str:
    """Obfuscate a phone number for display: 01712345678 → 017*****678"""
    if not phone or len(phone) < 6:
        return phone
    return phone[:3] + '*' * (len(phone) - 6) + phone[-3:]


def obfuscate_email(email: str) -> str:
    """Obfuscate an email for display: user@example.com → us**@example.com"""
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    visible = min(2, len(local))
    return local[:visible] + '*' * (len(local) - visible) + '@' + domain


def normalize_bd_phone(phone: str) -> str:
    """
    Normalize a Bangladesh phone number to 01XXXXXXXXX format.
    Handles: +8801X, 8801X, 01X formats.
    """
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if cleaned.startswith('+880'):
        cleaned = '0' + cleaned[4:]
    elif cleaned.startswith('880'):
        cleaned = '0' + cleaned[3:]
    elif cleaned.startswith('0088'):
        cleaned = '0' + cleaned[4:]
    return cleaned


def phone_to_international_bd(phone: str) -> str:
    """Convert BD phone to international format: 01712345678 → +8801712345678"""
    normalized = normalize_bd_phone(phone)
    if normalized.startswith('0'):
        return '+880' + normalized[1:]
    return phone


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def chunk_list(lst: list, size: int) -> List[list]:
    """Split a list into chunks of `size`. Used for batch processing."""
    if size <= 0:
        return [lst]
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def deduplicate_list(lst: list) -> list:
    """Remove duplicates from a list while preserving order."""
    seen = set()
    return [x for x in lst if not (x in seen or seen.add(x))]


def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    """
    Flatten a nested dict.
    {'a': {'b': 1}} → {'a.b': 1}
    """
    items = []
    for k, v in d.items():
        new_key = f'{parent_key}{sep}{k}' if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def merge_dicts(*dicts) -> dict:
    """Deep-merge multiple dicts. Later dicts override earlier ones."""
    result = {}
    for d in dicts:
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = merge_dicts(result[k], v)
            else:
                result[k] = v
    return result


def safe_json_loads(text: str, default=None) -> Any:
    """Parse JSON string, returning default on error."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def safe_get(d: dict, *keys, default=None) -> Any:
    """Safely traverse nested dict: safe_get(d, 'a', 'b', 'c', default=0)"""
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is default:
            return default
    return current


# ---------------------------------------------------------------------------
# Type conversion helpers
# ---------------------------------------------------------------------------

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = '') -> str:
    if value is None:
        return default
    return str(value)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def time_ago(dt: datetime) -> str:
    """Human-readable relative time string. e.g. '3 minutes ago'"""
    if dt is None:
        return 'unknown'
    now = timezone.now()
    if not timezone.is_aware(dt):
        dt = timezone.make_aware(dt)
    diff = (now - dt).total_seconds()
    if diff < 60:
        return 'just now'
    if diff < 3600:
        m = int(diff / 60)
        return f'{m} minute{"s" if m > 1 else ""} ago'
    if diff < 86400:
        h = int(diff / 3600)
        return f'{h} hour{"s" if h > 1 else ""} ago'
    if diff < 604800:
        d = int(diff / 86400)
        return f'{d} day{"s" if d > 1 else ""} ago'
    if diff < 2592000:
        w = int(diff / 604800)
        return f'{w} week{"s" if w > 1 else ""} ago'
    m = int(diff / 2592000)
    return f'{m} month{"s" if m > 1 else ""} ago'


def to_local_time(dt: datetime, timezone_str: str = 'Asia/Dhaka') -> datetime:
    """Convert a UTC datetime to a local timezone datetime."""
    try:
        import pytz
        tz = pytz.timezone(timezone_str)
        if not timezone.is_aware(dt):
            dt = timezone.make_aware(dt, pytz.utc)
        return dt.astimezone(tz)
    except Exception:
        return dt


def is_business_hours(dt: datetime = None, timezone_str: str = 'Asia/Dhaka',
                       start_hour: int = 9, end_hour: int = 21) -> bool:
    """Check if a datetime falls within business hours (default 9am-9pm BD time)."""
    if dt is None:
        dt = timezone.now()
    local_dt = to_local_time(dt, timezone_str)
    return start_hour <= local_dt.hour < end_hour


def next_business_hour(timezone_str: str = 'Asia/Dhaka', start_hour: int = 9) -> datetime:
    """Return the next business start time in UTC."""
    try:
        import pytz
        tz = pytz.timezone(timezone_str)
        now_local = datetime.now(tz)
        if now_local.hour < start_hour:
            target = now_local.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        else:
            tomorrow = now_local + timedelta(days=1)
            target = tomorrow.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        return target.astimezone(pytz.utc).replace(tzinfo=timezone.utc)
    except Exception:
        return timezone.now() + timedelta(hours=1)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def get_or_set_cache(key: str, factory_fn, ttl: int = 300) -> Any:
    """Get from cache or call factory_fn to compute and cache the value."""
    value = cache.get(key)
    if value is not None:
        return value
    value = factory_fn()
    try:
        cache.set(key, value, ttl)
    except Exception:
        pass
    return value


def invalidate_user_notification_cache(user_id: int):
    """Invalidate all notification-related cache keys for a user."""
    keys = [
        f'notif:count:{user_id}',
        f'notif:ctx:{user_id}',
        f'notif:fatigue:{user_id}',
        f'notif:optout:{user_id}',
        f'notif:pref:{user_id}',
    ]
    cache.delete_many(keys)


# ---------------------------------------------------------------------------
# Rate limit helpers
# ---------------------------------------------------------------------------

def check_rate_limit(key: str, limit: int, window: int) -> Tuple[bool, int]:
    """
    Check if rate limit is exceeded.

    Returns:
        (is_allowed: bool, current_count: int)
    """
    cache_key = f'rl:{key}'
    current = cache.get(cache_key, 0)
    if current >= limit:
        return False, current
    if current == 0:
        cache.set(cache_key, 1, window)
    else:
        try:
            cache.incr(cache_key)
        except Exception:
            pass
    return True, current + 1


# ---------------------------------------------------------------------------
# Notification-specific helpers
# ---------------------------------------------------------------------------

def get_notification_icon(notification_type: str) -> str:
    """Return an emoji icon for a notification type."""
    icons = {
        'withdrawal_success': '💰',
        'withdrawal_rejected': '❌',
        'withdrawal_pending': '⏳',
        'withdrawal_approved': '✅',
        'task_approved': '🎉',
        'task_rejected': '❌',
        'task_completed': '✅',
        'offer_completed': '🎯',
        'kyc_approved': '✅',
        'kyc_rejected': '❌',
        'referral_reward': '🎁',
        'referral_completed': '🤝',
        'level_up': '🚀',
        'achievement_unlocked': '🏆',
        'badge_earned': '🥇',
        'daily_reward': '🎁',
        'streak_reward': '🔥',
        'login_new_device': '🔐',
        'fraud_detected': '🚨',
        'account_suspended': '⛔',
        'low_balance': '⚠️',
        'deposit_success': '💵',
        'wallet_credited': '💵',
        'announcement': '📢',
        'system_update': '⚙️',
        'survey_completed': '📝',
        'leaderboard_update': '🏅',
    }
    return icons.get(notification_type, '🔔')


def build_push_payload(notification) -> Dict:
    """
    Build a standard push notification payload dict from a Notification instance.
    Used by FCMProvider and APNsProvider.
    """
    return {
        'notification_id': str(getattr(notification, 'pk', '')),
        'type': getattr(notification, 'notification_type', 'announcement'),
        'channel': getattr(notification, 'channel', 'push'),
        'priority': getattr(notification, 'priority', 'medium'),
        'action_url': getattr(notification, 'action_url', '') or '',
        'group_id': getattr(notification, 'group_id', '') or '',
        'icon': get_notification_icon(getattr(notification, 'notification_type', '')),
        'sound': _get_sound(getattr(notification, 'notification_type', '')),
        'badge': 1,
        'timestamp': timezone.now().isoformat(),
    }


def _get_sound(notification_type: str) -> str:
    sounds = {
        'withdrawal_success': 'money_received',
        'task_approved': 'success',
        'fraud_detected': 'urgent_alert',
        'account_suspended': 'urgent_alert',
        'login_new_device': 'security',
        'level_up': 'level_up',
        'achievement_unlocked': 'achievement',
        'daily_reward': 'reward',
        'streak_reward': 'streak',
        'low_balance': 'warning',
    }
    return sounds.get(notification_type, 'default')


def estimate_read_time(message: str, wpm: int = 200) -> int:
    """Estimate read time in seconds for a notification message."""
    words = len(message.split())
    return max(1, round(words / wpm * 60))


def calculate_send_window(user_timezone: str = 'Asia/Dhaka',
                           preferred_hour: int = 9) -> datetime:
    """
    Calculate the next send window for a user based on their timezone.
    Returns UTC datetime for the next occurrence of preferred_hour in user's timezone.
    """
    try:
        import pytz
        tz = pytz.timezone(user_timezone)
        now_local = datetime.now(tz)
        target = now_local.replace(hour=preferred_hour, minute=0, second=0, microsecond=0)
        if target <= now_local:
            target += timedelta(days=1)
        return target.astimezone(pytz.utc).replace(tzinfo=timezone.utc)
    except Exception:
        return timezone.now() + timedelta(hours=1)


def get_channel_display(channel: str) -> str:
    """Return a human-readable channel name."""
    display = {
        'in_app': 'In-App', 'push': 'Push Notification',
        'email': 'Email', 'sms': 'SMS', 'telegram': 'Telegram',
        'whatsapp': 'WhatsApp', 'browser': 'Browser Push',
        'slack': 'Slack', 'discord': 'Discord', 'all': 'All Channels',
    }
    return display.get(channel, channel.title())


def get_priority_display(priority: str) -> str:
    """Return a human-readable priority label."""
    labels = {
        'lowest': 'Lowest', 'low': 'Low', 'medium': 'Medium',
        'high': 'High', 'urgent': 'Urgent', 'critical': 'Critical',
    }
    return labels.get(priority, priority.title())


def notification_to_dict(notification) -> Dict:
    """Serialize a Notification instance to a lightweight dict for WebSocket/API."""
    return {
        'id': getattr(notification, 'pk', None),
        'title': getattr(notification, 'title', ''),
        'message': getattr(notification, 'message', ''),
        'notification_type': getattr(notification, 'notification_type', ''),
        'channel': getattr(notification, 'channel', 'in_app'),
        'priority': getattr(notification, 'priority', 'medium'),
        'is_read': getattr(notification, 'is_read', False),
        'is_pinned': getattr(notification, 'is_pinned', False),
        'action_url': getattr(notification, 'action_url', '') or '',
        'icon': get_notification_icon(getattr(notification, 'notification_type', '')),
        'time_ago': time_ago(getattr(notification, 'created_at', None)),
        'created_at': (
            getattr(notification, 'created_at', None).isoformat()
            if getattr(notification, 'created_at', None) else None
        ),
    }


# ---------------------------------------------------------------------------
# Retry / exponential backoff
# ---------------------------------------------------------------------------

def exponential_backoff(attempt: int, base: int = 60, cap: int = 3600,
                         jitter: bool = True) -> int:
    """
    Calculate exponential backoff delay in seconds.

    attempt=1 → 60s, attempt=2 → 120s, attempt=3 → 240s, ... cap=3600s
    """
    import random
    delay = min(base * (2 ** (attempt - 1)), cap)
    if jitter:
        delay += random.uniform(0, delay * 0.1)
    return int(delay)


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

class Timer:
    """Context manager for timing code blocks."""

    def __init__(self, name: str = '', log: bool = True):
        self.name = name
        self.log = log
        self.elapsed_ms = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.monotonic() - self._start) * 1000
        if self.log and self.name:
            logger.debug(f'Timer [{self.name}]: {self.elapsed_ms:.2f}ms')

    def __str__(self):
        return f'{self.elapsed_ms:.2f}ms'


def mask_sensitive_data(data: dict) -> dict:
    """
    Mask sensitive fields in a dict for safe logging.
    e.g. token, password, fcm_token → 'fcm_****'
    """
    SENSITIVE = {'password', 'token', 'secret', 'key', 'fcm_token', 'apns_token',
                 'api_key', 'auth_token', 'access_token', 'refresh_token',
                 'credit_card', 'ssn', 'bank_account', 'webhook_secret'}
    masked = {}
    for k, v in data.items():
        if any(s in k.lower() for s in SENSITIVE):
            if isinstance(v, str) and len(v) > 8:
                masked[k] = v[:4] + '****' + v[-4:]
            else:
                masked[k] = '****'
        elif isinstance(v, dict):
            masked[k] = mask_sensitive_data(v)
        else:
            masked[k] = v
    return masked
