"""
Backup Module Repositories
Data access layer separating business logic from ORM queries.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class BackupRepository:
    """Repository for Backup model — all DB access goes here"""

    def get_by_id(self, backup_id: str):
        from api.backup.models import Backup
        try:
            return Backup.objects.get(id=backup_id)
        except Backup.DoesNotExist:
            return None

    def get_all(self):
        from api.backup.models import Backup
        return Backup.objects.all()

    def get_recent(self, days: int = 7):
        from api.backup.models import Backup
        cutoff = timezone.now() - timedelta(days=days)
        return Backup.objects.filter(created_at__gte=cutoff)

    def get_by_status(self, status: str):
        from api.backup.models import Backup
        return Backup.objects.filter(status=status)

    def get_expired(self):
        from api.backup.models import Backup
        return Backup.objects.filter(expires_at__lt=timezone.now())

    def create(self, data: Dict[str, Any]):
        from api.backup.models import Backup
        return Backup.objects.create(**data)

    def update(self, backup_id: str, data: Dict[str, Any]):
        from api.backup.models import Backup
        updated = Backup.objects.filter(id=backup_id).update(**data)
        return updated > 0

    def delete(self, backup_id: str) -> bool:
        from api.backup.models import Backup
        deleted, _ = Backup.objects.filter(id=backup_id).delete()
        return deleted > 0

    def count_by_status(self) -> Dict[str, int]:
        from api.backup.models import Backup
        from django.db.models import Count
        result = Backup.objects.values("status").annotate(count=Count("id"))
        return {row["status"]: row["count"] for row in result}

    def total_size_bytes(self) -> int:
        from api.backup.models import Backup
        from django.db.models import Sum
        result = Backup.objects.aggregate(total=Sum("size_bytes"))
        return result["total"] or 0


class BackupScheduleRepository:
    """Repository for BackupSchedule model"""

    def get_all_active(self):
        from api.backup.models import BackupSchedule
        return BackupSchedule.objects.filter(is_active=True)

    def get_due_schedules(self):
        from api.backup.models import BackupSchedule
        return BackupSchedule.objects.filter(
            is_active=True, next_run_at__lte=timezone.now()
        )

    def mark_triggered(self, schedule_id: str) -> bool:
        from api.backup.models import BackupSchedule
        updated = BackupSchedule.objects.filter(id=schedule_id).update(
            last_run_at=timezone.now()
        )
        return updated > 0


class StorageLocationRepository:
    """Repository for BackupStorageLocation model"""

    def get_default(self):
        from api.backup.models import BackupStorageLocation
        return BackupStorageLocation.objects.filter(is_default=True, is_active=True).first()

    def get_all_active(self):
        from api.backup.models import BackupStorageLocation
        return BackupStorageLocation.objects.filter(is_active=True)

    def get_by_type(self, storage_type: str):
        from api.backup.models import BackupStorageLocation
        return BackupStorageLocation.objects.filter(
            storage_type=storage_type, is_active=True
        )
