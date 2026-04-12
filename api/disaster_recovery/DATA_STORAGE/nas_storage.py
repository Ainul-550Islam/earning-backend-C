"""
NAS Storage Backend — Network Attached Storage (NFS/SMB) integration.
"""
import os
import shutil
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class NASStorage:
    """
    NAS (Network Attached Storage) backend using NFS or SMB/CIFS mounts.
    Manages mount lifecycle, health checks, and automatic reconnection.
    """

    def __init__(self, config: dict):
        self.config = config
        self.server = config["server"]
        self.share = config["share"]
        self.mount_point = Path(config.get("mount_point", f"/mnt/nas_dr"))
        self.protocol = config.get("protocol", "nfs")   # nfs or smb
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.options = config.get("mount_options", "rw,soft,timeo=30,retrans=3")
        self._mounted = False

    def mount(self) -> bool:
        """Mount the NAS share."""
        self.mount_point.mkdir(parents=True, exist_ok=True)
        if self._is_already_mounted():
            logger.info(f"NAS already mounted: {self.mount_point}")
            self._mounted = True
            return True
        if self.protocol == "nfs":
            cmd = ["mount", "-t", "nfs", f"{self.server}:{self.share}",
                   str(self.mount_point), "-o", self.options]
        else:  # smb/cifs
            creds = f"username={self.username},password={self.password}"
            cmd = ["mount", "-t", "cifs", f"//{self.server}/{self.share}",
                   str(self.mount_point), "-o", f"{self.options},{creds}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self._mounted = True
                logger.info(f"NAS mounted: {self.server}:{self.share} -> {self.mount_point}")
                return True
            else:
                logger.error(f"NAS mount failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("NAS mount timed out")
            return False

    def unmount(self) -> bool:
        """Unmount the NAS share."""
        try:
            subprocess.run(["umount", str(self.mount_point)], timeout=30, check=True)
            self._mounted = False
            logger.info(f"NAS unmounted: {self.mount_point}")
            return True
        except Exception as e:
            logger.warning(f"NAS unmount warning: {e}")
            return False

    def ensure_mounted(self) -> bool:
        """Ensure NAS is mounted, remount if necessary."""
        if not self._is_already_mounted():
            logger.warning("NAS not mounted — attempting remount")
            return self.mount()
        return True

    def upload(self, local_path: str, remote_path: str) -> dict:
        """Copy a file to NAS storage."""
        self.ensure_mounted()
        dest = self.mount_point / remote_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, str(dest))
        size = os.path.getsize(str(dest))
        logger.info(f"NAS upload: {local_path} -> {dest} ({size:,} bytes)")
        return {"nas_path": str(dest), "size_bytes": size,
                "server": self.server, "share": self.share}

    def download(self, remote_path: str, local_dest: str) -> dict:
        """Copy a file from NAS to local storage."""
        self.ensure_mounted()
        src = self.mount_point / remote_path
        if not src.exists():
            raise FileNotFoundError(f"NAS file not found: {src}")
        Path(local_dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), local_dest)
        size = os.path.getsize(local_dest)
        return {"local_path": local_dest, "size_bytes": size}

    def delete(self, remote_path: str) -> bool:
        """Delete a file from NAS."""
        self.ensure_mounted()
        target = self.mount_point / remote_path
        if target.exists():
            target.unlink()
        return True

    def list_objects(self, prefix: str = "") -> List[dict]:
        """List files on NAS storage."""
        self.ensure_mounted()
        search_dir = self.mount_point / prefix if prefix else self.mount_point
        objects = []
        if not search_dir.exists():
            return objects
        for path in search_dir.rglob("*"):
            if path.is_file():
                stat = path.stat()
                rel = path.relative_to(self.mount_point)
                objects.append({
                    "path": str(rel),
                    "size_bytes": stat.st_size,
                    "last_modified": stat.st_mtime,
                })
        return objects

    def get_usage(self) -> dict:
        """Get NAS share usage statistics."""
        self.ensure_mounted()
        total, used, free = shutil.disk_usage(str(self.mount_point))
        return {
            "server": self.server, "share": self.share,
            "total_gb": round(total / 1e9, 2),
            "used_gb": round(used / 1e9, 2),
            "free_gb": round(free / 1e9, 2),
            "usage_percent": round(used / total * 100, 2),
        }

    def health_check(self) -> dict:
        """Verify NAS is reachable and writable."""
        if not self.ensure_mounted():
            return {"healthy": False, "reason": "Cannot mount NAS"}
        test_file = self.mount_point / ".dr_health_check"
        try:
            test_file.write_text("ok")
            test_file.unlink()
            return {"healthy": True, "server": self.server, "mount": str(self.mount_point)}
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    def _is_already_mounted(self) -> bool:
        try:
            result = subprocess.run(["mountpoint", "-q", str(self.mount_point)], timeout=5)
            return result.returncode == 0
        except Exception:
            return (self.mount_point / ".").exists()
