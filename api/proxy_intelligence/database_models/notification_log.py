"""Notification Log — tracks sent alert notifications."""
import logging
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

MAX_LOGS_PER_IP = 20
NOTIFICATION_LOG_TTL = 86400  # 24 hours


class NotificationLog:
    """
    Lightweight notification tracker using Redis.
    Stores the last N notifications per IP/alert_type combination.
    For persistent storage, integrate with your notifications/audit model.
    """

    @staticmethod
    def record(alert_type: str, recipient: str, ip_address: str,
               channel: str = 'webhook', status: str = 'sent',
               error: str = '', tenant=None):
        """Record a sent notification."""
        key  = f"pi:notif_log:{ip_address}:{alert_type}"
        logs = cache.get(key, [])
        logs.append({
            'type':      alert_type,
            'recipient': recipient[:100],
            'channel':   channel,
            'status':    status,
            'error':     error[:200] if error else '',
            'time':      timezone.now().isoformat(),
        })
        cache.set(key, logs[-MAX_LOGS_PER_IP:], NOTIFICATION_LOG_TTL)

        if status == 'error':
            logger.warning(f"Alert notification failed: type={alert_type} channel={channel} error={error}")
        else:
            logger.debug(f"Alert sent: type={alert_type} channel={channel} to={recipient[:30]}")

    @staticmethod
    def get_recent(ip_address: str, alert_type: str = '') -> list:
        """Get recent notifications for an IP."""
        key = f"pi:notif_log:{ip_address}:{alert_type}"
        return cache.get(key, [])

    @staticmethod
    def get_send_count(ip_address: str, alert_type: str,
                       hours: int = 24) -> int:
        """Count how many alerts were sent for this IP/type in the last N hours."""
        logs = NotificationLog.get_recent(ip_address, alert_type)
        if not logs:
            return 0
        cutoff = timezone.now().isoformat()[:13]  # Hour-level truncation
        return len([
            l for l in logs
            if l.get('status') == 'sent' and l.get('time', '')[:13] >= cutoff
        ])

    @staticmethod
    def was_recently_sent(ip_address: str, alert_type: str,
                           minutes: int = 60) -> bool:
        """True if an alert was sent in the last N minutes (for throttling)."""
        from datetime import timedelta
        cutoff = (timezone.now() - timedelta(minutes=minutes)).isoformat()
        logs   = NotificationLog.get_recent(ip_address, alert_type)
        return any(
            l.get('status') == 'sent' and l.get('time', '') >= cutoff
            for l in logs
        )

    @staticmethod
    def clear(ip_address: str, alert_type: str = ''):
        """Clear notification logs for an IP."""
        cache.delete(f"pi:notif_log:{ip_address}:{alert_type}")
