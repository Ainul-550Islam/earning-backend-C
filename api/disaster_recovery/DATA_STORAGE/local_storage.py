"""
Local Storage Backend — Stores backups on local or mounted filesystem.
"""
import os
import shutil
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class LocalStorage:
    """
    Local filesystem storage backend.
    Supports local disk, NFS mounts, and any POSIX-compatible filesystem.
    Includes directory structure management, quota monitoring, and cleanup.
    """

    def __init__(self, config: dict):
        self.config = config
        self.base_path = Path(config.get("base_path", "/var/backups/dr"))
        self.max_usage_pct = config.get("max_usage_percent", 85.0)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upload(self, local_source: str, remote_path: str, metadata: dict = None) -> dict:
        """Copy a file into the local backup storage tree."""
        dest = self.base_path / remote_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_source, str(dest))
        size = dest.stat().st_size
        checksum = self._compute_checksum(str(dest))
        # Write metadata sidecar file
        if metadata:
            meta_path = str(dest) + ".meta"
            import json
            with open(meta_path, "w") as f:
                json.dump({**metadata, "checksum": checksum, "uploaded_at": datetime.utcnow().isoformat()}, f, indent=2)
        logger.info(f"LocalStorage upload: {local_source} -> {dest} ({size:,} bytes)")
        return {"path": str(dest), "size_bytes": size, "checksum": checksum}

    def download(self, remote_path: str, local_dest: str) -> dict:
        """Copy a backup file from local storage to destination."""
        src = self.base_path / remote_path
        if not src.exists():
            raise FileNotFoundError(f"Backup not found: {src}")
        Path(local_dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), local_dest)
        size = os.path.getsize(local_dest)
        logger.info(f"LocalStorage download: {src} -> {local_dest} ({size:,} bytes)")
        return {"local_path": local_dest, "size_bytes": size}

    def delete(self, remote_path: str) -> bool:
        """Delete a backup file and its metadata."""
        target = self.base_path / remote_path
        if target.exists():
            target.unlink()
        meta = Path(str(target) + ".meta")
        if meta.exists():
            meta.unlink()
        logger.info(f"LocalStorage delete: {target}")
        return True

    def list_objects(self, prefix: str = "", recursive: bool = True) -> List[dict]:
        """List all backup files under a path prefix."""
        search_dir = self.base_path / prefix if prefix else self.base_path
        objects = []
        if not search_dir.exists():
            return objects
        pattern = "**/*" if recursive else "*"
        for path in search_dir.glob(pattern):
            if path.is_file() and not path.name.endswith(".meta"):
                stat = path.stat()
                rel_path = path.relative_to(self.base_path)
                objects.append({
                    "path": str(rel_path),
                    "size_bytes": stat.st_size,
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                })
        return sorted(objects, key=lambda x: x["last_modified"], reverse=True)

    def file_exists(self, remote_path: str) -> bool:
        return (self.base_path / remote_path).exists()

    def get_file_size(self, remote_path: str) -> int:
        target = self.base_path / remote_path
        return target.stat().st_size if target.exists() else 0

    def get_disk_usage(self) -> dict:
        """Get disk usage statistics for the storage path."""
        total, used, free = shutil.disk_usage(str(self.base_path))
        backup_size = self._get_directory_size(self.base_path)
        usage_pct = (used / total) * 100
        return {
            "base_path": str(self.base_path),
            "total_gb": round(total / 1e9, 2),
            "used_gb": round(used / 1e9, 2),
            "free_gb": round(free / 1e9, 2),
            "usage_percent": round(usage_pct, 2),
            "backup_size_gb": round(backup_size / 1e9, 3),
            "is_over_limit": usage_pct >= self.max_usage_pct,
        }

    def check_space_available(self, required_bytes: int) -> bool:
        """Check if enough free space is available for a backup."""
        _, _, free = shutil.disk_usage(str(self.base_path))
        # Keep 10% buffer
        available = free * 0.9
        if available < required_bytes:
            logger.warning(f"Insufficient space: need {required_bytes:,}, have {free:,} free")
            return False
        return True

    def cleanup_old_backups(self, older_than_days: int) -> dict:
        """Delete backup files older than N days."""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        deleted_count = 0
        freed_bytes = 0
        for obj in self.list_objects():
            mtime = datetime.fromisoformat(obj["last_modified"])
            if mtime < cutoff:
                size = obj["size_bytes"]
                if self.delete(obj["path"]):
                    deleted_count += 1
                    freed_bytes += size
        logger.info(f"Cleanup: deleted {deleted_count} files, freed {freed_bytes / 1e6:.1f} MB")
        return {"deleted": deleted_count, "freed_bytes": freed_bytes,
                "freed_mb": round(freed_bytes / 1e6, 2)}

    def create_directory(self, path: str) -> str:
        """Create a directory in the storage tree."""
        full_path = self.base_path / path
        full_path.mkdir(parents=True, exist_ok=True)
        return str(full_path)

    def move(self, source_path: str, dest_path: str) -> bool:
        """Move/rename a backup file."""
        src = self.base_path / source_path
        dst = self.base_path / dest_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True

    def verify_integrity(self, remote_path: str, expected_checksum: str) -> bool:
        """Verify file integrity by comparing checksums."""
        target = self.base_path / remote_path
        if not target.exists():
            return False
        actual = self._compute_checksum(str(target))
        return actual == expected_checksum

    def _get_directory_size(self, path: Path) -> int:
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
        return total

    @staticmethod
    def _compute_checksum(path: str) -> str:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
