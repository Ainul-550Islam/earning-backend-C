"""
Backup Scheduler — Manages automated backup schedule execution
"""
import logging
from datetime import datetime, timedelta
from typing import List
from croniter import croniter

from ..enums import BackupType, BackupFrequency
from ..config import settings

logger = logging.getLogger(__name__)


class BackupScheduler:
    """
    Evaluates backup policies and determines which backups are due.
    Integrates with Celery Beat for scheduled task dispatch.
    """

    FREQUENCY_INTERVALS = {
        BackupFrequency.HOURLY: timedelta(hours=1),
        BackupFrequency.DAILY: timedelta(days=1),
        BackupFrequency.WEEKLY: timedelta(weeks=1),
        BackupFrequency.MONTHLY: timedelta(days=30),
    }

    def __init__(self, db_session=None):
        self.db = db_session

    def is_backup_due(self, policy) -> bool:
        """Check if a backup is due based on policy frequency or cron expression."""
        if policy.cron_expression:
            return self._check_cron(policy.cron_expression)
        interval = self.FREQUENCY_INTERVALS.get(policy.frequency)
        if not interval:
            return False
        if not policy.jobs:
            return True  # No backup ever run
        last_job = max(policy.jobs, key=lambda j: j.created_at)
        return datetime.utcnow() - last_job.created_at >= interval

    def _check_cron(self, expression: str) -> bool:
        try:
            cron = croniter(expression, datetime.utcnow() - timedelta(minutes=1))
            next_time = cron.get_next(datetime)
            return next_time <= datetime.utcnow() + timedelta(seconds=30)
        except Exception as e:
            logger.error(f"Invalid cron expression '{expression}': {e}")
            return False

    def get_due_policies(self, policies: list) -> list:
        """Filter policies that are due for backup."""
        due = []
        for policy in policies:
            if policy.is_active and self.is_backup_due(policy):
                due.append(policy)
                logger.info(f"Backup due: policy={policy.id} ({policy.name})")
        return due

    def schedule_all(self, policies: list) -> int:
        """Schedule all due backup jobs. Returns count dispatched."""
        from ..AUTOMATION_ENGINES.auto_backup import AutoBackup
        due_policies = self.get_due_policies(policies)
        count = 0
        for policy in due_policies:
            try:
                AutoBackup.dispatch(policy_id=policy.id)
                count += 1
            except Exception as e:
                logger.error(f"Failed to dispatch backup for policy {policy.id}: {e}")
        logger.info(f"Scheduled {count} backup jobs")
        return count

    def get_next_run(self, policy) -> datetime:
        """Calculate next scheduled run for a policy."""
        if policy.cron_expression:
            cron = croniter(policy.cron_expression, datetime.utcnow())
            return cron.get_next(datetime)
        interval = self.FREQUENCY_INTERVALS.get(policy.frequency, timedelta(days=1))
        return datetime.utcnow() + interval
