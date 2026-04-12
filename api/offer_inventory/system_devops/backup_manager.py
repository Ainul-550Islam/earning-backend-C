# api/offer_inventory/system_devops/backup_manager.py
"""
Backup Manager — Automated database and file backup management.
"""
import logging
import os
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

BACKUP_DIR     = '/tmp/backups'
RETENTION_DAYS = 30


class BackupManager:
    """Database and media backup management."""

    @classmethod
    def create_db_backup(cls, destination: str = BACKUP_DIR) -> dict:
        """Create a database backup using pg_dump."""
        import subprocess, gzip
        from django.conf import settings

        db    = settings.DATABASES['default']
        fname = f'offer_inventory_{timezone.now().strftime("%Y%m%d_%H%M%S")}.sql.gz'
        fpath = os.path.join(destination, fname)
        os.makedirs(destination, exist_ok=True)

        cmd = [
            'pg_dump',
            '-h', db.get('HOST', 'localhost'),
            '-U', db.get('USER', 'postgres'),
            '-d', db.get('NAME', ''),
            '-t', 'offer_inventory_*',
            '--no-owner', '--no-acl',
        ]

        from api.offer_inventory.models import BackupLog
        log = BackupLog.objects.create(
            backup_type='db', status='running', started_by='system'
        )
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            with gzip.open(fpath, 'wb') as f:
                f.write(result.stdout)
            size = os.path.getsize(fpath)
            BackupLog.objects.filter(id=log.id).update(
                status='completed', file_path=fpath, file_size=size
            )
            logger.info(f'Backup created: {fpath} ({size} bytes)')
            return {'success': True, 'file': fpath, 'size_bytes': size}
        except Exception as e:
            BackupLog.objects.filter(id=log.id).update(status='failed', error=str(e))
            logger.error(f'Backup failed: {e}')
            return {'success': False, 'error': str(e)}

    @classmethod
    def cleanup_old_backups(cls, directory: str = BACKUP_DIR) -> int:
        """Remove backup files older than retention period."""
        cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)
        removed = 0
        try:
            for fname in os.listdir(directory):
                fpath = os.path.join(directory, fname)
                if os.path.isfile(fpath):
                    if os.path.getmtime(fpath) < cutoff.timestamp():
                        os.remove(fpath)
                        removed += 1
        except Exception as e:
            logger.error(f'Backup cleanup error: {e}')
        logger.info(f'Removed {removed} old backup files.')
        return removed

    @staticmethod
    def get_backup_history(limit: int = 20) -> list:
        """List recent backup records."""
        from api.offer_inventory.models import BackupLog
        return list(
            BackupLog.objects.all()
            .order_by('-created_at')
            .values('backup_type', 'status', 'file_size', 'created_at')
            [:limit]
        )

    @staticmethod
    def get_backup_status() -> dict:
        """Current backup system status."""
        history = BackupManager.get_backup_history(limit=1)
        last    = history[0] if history else None
        return {
            'last_backup'    : last,
            'retention_days' : RETENTION_DAYS,
            'backup_dir'     : BACKUP_DIR,
        }
