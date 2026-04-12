# api/offer_inventory/system_devops/log_rotator.py
"""
Log Rotator — Periodic cleanup of old log records from the database.
Prevents DB bloat while retaining important audit data.
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_RETENTION = {
    'fraud_clicks'    : 90,    # days
    'postback_logs'   : 60,
    'rate_limit'      : 7,
    'honeypot'        : 30,
    'network_ping'    : 14,
    'errors_resolved' : 90,
    'audit_logs'      : 365,   # 1 year — for compliance
    'pixel_logs'      : 30,
    'impressions'     : 60,
}


class LogRotator:
    """Database log cleanup with configurable retention periods."""

    @classmethod
    def rotate_all(cls, dry_run: bool = False,
                    custom_retention: dict = None) -> dict:
        """
        Run all log rotation tasks.
        dry_run=True: count only, don't delete.
        """
        retention = DEFAULT_RETENTION.copy()
        if custom_retention:
            retention.update(custom_retention)

        results = {}

        tasks = [
            ('fraud_clicks',    cls._rotate_fraud_clicks,    retention['fraud_clicks']),
            ('postback_logs',   cls._rotate_postback_logs,   retention['postback_logs']),
            ('rate_limit',      cls._rotate_rate_limit_logs, retention['rate_limit']),
            ('honeypot',        cls._rotate_honeypot_logs,   retention['honeypot']),
            ('network_ping',    cls._rotate_network_pings,   retention['network_ping']),
            ('errors_resolved', cls._rotate_resolved_errors, retention['errors_resolved']),
            ('pixel_logs',      cls._rotate_pixel_logs,      retention['pixel_logs']),
        ]

        total = 0
        for name, fn, days in tasks:
            try:
                count = fn(days, dry_run)
                results[name] = count
                total += count if isinstance(count, int) else 0
            except Exception as e:
                results[name] = f'error: {e}'

        logger.info(f'Log rotation: {total} records {"would be" if dry_run else ""} deleted')
        return {'results': results, 'total': total, 'dry_run': dry_run}

    @staticmethod
    def _rotate_fraud_clicks(days: int, dry_run: bool) -> int:
        from api.offer_inventory.models import Click
        cutoff = timezone.now() - timedelta(days=days)
        qs     = Click.objects.filter(is_fraud=True, created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _rotate_postback_logs(days: int, dry_run: bool) -> int:
        from api.offer_inventory.models import PostbackLog
        cutoff = timezone.now() - timedelta(days=days)
        qs     = PostbackLog.objects.filter(is_success=True, created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _rotate_rate_limit_logs(days: int, dry_run: bool) -> int:
        from api.offer_inventory.models import RateLimitLog
        cutoff = timezone.now() - timedelta(days=days)
        qs     = RateLimitLog.objects.filter(created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _rotate_honeypot_logs(days: int, dry_run: bool) -> int:
        from api.offer_inventory.models import HoneypotLog
        cutoff = timezone.now() - timedelta(days=days)
        qs     = HoneypotLog.objects.filter(created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _rotate_network_pings(days: int, dry_run: bool) -> int:
        from api.offer_inventory.models import NetworkPinger
        cutoff = timezone.now() - timedelta(days=days)
        qs     = NetworkPinger.objects.filter(created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _rotate_resolved_errors(days: int, dry_run: bool) -> int:
        from api.offer_inventory.models import ErrorLog
        cutoff = timezone.now() - timedelta(days=days)
        qs     = ErrorLog.objects.filter(is_resolved=True, created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _rotate_pixel_logs(days: int, dry_run: bool) -> int:
        from api.offer_inventory.models import PixelLog
        cutoff = timezone.now() - timedelta(days=days)
        qs     = PixelLog.objects.filter(is_fired=True, created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def get_log_sizes() -> dict:
        """Current row counts for all log tables."""
        from api.offer_inventory.models import (
            Click, Conversion, PostbackLog, AuditLog,
            ErrorLog, RateLimitLog, HoneypotLog, NetworkPinger,
        )
        return {
            'clicks'       : Click.objects.count(),
            'conversions'  : Conversion.objects.count(),
            'postback_logs': PostbackLog.objects.count(),
            'audit_logs'   : AuditLog.objects.count(),
            'error_logs'   : ErrorLog.objects.count(),
            'rate_limits'  : RateLimitLog.objects.count(),
            'honeypot'     : HoneypotLog.objects.count(),
            'network_pings': NetworkPinger.objects.count(),
        }
