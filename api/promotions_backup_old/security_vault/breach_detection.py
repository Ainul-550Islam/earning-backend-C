# api/promotions/security_vault/breach_detection.py
breach_detection.py
# Data Breach & Anomaly Detection
# Unusual data access pattern, mass export, credential stuffing ধরে
# =============================================================================

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('security_vault.breach_detection')

# Cache key prefixes
CACHE_KEY_DATA_ACCESS     = 'breach:data_access:{}:{}'   # user_id:resource
CACHE_KEY_EXPORT_COUNT    = 'breach:export:{}:{}'         # user_id:date
CACHE_KEY_CRED_STUFF      = 'breach:credstuff:{}'         # ip
CACHE_KEY_ANOMALY_SCORE   = 'breach:anomaly:{}'           # user_id
CACHE_KEY_ALERT_SENT      = 'breach:alert_sent:{}:{}'     # user_id:alert_type

# Thresholds
EXPORT_DAILY_THRESHOLD    = getattr(settings, 'BREACH_EXPORT_THRESHOLD', 1000)      # records/day
DATA_ACCESS_BURST         = getattr(settings, 'BREACH_DATA_ACCESS_BURST', 500)      # requests/hour
CRED_STUFF_THRESHOLD      = getattr(settings, 'BREACH_CRED_STUFF_THRESHOLD', 50)    # different users/ip/hour


@dataclass
class BreachAlert:
    """Data breach alert।"""
    alert_type:   str
    severity:     str                       # low, medium, high, critical
    user_id:      Optional[int]  = None
    ip_address:   Optional[str]  = None
    details:      dict           = field(default_factory=dict)
    detected_at:  str            = field(default_factory=lambda: timezone.now().isoformat())
    action_taken: str            = 'logged'


