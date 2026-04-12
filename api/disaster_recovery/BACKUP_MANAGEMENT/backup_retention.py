"""
Backup Retention — Enforces retention policies (GFS: Grandfather-Father-Son)
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)


class BackupRetentionManager:
    """
    Implements GFS (Grandfather-Father-Son) retention strategy:
    - Son    : Daily backups — keep last N days
    - Father : Weekly backups — keep last N weeks
    - Grandfather: Monthly backups — keep last N months
    """

    def __init__(
        self,
        daily_count: int = 7,
        weekly_count: int = 4,
        monthly_count: int = 12,
        yearly_count: int = 7
    ):
        self.daily_count = daily_count
        self.weekly_count = weekly_count
        self.monthly_count = monthly_count
        self.yearly_count = yearly_count

    def get_backups_to_delete(self, backups: list) -> list:
        """
        Given a list of backup job objects (sorted oldest-first),
        return the ones that should be deleted per GFS policy.
        """
        if not backups:
            return []
        sorted_backups = sorted(backups, key=lambda b: b.created_at)
        to_keep = set()

        # Keep daily backups
        daily_cutoff = datetime.utcnow() - timedelta(days=self.daily_count)
        for b in sorted_backups:
            if b.created_at >= daily_cutoff:
                to_keep.add(b.id)

        # Keep one backup per week for weekly retention
        weekly_cutoff = datetime.utcnow() - timedelta(weeks=self.weekly_count)
        weekly_seen = set()
        for b in reversed(sorted_backups):
            if b.created_at >= weekly_cutoff:
                week_key = b.created_at.isocalendar()[:2]  # (year, week)
                if week_key not in weekly_seen:
                    to_keep.add(b.id)
                    weekly_seen.add(week_key)

        # Keep one backup per month for monthly retention
        monthly_cutoff = datetime.utcnow() - timedelta(days=30 * self.monthly_count)
        monthly_seen = set()
        for b in reversed(sorted_backups):
            if b.created_at >= monthly_cutoff:
                month_key = (b.created_at.year, b.created_at.month)
                if month_key not in monthly_seen:
                    to_keep.add(b.id)
                    monthly_seen.add(month_key)

        # Keep one per year
        yearly_cutoff = datetime.utcnow() - timedelta(days=365 * self.yearly_count)
        yearly_seen = set()
        for b in reversed(sorted_backups):
            if b.created_at >= yearly_cutoff:
                year_key = b.created_at.year
                if year_key not in yearly_seen:
                    to_keep.add(b.id)
                    yearly_seen.add(year_key)

        to_delete = [b for b in sorted_backups if b.id not in to_keep]
        logger.info(f"Retention: keeping {len(to_keep)}, deleting {len(to_delete)} backups")
        return to_delete

    def calculate_retention_date(self, backup_type: str) -> datetime:
        """Return the expiry date for a given backup type."""
        mapping = {
            "daily": timedelta(days=self.daily_count),
            "weekly": timedelta(weeks=self.weekly_count),
            "monthly": timedelta(days=30 * self.monthly_count),
            "yearly": timedelta(days=365 * self.yearly_count),
        }
        return datetime.utcnow() + mapping.get(backup_type, timedelta(days=self.daily_count))

    def get_retention_summary(self, backups: list) -> Dict:
        to_delete = self.get_backups_to_delete(backups)
        return {
            "total_backups": len(backups),
            "to_delete": len(to_delete),
            "to_keep": len(backups) - len(to_delete),
            "delete_ids": [b.id for b in to_delete],
        }
