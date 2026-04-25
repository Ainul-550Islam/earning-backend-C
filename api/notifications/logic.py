# earning_backend/api/notifications/logic.py
"""
Logic — Pure business logic functions for the notification system.
No Django model dependencies — only data transformation and decision logic.
These functions are easily unit-tested without DB setup.
"""
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone


def should_send_notification(priority: str, is_fatigued: bool,
                              is_opted_out: bool, is_dnd_active: bool) -> Tuple[bool, str]:
    """
    Core send decision logic — determines whether a notification should be sent.
    Returns (should_send: bool, reason: str).
    """
    if priority == 'critical':
        return True, 'critical_bypasses_all'
    if is_opted_out:
        return False, 'opted_out'
    if priority == 'urgent':
        return True, 'urgent_bypasses_fatigue_and_dnd'
    if is_fatigued:
        return False, 'user_fatigued'
    if is_dnd_active and priority not in ('high', 'urgent', 'critical'):
        return False, 'dnd_active'
    return True, 'allowed'


def calculate_optimal_batch_size(total_users: int, channel: str) -> int:
    """Calculate the optimal batch size for bulk notification sending."""
    limits = {'push': 500, 'email': 100, 'sms': 50, 'in_app': 1000, 'default': 200}
    return limits.get(channel, limits['default'])


def calculate_retry_delay(attempt: int, base: int = 60, cap: int = 3600) -> int:
    """Exponential backoff delay in seconds."""
    import random
    delay = min(base * (2 ** (attempt - 1)), cap)
    return int(delay + random.uniform(0, delay * 0.1))


def group_notifications_by_user(notifications: list) -> Dict[int, list]:
    """Group a list of Notification objects by user_id."""
    groups: Dict[int, list] = {}
    for n in notifications:
        uid = getattr(n, 'user_id', None)
        if uid:
            groups.setdefault(uid, []).append(n)
    return groups


def calculate_delivery_rate(sent: int, delivered: int) -> float:
    if sent == 0:
        return 0.0
    return round(delivered / sent * 100, 2)


def calculate_open_rate(delivered: int, opened: int) -> float:
    if delivered == 0:
        return 0.0
    return round(opened / delivered * 100, 2)


def calculate_click_rate(opened: int, clicked: int) -> float:
    if opened == 0:
        return 0.0
    return round(clicked / opened * 100, 2)


def determine_winner(variant_a_stats: dict, variant_b_stats: dict, metric: str = 'open_rate') -> str:
    """Determine A/B test winner based on metric. Returns 'a' or 'b'."""
    a_val = variant_a_stats.get(metric, 0) or 0
    b_val = variant_b_stats.get(metric, 0) or 0
    return 'a' if a_val >= b_val else 'b'


def is_bdphone(phone: str) -> bool:
    import re
    return bool(re.match(r'^(?:\+?880|0088|0)?1[3-9]\d{8}$', phone.strip().replace(' ', '')))


def get_notification_sound(notification_type: str) -> str:
    """Return the notification sound name for a given type."""
    sound_map = {
        'withdrawal_success': 'money_received', 'task_approved': 'success',
        'level_up': 'level_up', 'achievement_unlocked': 'achievement',
        'fraud_detected': 'urgent_alert', 'account_suspended': 'urgent_alert',
        'login_new_device': 'security', 'low_balance': 'warning',
        'daily_reward': 'reward', 'streak_reward': 'streak',
    }
    return sound_map.get(notification_type, 'default')


def truncate_notification_message(message: str, max_chars: int = 100) -> str:
    """Truncate message for push notification preview."""
    if len(message) <= max_chars:
        return message
    return message[:max_chars - 3].rstrip() + '...'


def build_notification_metadata(user, extra: dict = None) -> dict:
    """Build standard metadata dict for a notification."""
    meta = {
        'user_id': getattr(user, 'pk', None),
        'username': getattr(user, 'username', ''),
        'created_at': timezone.now().isoformat(),
    }
    if extra:
        meta.update(extra)
    return meta
