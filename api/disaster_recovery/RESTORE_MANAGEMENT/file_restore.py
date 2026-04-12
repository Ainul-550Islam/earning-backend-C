"""
File Restore — Restores individual files and directories from backup archives.
"""
import logging
import os
import subprocess
import shutil
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class FileRestore:
    """
    Restores individual files or directories from tar/zip archives.
    Supports wildcard patterns, version selection, and conflict handling.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.conflict_strategy = config.get("conflict_strategy", "rename") if config else "rename"
        # conflict_strategy: "overwrite", "rename", "skip"

    def restore_file(self, archive_path: str, file_path_in_archive: str,
                      destination: str, create_backup: bool = True) -> dict:
        """Restore a single file from an archive."""
        started_at = datetime.utcnow()
        dest_path = Path(destination) / Path(file_path_in_archive).name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        # Handle conflict
        if dest_path.exists() and create_backup:
            self._handle_conflict(dest_path)
        logger.info(f"File restore: {file_path_in_archive} -> {dest_path}")
        if archive_path.endswith(".zip"):
            cmd = ["unzip", "-p", archive_path, file_path_in_archive]
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=300)
                if result.returncode == 0:
                    with open(str(dest_path), "wb") as f:
                        f.write(result.stdout)
                    success = True
                else:
                    success = False
            except Exception as e:
                logger.error(f"Zip extract error: {e}")
                success = False
        else:
            # tar archive
            extract_cmd = self._build_tar_extract_cmd(
                archive_path, file_path_in_archive, str(dest_path.parent)
            )
            try:
                result = subprocess.run(
                    extract_cmd, capture_output=True, text=True, timeout=300
                )
                success = result.returncode == 0
            except Exception as e:
                logger.error(f"Tar extract error: {e}")
                success = False
        size = dest_path.stat().st_size if dest_path.exists() else 0
        duration = (datetime.utcnow() - started_at).total_seconds()
        return {
            "success": success,
            "file": file_path_in_archive,
            "destination": str(dest_path),
            "size_bytes": size,
            "duration_seconds": round(duration, 3),
        }

    def restore_directory(self, archive_path: str, dir_path_in_archive: str,
                           destination: str) -> dict:
        """Restore an entire directory from a tar archive."""
        started_at = datetime.utcnow()
        os.makedirs(destination, exist_ok=True)
        logger.info(f"Directory restore: {dir_path_in_archive} -> {destination}")
        if archive_path.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar")):
            cmd = [
                "tar", "-xf", archive_path, "-C", destination,
                "--wildcards", f"{dir_path_in_archive.rstrip('/')}/*",
                "--strip-components", str(dir_path_in_archive.count("/")),
            ]
        else:
            cmd = ["unzip", archive_path, f"{dir_path_in_archive}/*", "-d", destination]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            success = result.returncode == 0
        except Exception as e:
            success = False
            logger.error(f"Directory restore error: {e}")
        # Count restored
        file_count = sum(1 for _ in Path(destination).rglob("*") if _.is_file())
        total_size = sum(
            f.stat().st_size for f in Path(destination).rglob("*") if f.is_file()
        )
        duration = (datetime.utcnow() - started_at).total_seconds()
        return {
            "success": success,
            "source_dir": dir_path_in_archive,
            "destination": destination,
            "files_restored": file_count,
            "bytes_restored": total_size,
            "duration_seconds": round(duration, 2),
        }

    def restore_by_pattern(self, archive_path: str, patterns: List[str],
                            destination: str) -> dict:
        """Restore files matching glob patterns from archive."""
        os.makedirs(destination, exist_ok=True)
        restored = []
        failed = []
        for pattern in patterns:
            cmd = [
                "tar", "-xf", archive_path, "-C", destination,
                "--wildcards", pattern,
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=3600)
                if result.returncode == 0:
                    restored.append(pattern)
                else:
                    failed.append({"pattern": pattern, "error": result.stderr.decode()[:200]})
            except Exception as e:
                failed.append({"pattern": pattern, "error": str(e)})
        return {
            "success": len(failed) == 0,
            "patterns_restored": restored,
            "patterns_failed": failed,
            "destination": destination,
        }

    def list_archive_contents(self, archive_path: str, prefix: str = "") -> List[dict]:
        """List contents of a backup archive."""
        if archive_path.endswith(".zip"):
            cmd = ["unzip", "-l", archive_path]
        else:
            cmd = ["tar", "-tvf", archive_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return []
            entries = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if not parts:
                    continue
                # tar format: permissions links owner group size date time path
                if len(parts) >= 9:
                    path = parts[-1]
                    size = int(parts[4]) if parts[4].isdigit() else 0
                    if not prefix or path.startswith(prefix):
                        entries.append({"path": path, "size_bytes": size})
            return entries
        except Exception as e:
            logger.error(f"Error listing archive: {e}")
            return []

    def _handle_conflict(self, dest_path: Path):
        """Handle file conflict based on strategy."""
        if not dest_path.exists():
            return
        if self.conflict_strategy == "overwrite":
            pass
        elif self.conflict_strategy == "rename":
            ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            backup = dest_path.with_suffix(f".bak_{ts}")
            shutil.move(str(dest_path), str(backup))
            logger.info(f"Existing file backed up to: {backup}")
        elif self.conflict_strategy == "skip":
            raise FileExistsError(f"File already exists: {dest_path}")

    @staticmethod
    def _build_tar_extract_cmd(archive: str, file_path: str, dest_dir: str) -> List[str]:
        flags = "-xzf" if archive.endswith(".gz") else (
            "-xjf" if archive.endswith(".bz2") else "-xf"
        )
        return ["tar", flags, archive, "-C", dest_dir, "--wildcards", f"*{file_path}*"]
