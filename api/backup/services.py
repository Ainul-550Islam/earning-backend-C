# api/backup/services.py
"""
Business logic for backup. Move complex logic out of views.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BackupService:
    """Service for backup operations."""

    @staticmethod
    def get_last_backup_status() -> Dict[str, Any]:
        """Return status of most recent backup."""
        try:
            from .models import Backup
            last = Backup.objects.order_by('-created_at').first()
            if not last:
                return {"status": "none", "last_run": None}
            return {
                "status": getattr(last, 'status', 'unknown'),
                "last_run": getattr(last, 'created_at', None),
                "backup_type": getattr(last, 'backup_type', None),
            }
        except Exception as e:
            logger.debug("Backup status: %s", e)
            return {"status": "error", "last_run": None}