class BreachDetector:
    """
    Data breach ও security anomaly detect করে।

    Detects:
    1. Mass data export (একসাথে অনেক record download)
    2. Credential stuffing attack (অনেক user নিয়ে login try)
    3. Unusual data access pattern (rate anomaly)
    4. Sensitive field mass access
    5. Off-hours admin activity
    """

    def check_mass_export(
        self,
        user_id: int,
        records_count: int,
        resource_type: str = 'generic',
    ) -> Optional[BreachAlert]:
        """
        Mass data export detect করে।
        কেউ একদিনে অনেক record export করলে alert।
        """
        today        = timezone.now().date().isoformat()
        cache_key    = CACHE_KEY_EXPORT_COUNT.format(user_id, today)
        daily_total  = cache.get(cache_key, 0) + records_count
        cache.set(cache_key, daily_total, timeout=86400)

        if daily_total > EXPORT_DAILY_THRESHOLD:
            alert = BreachAlert(
                alert_type = 'mass_data_export',
                severity   = 'high' if daily_total > EXPORT_DAILY_THRESHOLD * 3 else 'medium',
                user_id    = user_id,
                details    = {
                    'records_today': daily_total,
                    'threshold':     EXPORT_DAILY_THRESHOLD,
                    'resource':      resource_type,
                    'excess':        daily_total - EXPORT_DAILY_THRESHOLD,
                },
            )
            self._handle_alert(alert)
            return alert
        return None

    def check_credential_stuffing(self, ip: str, attempted_username: str) -> Optional[BreachAlert]:
        """
        Credential stuffing detect করে।
        একটি IP থেকে অনেক different username দিয়ে login try।
        """
        cache_key  = CACHE_KEY_CRED_STUFF.format(ip)
        user_set   = cache.get(cache_key, set())
        user_set.add(attempted_username.lower())
        cache.set(cache_key, user_set, timeout=3600)

        if len(user_set) >= CRED_STUFF_THRESHOLD:
            alert = BreachAlert(
                alert_type = 'credential_stuffing',
                severity   = 'critical',
                ip_address = ip,
                details    = {
                    'unique_usernames_tried': len(user_set),
                    'threshold':              CRED_STUFF_THRESHOLD,
                    'timeframe':              '1 hour',
                },
            )
            self._handle_alert(alert)
            return alert
        return None

    def check_unusual_data_access(
        self,
        user_id: int,
        resource: str,
        window_seconds: int = 3600,
    ) -> Optional[BreachAlert]:
        """
        Unusual data access burst detect করে।
        """
        cache_key = CACHE_KEY_DATA_ACCESS.format(user_id, resource)
        count     = cache.get(cache_key, 0) + 1
        cache.set(cache_key, count, timeout=window_seconds)

        if count > DATA_ACCESS_BURST:
            alert = BreachAlert(
                alert_type = 'unusual_data_access',
                severity   = 'high',
                user_id    = user_id,
                details    = {
                    'resource':      resource,
                    'access_count':  count,
                    'window':        f'{window_seconds}s',
                    'threshold':     DATA_ACCESS_BURST,
                },
            )
            self._handle_alert(alert)
            return alert
        return None

    def check_off_hours_admin_activity(
        self,
        user_id: int,
        action: str,
        allowed_hours: tuple = (8, 22),
    ) -> Optional[BreachAlert]:
        """
        Off-hours admin activity detect করে।
        allowed_hours: (start_hour, end_hour) — 24h format
        """
        now  = timezone.now()
        hour = now.hour

        if not (allowed_hours[0] <= hour <= allowed_hours[1]):
            alert = BreachAlert(
                alert_type = 'off_hours_admin_activity',
                severity   = 'medium',
                user_id    = user_id,
                details    = {
                    'action':         action,
                    'hour':           hour,
                    'allowed_range':  f'{allowed_hours[0]}:00 - {allowed_hours[1]}:00 UTC',
                    'timestamp':      now.isoformat(),
                },
            )
            self._handle_alert(alert)
            return alert
        return None

    def check_sensitive_field_access(
        self,
        user_id: int,
        model_name: str,
        field_name: str,
        count: int = 1,
    ) -> Optional[BreachAlert]:
        """
        Sensitive field (bank_account, national_id) mass access detect করে।
        """
        threshold  = 50  # per hour
        cache_key  = f'breach:sensitive:{user_id}:{model_name}:{field_name}'
        total      = cache.get(cache_key, 0) + count
        cache.set(cache_key, total, timeout=3600)

        if total > threshold:
            alert = BreachAlert(
                alert_type = 'sensitive_field_mass_access',
                severity   = 'high',
                user_id    = user_id,
                details    = {
                    'model':      model_name,
                    'field':      field_name,
                    'access_count': total,
                    'threshold':  threshold,
                },
            )
            self._handle_alert(alert)
            return alert
        return None

    def scan_leaked_credentials(self, email: str, password_hash: str = None) -> dict:
        """
        HaveIBeenPwned API দিয়ে leaked credentials check করে।
        k-anonymity model ব্যবহার করে — full hash পাঠায় না।
        """
        result = {'leaked': False, 'breach_count': 0}
        try:
            import requests
            # k-anonymity: শুধু hash এর প্রথম 5 char পাঠাই
            if password_hash:
                prefix   = password_hash[:5].upper()
                suffix   = password_hash[5:].upper()
                response = requests.get(
                    f'https://api.pwnedpasswords.com/range/{prefix}',
                    headers={'Add-Padding': 'true'},
                    timeout=3,
                )
                if response.status_code == 200:
                    for line in response.text.splitlines():
                        if ':' in line:
                            hash_suffix, count = line.split(':', 1)
                            if hash_suffix.upper() == suffix:
                                result['leaked']       = True
                                result['breach_count'] = int(count)
                                logger.warning(f'Password found in breach database: {count} times')
                                break
        except Exception as e:
            logger.error(f'HIBP check failed: {e}')
        return result

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _handle_alert(self, alert: BreachAlert) -> None:
        """Alert এ action নেয়।"""
        # Duplicate alert prevention (1 hour cooldown)
        cooldown_key = CACHE_KEY_ALERT_SENT.format(alert.user_id or 'anon', alert.alert_type)
        if cache.get(cooldown_key):
            return
        cache.set(cooldown_key, True, timeout=3600)

        # Log করো
        log_fn = logger.critical if alert.severity == 'critical' else logger.warning
        log_fn(
            f'BREACH ALERT [{alert.severity.upper()}]: type={alert.alert_type}, '
            f'user={alert.user_id}, ip={alert.ip_address}, details={alert.details}'
        )

        # Async notification পাঠাও (Celery task)
        self._send_breach_notification(alert)

        # Critical breach হলে automatic action নাও
        if alert.severity == 'critical' and alert.user_id:
            self._auto_suspend_user(alert.user_id, reason=alert.alert_type)

    @staticmethod
    def _send_breach_notification(alert: BreachAlert) -> None:
        """Security team কে notification পাঠায়।"""
        try:
            # Slack/PagerDuty/Email notification — implement অনুযায়ী
            # from notifications.tasks import send_security_alert
            # send_security_alert.delay(alert.__dict__)
            logger.info(f'Breach notification queued: {alert.alert_type}')
        except Exception as e:
            logger.exception(f'Failed to send breach notification: {e}')

    @staticmethod
    def _auto_suspend_user(user_id: int, reason: str) -> None:
        """Critical breach এ user suspend করে।"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(pk=user_id).update(is_active=False)
            logger.critical(f'User #{user_id} auto-suspended due to: {reason}')
        except Exception as e:
            logger.exception(f'Auto-suspend failed for user #{user_id}: {e}')


# ── Singleton ──────────────────────────────────────────────────────────────────
breach_detector = BreachDetector()
