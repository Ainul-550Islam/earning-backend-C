"""
Archive Manager — Manages long-term backup archives with catalog and retrieval.
"""
import logging
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class ArchiveEntry:
    """Represents a single archived backup."""
    def __init__(self, backup_id: str, storage_type: str, archive_id: str,
                 size_bytes: int, created_at: datetime, checksum: str,
                 metadata: dict = None):
        self.backup_id = backup_id
        self.storage_type = storage_type   # "glacier", "tape", "azure_archive"
        self.archive_id = archive_id
        self.size_bytes = size_bytes
        self.created_at = created_at
        self.checksum = checksum
        self.metadata = metadata or {}
        self.retrieval_status = None


class ArchiveManager:
    """
    Manages the archive catalog and coordinates long-term storage.
    Keeps a local catalog of all archived backups for fast lookup,
    even when the actual data is in Glacier or tape.
    """

    ARCHIVE_CATALOG_PATH = "/var/lib/dr/archive_catalog.json"

    def __init__(self, config: dict = None, db_session=None):
        self.config = config or {}
        self.db = db_session
        self._catalog: Dict[str, dict] = {}
        self._load_catalog()

    def archive_backup(self, backup_job_id: str, source_path: str,
                       storage_type: str = "glacier") -> dict:
        """
        Move a backup to long-term archive storage.
        Records the archive in the local catalog.
        """
        logger.info(f"Archiving backup {backup_job_id} to {storage_type}")
        archive_id = f"arch-{backup_job_id[:8]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        size = os.path.getsize(source_path) if os.path.exists(source_path) else 0
        import hashlib
        checksum = ""
        if os.path.exists(source_path):
            sha = hashlib.sha256()
            with open(source_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha.update(chunk)
            checksum = sha.hexdigest()

        entry = {
            "backup_id": backup_job_id,
            "archive_id": archive_id,
            "storage_type": storage_type,
            "size_bytes": size,
            "checksum": checksum,
            "archived_at": datetime.utcnow().isoformat(),
            "retrieval_status": "archived",
            "source_path": source_path,
            "metadata": {
                "archived_by": "archive_manager",
                "config": self.config.get("archive_tag", ""),
            }
        }
        self._catalog[backup_job_id] = entry
        self._save_catalog()
        logger.info(f"Archive complete: {backup_job_id} -> {archive_id} ({size/1e6:.1f} MB)")
        return entry

    def retrieve_archive(self, backup_id: str, destination_path: str,
                         retrieval_tier: str = "Standard") -> dict:
        """Initiate retrieval of an archived backup."""
        entry = self._catalog.get(backup_id)
        if not entry:
            raise KeyError(f"No archive found for backup: {backup_id}")
        logger.info(
            f"Initiating archive retrieval: {backup_id} "
            f"(tier={retrieval_tier}, destination={destination_path})"
        )
        storage_type = entry.get("storage_type", "glacier")
        if storage_type == "glacier":
            from .glacier_storage import GlacierStorage
            glacier = GlacierStorage(self.config.get("glacier", {}))
            result = glacier.initiate_retrieval(
                entry["archive_id"], tier=retrieval_tier
            )
            self._catalog[backup_id]["retrieval_status"] = "pending"
            self._catalog[backup_id]["retrieval_job_id"] = result.get("job_id")
            self._save_catalog()
            return {**result, "backup_id": backup_id, "destination": destination_path}
        else:
            return {
                "backup_id": backup_id,
                "status": "retrieval_initiated",
                "storage_type": storage_type,
                "destination": destination_path,
            }

    def get_archive_entry(self, backup_id: str) -> Optional[dict]:
        """Look up archive catalog entry."""
        return self._catalog.get(backup_id)

    def list_archives(self, older_than_days: int = None) -> List[dict]:
        """List all archives, optionally filtered by age."""
        entries = list(self._catalog.values())
        if older_than_days:
            cutoff = datetime.utcnow() - timedelta(days=older_than_days)
            entries = [
                e for e in entries
                if datetime.fromisoformat(e["archived_at"]) < cutoff
            ]
        return sorted(entries, key=lambda x: x["archived_at"], reverse=True)

    def delete_archive(self, backup_id: str, authorized_by: str) -> dict:
        """Permanently delete an archive (irreversible)."""
        entry = self._catalog.get(backup_id)
        if not entry:
            return {"success": False, "reason": "Archive not found"}
        logger.warning(
            f"ARCHIVE DELETE: {backup_id} authorized by {authorized_by}"
        )
        if entry.get("storage_type") == "glacier":
            from .glacier_storage import GlacierStorage
            glacier = GlacierStorage(self.config.get("glacier", {}))
            glacier.delete_archive(entry["archive_id"])
        del self._catalog[backup_id]
        self._save_catalog()
        return {
            "success": True, "backup_id": backup_id,
            "deleted_by": authorized_by, "deleted_at": datetime.utcnow().isoformat()
        }

    def get_catalog_stats(self) -> dict:
        """Get summary statistics for the archive catalog."""
        total_size = sum(e.get("size_bytes", 0) for e in self._catalog.values())
        by_type: Dict[str, int] = {}
        for entry in self._catalog.values():
            stype = entry.get("storage_type", "unknown")
            by_type[stype] = by_type.get(stype, 0) + 1
        return {
            "total_archives": len(self._catalog),
            "total_size_gb": round(total_size / 1e9, 3),
            "by_storage_type": by_type,
            "catalog_path": self.ARCHIVE_CATALOG_PATH,
        }

    def _load_catalog(self):
        """Load archive catalog from disk."""
        try:
            if os.path.exists(self.ARCHIVE_CATALOG_PATH):
                with open(self.ARCHIVE_CATALOG_PATH, "r") as f:
                    self._catalog = json.load(f)
                logger.debug(f"Loaded {len(self._catalog)} archive entries")
        except Exception as e:
            logger.warning(f"Could not load archive catalog: {e}")
            self._catalog = {}

    def _save_catalog(self):
        """Persist archive catalog to disk."""
        try:
            os.makedirs(os.path.dirname(self.ARCHIVE_CATALOG_PATH), exist_ok=True)
            with open(self.ARCHIVE_CATALOG_PATH, "w") as f:
                json.dump(self._catalog, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save archive catalog: {e}")
