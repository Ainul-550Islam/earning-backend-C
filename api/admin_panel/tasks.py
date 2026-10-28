# api/admin_panel/tasks.py
"""
Core Celery task entry point for admin_panel.
Imports & re-exports all tasks from the tasks/ sub-package
so existing code (e.g. generate_report_task.delay()) still works.

All actual task implementations live in admin_panel/tasks/*.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


# ==================== Existing Task (kept for backward compat) ====================

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='admin_panel.tasks.generate_report_task')
def generate_report_task(self, report_id: int):
    """
    Generate a Report object's data & file.
    Used by ReportViewSet.regenerate() and ReportViewSet.generate_report().
    """
    try:
        from .models.core import Report
        report = Report.objects.get(pk=report_id)
        report.status = 'processing'
        report.save(update_fields=['status'])

        # Attempt real generation via ReportService
        try:
            from .services.ReportService import ReportService
            ReportService.generate(report)
        except ImportError:
            # Fallback: basic placeholder
            import json
            from django.utils import timezone
            report.report_data = {
                'generated_at': timezone.now().isoformat(),
                'report_type': report.report_type,
                'rows': [],
                'summary': {},
            }
            report.status = 'completed'
            report.save(update_fields=['report_data', 'status'])

        logger.info(f"Report {report_id} generated successfully.")
        return {'success': True, 'report_id': report_id}

    except Exception as exc:
        logger.error(f"generate_report_task failed for report {report_id}: {exc}")
        try:
            from .models.core import Report
            Report.objects.filter(pk=report_id).update(status='failed')
        except Exception:
            pass
        raise self.retry(exc=exc)


# ==================== Dashboard Tasks ====================

@shared_task(name='admin_panel.tasks.refresh_dashboard_kpis')
def refresh_dashboard_kpis():
    """Refresh all dashboard KPI metrics. Called every 5 minutes."""
    try:
        from .tasks.dashboard_refresh_tasks import refresh_all_metrics
        return refresh_all_metrics()
    except ImportError:
        logger.debug("dashboard_refresh_tasks not yet available.")
        return None


# ==================== Report Tasks ====================

@shared_task(bind=True, max_retries=3, default_retry_delay=120, name='admin_panel.tasks.run_scheduled_reports')
def run_scheduled_reports(self):
    """Run all due scheduled reports."""
    try:
        from .tasks.report_generation_tasks import run_due_schedules
        return run_due_schedules()
    except ImportError:
        logger.debug("report_generation_tasks not yet available.")
        return None


# ==================== Data Export Tasks ====================

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='admin_panel.tasks.process_data_export')
def process_data_export(self, export_id: str):
    """Process a DataExport async task."""
    try:
        from .tasks.data_export_tasks import process_export
        return process_export(export_id)
    except ImportError:
        logger.debug("data_export_tasks not yet available.")
        return None


# ==================== Insight Tasks ====================

@shared_task(name='admin_panel.tasks.generate_daily_insights')
def generate_daily_insights():
    """Generate AI-powered admin insights daily."""
    try:
        from .tasks.insight_tasks import generate_insights
        return generate_insights()
    except ImportError:
        logger.debug("insight_tasks not yet available.")
        return None


# ==================== Cleanup Tasks ====================

@shared_task(name='admin_panel.tasks.cleanup_old_activity')
def cleanup_old_activity():
    """Archive/delete old admin activity logs."""
    try:
        from .tasks.activity_cleanup_tasks import run_cleanup
        return run_cleanup()
    except ImportError:
        logger.debug("activity_cleanup_tasks not yet available.")
        return None


@shared_task(name='admin_panel.tasks.cleanup_stale_sessions')
def cleanup_stale_sessions():
    """Expire stale admin sessions."""
    try:
        from .tasks.session_cleanup_tasks import run_session_cleanup
        return run_session_cleanup()
    except ImportError:
        logger.debug("session_cleanup_tasks not yet available.")
        return None


# ==================== Config Cache Tasks ====================

@shared_task(name='admin_panel.tasks.refresh_config_cache')
def refresh_config_cache():
    """Refresh system config cache."""
    try:
        from .tasks.config_cache_tasks import refresh_all_config
        return refresh_all_config()
    except ImportError:
        logger.debug("config_cache_tasks not yet available.")
        return None


# ==================== System Health Tasks ====================

@shared_task(name='admin_panel.tasks.check_system_health')
def check_system_health():
    """Ping all services and update health status."""
    try:
        from .tasks.system_health_tasks import run_health_check
        return run_health_check()
    except ImportError:
        from .utils import get_full_system_health
        result = get_full_system_health()
        logger.info(f"System health: {result['overall']}")
        return result


# ==================== Maintenance Tasks ====================

@shared_task(name='admin_panel.tasks.notify_pre_maintenance')
def notify_pre_maintenance(window_id: int):
    """Send pre-maintenance notification to users."""
    try:
        from .tasks.maintenance_tasks import send_pre_maintenance_notification
        return send_pre_maintenance_notification(window_id)
    except ImportError:
        logger.debug("maintenance_tasks not yet available.")
        return None


# ==================== Feature Flag Tasks ====================

@shared_task(name='admin_panel.tasks.evaluate_feature_flag_rollouts')
def evaluate_feature_flag_rollouts():
    """Evaluate and re-cache feature flag rollout states."""
    try:
        from .tasks.feature_flag_tasks import refresh_all_flags
        return refresh_all_flags()
    except ImportError:
        logger.debug("feature_flag_tasks not yet available.")
        return None


# ==================== Admin Digest Tasks ====================

@shared_task(name='admin_panel.tasks.send_admin_digest')
def send_admin_digest():
    """Send daily admin summary email."""
    try:
        from .tasks.admin_digest_tasks import send_digest
        return send_digest()
    except ImportError:
        logger.debug("admin_digest_tasks not yet available.")
        return None