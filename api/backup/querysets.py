"""
Backup Module Custom QuerySets
Custom Django QuerySet and Manager classes for backup models.
"""

import logging
from datetime import timedelta
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class BackupQuerySet(models.QuerySet):
    """Custom QuerySet for Backup model"""

    def active(self):
        return self.filter(is_deleted=False)

    def completed(self):
        return self.filter(status="completed")

    def failed(self):
        return self.filter(status="failed")

    def running(self):
        return self.filter(status="running")

    def recent(self, days: int = 7):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

    def older_than(self, days: int):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__lt=cutoff)

    def by_storage(self, storage_type: str):
        return self.filter(storage_location__storage_type=storage_type)

    def with_size(self):
        return self.exclude(size_bytes__isnull=True)

    def total_size(self) -> int:
        from django.db.models import Sum
        result = self.aggregate(total=Sum("size_bytes"))
        return result["total"] or 0

    def success_rate(self) -> float:
        total = self.count()
        if total == 0:
            return 0.0
        completed = self.completed().count()
        return completed / total


class BackupScheduleQuerySet(models.QuerySet):
    """Custom QuerySet for BackupSchedule model"""

    def enabled(self):
        return self.filter(is_active=True)

    def disabled(self):
        return self.filter(is_active=False)

    def due(self):
        return self.filter(next_run_at__lte=timezone.now(), is_active=True)

    def overdue(self, threshold_minutes: int = 30):
        threshold = timezone.now() - timedelta(minutes=threshold_minutes)
        return self.filter(next_run_at__lte=threshold, is_active=True)


class BackupStorageLocationQuerySet(models.QuerySet):
    """Custom QuerySet for BackupStorageLocation model"""

    def active(self):
        return self.filter(is_active=True)

    def by_type(self, storage_type: str):
        return self.filter(storage_type=storage_type)

    def default(self):
        return self.filter(is_default=True).first()

    def healthy(self):
        return self.filter(health_status="healthy", is_active=True)
