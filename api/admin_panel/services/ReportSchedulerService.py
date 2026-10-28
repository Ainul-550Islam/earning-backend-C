# api/admin_panel/services/ReportSchedulerService.py
"""Service for managing report schedules."""
import logging
logger = logging.getLogger(__name__)


class ReportSchedulerService:
    @staticmethod
    def run_due():
        from ..tasks.report_generation_tasks import run_due_schedules
        return run_due_schedules()

    @staticmethod
    def toggle(schedule_id: int, enabled: bool) -> bool:
        try:
            from ..models.reports import ReportSchedule
            ReportSchedule.objects.filter(pk=schedule_id).update(is_active=enabled)
            return True
        except Exception as e:
            logger.error(f"ReportSchedulerService.toggle error: {e}")
            return False

    @staticmethod
    def get_next_run(cron_expr: str):
        """Estimate next run time from cron expression."""
        try:
            from croniter import croniter
            from datetime import datetime
            cron = croniter(cron_expr, datetime.now())
            return cron.get_next(datetime)
        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"cron next run error: {e}")
            return None