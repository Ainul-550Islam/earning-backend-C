"""Full Backup Manager — Complete data backup with no dependencies."""
import logging
from datetime import datetime
logger = logging.getLogger(__name__)

class FullBackupManager:
    """Manages full backups: the base for all other backup types."""
    def __init__(self, db_session=None):
        self.db = db_session

    def create_full_backup_config(self, policy) -> dict:
        return {
            "backup_type": "full",
            "source_path": policy.target_path,
            "target_database": policy.target_database,
            "enable_compression": policy.enable_compression,
            "enable_encryption": policy.enable_encryption,
            "started_at": datetime.utcnow().isoformat(),
        }

    def estimate_size(self, source_path: str) -> int:
        import os
        total = 0
        if os.path.isfile(source_path):
            return os.path.getsize(source_path)
        for root, _, files in os.walk(source_path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total
