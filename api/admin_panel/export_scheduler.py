# api/admin_panel/export_scheduler.py
"""Scheduled automated report delivery."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)

class ExportScheduler:
    SCHEDULES = {
        'daily':   'Send every day at 8 AM',
        'weekly':  'Send every Monday at 7 AM',
        'monthly': 'Send on 1st of each month',
    }

    @classmethod
    def create_schedule(cls, report_id: Any, frequency: str,
                        recipients: List[str], format: str = 'csv', actor=None) -> Dict:
        try:
            from api.admin_panel.models.reports import ReportSchedule
            schedule = ReportSchedule.objects.create(
                report_id=report_id, frequency=frequency,
                recipients=recipients, format=format, is_active=True,
            )
            return {'success': True, 'schedule_id': schedule.pk, 'frequency': frequency}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def list_schedules(cls) -> List[Dict]:
        try:
            from api.admin_panel.models.reports import ReportSchedule
            return list(ReportSchedule.objects.filter(is_active=True).values(
                'id', 'report__name', 'frequency', 'recipients', 'format', 'last_run'))
        except Exception: return []

    @classmethod
    def run_scheduled_exports(cls) -> int:
        """Run all due scheduled exports. Called by Celery Beat."""
        count = 0
        try:
            from api.admin_panel.models.reports import ReportSchedule
            for schedule in ReportSchedule.objects.filter(is_active=True):
                try:
                    cls._run_schedule(schedule)
                    count += 1
                except Exception as e:
                    logger.error(f"[ExportScheduler] Schedule {schedule.pk}: {e}")
        except Exception: pass
        return count

    @classmethod
    def _run_schedule(cls, schedule) -> None:
        from celery import current_app
        current_app.send_task('api.admin_panel.tasks.report_generation_tasks.run_report_and_email',
                               args=[schedule.report_id, schedule.recipients, schedule.format])

export_scheduler = ExportScheduler()