# Reconstructed from services/FIX_ALL_PART1_Services1-4.py (was never split into
# individual files, leaving alerts.services unimportable — see audit).
# Fixed on extraction: AlertNotification -> Notification (real model name),
# api.alerts.utils.* -> real existing module paths.

from django.utils import timezone
from django.db.models import Count
import logging

logger = logging.getLogger(__name__)


class SystemHealthService:
    """
    Consolidates system health check logic.
    Eliminates duplicates from: celery_tasks.py + api_views.py + context_processors.py
    """

    @staticmethod
    def check_system_health():
        """
        Run every SystemHealthCheck that is currently due.

        Previously duplicated in:
        - alerts/celery_tasks.py
        - alerts/tasks/core.py

        NOTE (corrected after cross-checking the real callers): this used to
        ping the DB connection directly and count failed alerts/pending
        notifications -- that never matched what either real caller does.
        Both actually loop SystemHealthCheck.get_checks_needed() and call
        check.update_status(...) per check. Rewritten to match.

        Returns:
            dict: {'checked': int, 'failed': int}
        """
        from api.alerts.models import SystemHealthCheck

        checks_needed = SystemHealthCheck.get_checks_needed()

        checked_count = 0
        failed_count = 0

        for check in checks_needed:
            try:
                success = check.update_status(
                    response_time=50,  # Simulated response time
                    success=True,
                    message="Check completed successfully"
                )
                checked_count += 1
                if not success:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error checking {check.check_name}: {e}")
                failed_count += 1

        logger.info(f"Checked {checked_count} health checks, failed: {failed_count}")
        return {'checked': checked_count, 'failed': failed_count}

    @staticmethod
    def system_health():
        """
        Get current system health status.
        
        Previously duplicated in:
        - alerts/api_views.py
        - alerts/context_processors.py
        
        Returns:
            dict: Current health information
        """
        from api.alerts.models import SystemHealthCheck
        latest_check = SystemHealthCheck.objects.order_by('-last_checked').first()

        if latest_check is None:
            return {'status': 'unknown', 'timestamp': None, 'details': {}}

        import json as _json
        try:
            details = _json.loads(latest_check.status_message) if latest_check.status_message else {}
        except (ValueError, TypeError):
            details = {}

        return {
            'status': latest_check.status,
            'timestamp': latest_check.last_checked,
            'details': details
        }

    @staticmethod
    def get_health_trends(days=7):
        """Get health trends over time"""
        from datetime import timedelta
        from api.alerts.models import SystemHealthCheck
        
        start_date = timezone.now() - timedelta(days=days)
        
        trends = SystemHealthCheck.objects.filter(
            created_at__gte=start_date
        ).values('created_at__date', 'status').annotate(
            count=Count('id')
        )
        
        return list(trends)

    @staticmethod
    def get_uptime_percentage(days=7):
        """Calculate uptime percentage"""
        from datetime import timedelta
        from api.alerts.models import SystemHealthCheck
        
        start_date = timezone.now() - timedelta(days=days)
        
        total_checks = SystemHealthCheck.objects.filter(
            created_at__gte=start_date
        ).count()
        
        healthy_checks = SystemHealthCheck.objects.filter(
            created_at__gte=start_date,
            status='healthy'
        ).count()
        
        if total_checks == 0:
            return 100.0
        
        uptime = (healthy_checks / total_checks) * 100
        return round(uptime, 2)

    @staticmethod
    def needs_checking():
        """Check if system needs a health check"""
        from datetime import timedelta
        from api.alerts.models import SystemHealthCheck

        latest_check = SystemHealthCheck.objects.order_by('-last_checked').first()

        if latest_check is None or latest_check.last_checked is None:
            return True

        # Check every 5 minutes
        time_since_check = timezone.now() - latest_check.last_checked
        return time_since_check >= timedelta(minutes=5)


from api.alerts.models import Notification

__all__ = ['SystemHealthService']
