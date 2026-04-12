"""
api/users/auth/login_attempt_tracker.py
Login attempt history DB-তে save করো (analytics + security)
views.py থেকে extract করা হয়েছে
"""
import logging
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..enums import LoginMethodEnum

logger = logging.getLogger(__name__)
User   = get_user_model()


class LoginAttemptTracker:
    """
    প্রতিটি login attempt (success বা fail) DB-তে record করো।
    - Security audit-এর জন্য
    - Suspicious pattern detect করার জন্য
    - api.fraud_detection signal দেওয়ার জন্য
    """

    def record_attempt(
        self,
        identifier: str,        # username বা email
        ip_address: str,
        user_agent: str = '',
        method: str     = LoginMethodEnum.PASSWORD,
        success: bool   = False,
        user            = None,
        failure_reason: str = '',
    ) -> None:
        """
        Login attempt save করো।
        Success হলে user object দাও।
        """
        try:
            from ..models import LoginHistory
            LoginHistory.objects.create(
                user           = user,
                identifier     = identifier,
                ip_address     = ip_address,
                user_agent     = user_agent[:500] if user_agent else '',
                method         = method,
                success        = success,
                failure_reason = failure_reason,
                attempted_at   = timezone.now(),
            )
        except Exception as e:
            logger.warning(f'LoginHistory save failed: {e}')

        # Fraud detection-কে signal দাও (failed attempt)
        if not success:
            self._notify_fraud_detection(
                identifier  = identifier,
                ip_address  = ip_address,
                user_agent  = user_agent,
                reason      = failure_reason,
            )

    def get_recent_failures(self, identifier: str, hours: int = 24) -> int:
        """Last N hours-এ কতটি failed attempt হয়েছে"""
        try:
            from ..models import LoginHistory
            from datetime import timedelta
            since = timezone.now() - timedelta(hours=hours)
            return LoginHistory.objects.filter(
                identifier = identifier,
                success    = False,
                attempted_at__gte = since,
            ).count()
        except Exception:
            return 0

    def get_user_login_history(self, user, limit: int = 20) -> list:
        """User-এর login history দাও"""
        try:
            from ..models import LoginHistory
            return list(
                LoginHistory.objects
                .filter(user=user, success=True)
                .order_by('-attempted_at')
                .values('ip_address', 'user_agent', 'method', 'attempted_at')[:limit]
            )
        except Exception:
            return []

    def get_suspicious_ips(self, threshold: int = 10, hours: int = 1) -> list:
        """Short time-এ অনেক failed attempt করা IPs"""
        try:
            from ..models import LoginHistory
            from datetime import timedelta
            from django.db.models import Count
            since = timezone.now() - timedelta(hours=hours)
            return list(
                LoginHistory.objects
                .filter(success=False, attempted_at__gte=since)
                .values('ip_address')
                .annotate(count=Count('id'))
                .filter(count__gte=threshold)
                .values_list('ip_address', flat=True)
            )
        except Exception:
            return []

    def _notify_fraud_detection(
        self,
        identifier: str,
        ip_address: str,
        user_agent: str,
        reason: str,
    ) -> None:
        """
        api.fraud_detection-কে signal দাও।
        Fraud detection নিজেই সিদ্ধান্ত নেবে।
        """
        try:
            from django.dispatch import Signal
            # api.fraud_detection.signals এটা শুনবে
            # login_failed_signal.send(sender=self.__class__, ...)
            logger.debug(f'Fraud detection notified: {ip_address} failed login')
        except Exception as e:
            logger.warning(f'Fraud detection signal failed: {e}')


# Singleton
login_attempt_tracker = LoginAttemptTracker()
