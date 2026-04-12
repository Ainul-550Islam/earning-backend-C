# api/offer_inventory/maintenance_logs/crash_report_handler.py
"""Crash Report Handler — Capture and alert on critical system errors."""
import logging
import traceback as _tb
from django.utils import timezone

logger = logging.getLogger(__name__)


class CrashReportHandler:
    """Handle application crashes and critical errors."""

    CRITICAL_ERROR_KEYWORDS = [
        'database', 'connection', 'timeout', 'memory',
        'integrity', 'deadlock', 'permission denied',
    ]

    @classmethod
    def capture(cls, exc: Exception, context: dict = None,
                 request=None, notify: bool = True) -> dict:
        """Capture an exception and log/alert as needed."""
        tb        = _tb.format_exc()
        exc_type  = type(exc).__name__
        exc_msg   = str(exc)[:1000]
        is_crit   = any(k in exc_msg.lower() for k in cls.CRITICAL_ERROR_KEYWORDS)

        from api.offer_inventory.reporting_audit.error_tracker import ErrorTracker
        ErrorTracker.log(
            level    ='critical' if is_crit else 'error',
            message  =exc_msg,
            traceback=tb,
            request  =request,
        )

        if notify and is_crit:
            cls._send_alerts(exc_type, exc_msg, tb)

        logger.critical(f'Crash captured [{exc_type}]: {exc_msg}', exc_info=True)
        return {
            'exception'  : exc_type,
            'message'    : exc_msg,
            'is_critical': is_crit,
            'notified'   : notify and is_crit,
            'captured_at': timezone.now().isoformat(),
        }

    @staticmethod
    def _send_alerts(exc_type: str, exc_msg: str, tb: str):
        """Send crash alerts via Slack and email."""
        try:
            from api.offer_inventory.notifications.slack_webhook import SlackNotifier
            SlackNotifier().alert_system_error(f'{exc_type}: {exc_msg[:200]}')
        except Exception as e:
            logger.error(f'Crash alert (Slack) error: {e}')
        try:
            from api.offer_inventory.notifications.email_alert_system import EmailAlertSystem
            EmailAlertSystem.send_system_error_alert(
                f'{exc_type}: {exc_msg[:300]}',
                context=tb[:500]
            )
        except Exception as e:
            logger.error(f'Crash alert (email) error: {e}')

    @staticmethod
    def get_crash_summary(hours: int = 24) -> dict:
        """Recent crash summary for ops review."""
        from api.offer_inventory.reporting_audit.error_tracker import ErrorTracker
        return {
            'error_summary': ErrorTracker.get_error_summary(hours=hours),
            'top_errors'   : ErrorTracker.get_top_errors(limit=5),
            'period_hours' : hours,
            'generated_at' : timezone.now().isoformat(),
        }

    @staticmethod
    def resolve_crash(error_id: str, note: str = '') -> bool:
        """Mark a crash as resolved."""
        from api.offer_inventory.reporting_audit.error_tracker import ErrorTracker
        return ErrorTracker.resolve(error_id)

    @staticmethod
    def django_exception_handler(exc, context):
        """Custom Django REST Framework exception handler."""
        from rest_framework.views import exception_handler
        from rest_framework import status
        from rest_framework.response import Response

        response = exception_handler(exc, context)
        if response is None:
            # Unhandled exception
            CrashReportHandler.capture(
                exc,
                request=context.get('request'),
                notify=True,
            )
            response = Response(
                {'success': False, 'message': 'একটি অভ্যন্তরীণ ত্রুটি ঘটেছে।', 'code': 'server_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return response
