# api/offer_inventory/reporting_audit/error_tracker.py
"""Error Tracker — Application error capture, grouping, and resolution."""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class ErrorTracker:
    """Capture, log, and analyze application errors."""

    @staticmethod
    def log(level: str, message: str, traceback: str = '',
             request=None, user=None) -> object:
        """Log an application error."""
        from api.offer_inventory.models import ErrorLog
        ip = ''
        if request:
            xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
            ip  = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
        return ErrorLog.objects.create(
            level       =level,
            message     =message[:1000],
            traceback   =traceback[:5000],
            request_path=request.path if request else '',
            user        =user or (request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None),
            ip_address  =ip or None,
        )

    @staticmethod
    def capture_exception(exc: Exception, context: dict = None, request=None):
        """Capture and log a Python exception with traceback."""
        import traceback as _tb
        from api.offer_inventory.notifications.slack_webhook import SlackNotifier
        tb = _tb.format_exc()
        ErrorTracker.log('critical', str(exc)[:1000], tb, request=request)
        # Alert for critical errors
        if any(k in str(exc).lower() for k in ['database', 'timeout', 'connection']):
            try:
                SlackNotifier().alert_system_error(
                    f'Critical: {type(exc).__name__}: {str(exc)[:200]}'
                )
            except Exception:
                pass
        logger.critical(f'Exception captured: {type(exc).__name__}: {exc}')

    @staticmethod
    def get_error_summary(hours: int = 24) -> dict:
        """Error count by level for dashboard."""
        from api.offer_inventory.models import ErrorLog
        from django.db.models import Count
        since = timezone.now() - timedelta(hours=hours)
        return dict(
            ErrorLog.objects.filter(created_at__gte=since)
            .values_list('level')
            .annotate(count=Count('id'))
        )

    @staticmethod
    def get_top_errors(limit: int = 10) -> list:
        """Most frequent unresolved errors (last 7 days)."""
        from api.offer_inventory.models import ErrorLog
        from django.db.models import Count
        since = timezone.now() - timedelta(days=7)
        return list(
            ErrorLog.objects.filter(created_at__gte=since, is_resolved=False)
            .values('message')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )

    @staticmethod
    def resolve(error_id: str, resolved_by=None) -> bool:
        """Mark an error as resolved."""
        from api.offer_inventory.models import ErrorLog
        updated = ErrorLog.objects.filter(id=error_id).update(
            is_resolved=True, resolved_at=timezone.now()
        )
        return updated > 0

    @staticmethod
    def bulk_resolve(level: str = 'error') -> int:
        """Mark all errors of a level as resolved."""
        from api.offer_inventory.models import ErrorLog
        updated = ErrorLog.objects.filter(
            level=level, is_resolved=False
        ).update(is_resolved=True, resolved_at=timezone.now())
        return updated
