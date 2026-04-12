"""
SAN Storage Backend — Storage Area Network block device management.
"""
import os
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class SANStorage:
    """
    SAN (Storage Area Network) backend using iSCSI or Fibre Channel.
    Manages LUN presentation, filesystem operations, and backup storage
    on enterprise block storage systems.
    """

    def __init__(self, config: dict):
        self.config = config
        self.target_iqn = config.get("target_iqn", "")       # iSCSI target IQN
        self.portal = config.get("portal", "")               # iSCSI portal IP:port
        self.lun_id = config.get("lun_id", 0)
        self.device_path = config.get("device_path", "/dev/sdb")
        self.mount_point = Path(config.get("mount_point", "/mnt/san_dr"))
        self.filesystem = config.get("filesystem", "ext4")
        self.chap_username = config.get("chap_username", "")
        self.chap_password = config.get("chap_password", "")

    def discover_target(self) -> List[str]:
        """Discover iSCSI targets on the portal."""
        cmd = ["iscsiadm", "-m", "discovery", "-t", "st", "-p", self.portal]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            targets = []
            for line in result.stdout.splitlines():
                if "iqn." in line:
                    targets.append(line.split()[-1])
            logger.info(f"Discovered {len(targets)} iSCSI targets at {self.portal}")
            return targets
        except Exception as e:
            logger.error(f"iSCSI discovery failed: {e}")
            return []

    def login(self) -> bool:
        """Login to iSCSI target."""
        if not self.target_iqn:
            logger.warning("No iSCSI target IQN configured")
            return False
        cmd = ["iscsiadm", "-m", "node", "-T", self.target_iqn, "-p", self.portal, "--login"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 or "already" in result.stderr:
                logger.info(f"iSCSI login successful: {self.target_iqn}")
                return True
            logger.error(f"iSCSI login failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"iSCSI login error: {e}")
            return False

    def logout(self) -> bool:
        """Logout from iSCSI target."""
        cmd = ["iscsiadm", "-m", "node", "-T", self.target_iqn, "-p", self.portal, "--logout"]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            return True
        except Exception:
            return False

    def mount(self) -> bool:
        """Mount the SAN LUN filesystem."""
        self.mount_point.mkdir(parents=True, exist_ok=True)
        # Check if already mounted
        result = subprocess.run(
            ["mountpoint", "-q", str(self.mount_point)], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return True
        cmd = ["mount", "-t", self.filesystem, self.device_path, str(self.mount_point),
               "-o", "rw,noatime"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info(f"SAN mounted: {self.device_path} -> {self.mount_point}")
                return True
            logger.error(f"SAN mount failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"SAN mount error: {e}")
            return False

    def upload(self, local_path: str, remote_path: str) -> dict:
        """Copy backup file to SAN mount."""
        if not self.mount():
            raise RuntimeError("SAN not mounted")
        import shutil
        dest = self.mount_point / remote_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, str(dest))
        size = os.path.getsize(str(dest))
        logger.info(f"SAN upload: {local_path} -> {dest} ({size:,} bytes)")
        return {"path": str(dest), "size_bytes": size, "device": self.device_path}

    def download(self, remote_path: str, local_dest: str) -> dict:
        """Copy file from SAN to local path."""
        if not self.mount():
            raise RuntimeError("SAN not mounted")
        import shutil
        src = self.mount_point / remote_path
        Path(local_dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), local_dest)
        return {"local_path": local_dest, "size_bytes": os.path.getsize(local_dest)}

    def delete(self, remote_path: str) -> bool:
        """Delete a file from SAN storage."""
        target = self.mount_point / remote_path
        if target.exists():
            target.unlink()
        return True

    def create_snapshot(self, snapshot_name: str) -> dict:
        """Create a filesystem snapshot using LVM or storage array snapshot."""
        # LVM snapshot example
        vg = self.config.get("lvm_vg", "san_vg")
        lv = self.config.get("lvm_lv", "backup_lv")
        snap_size = self.config.get("snapshot_size", "50G")
        cmd = ["lvcreate", "--size", snap_size, "--snapshot",
               "--name", snapshot_name, f"/dev/{vg}/{lv}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            success = result.returncode == 0
            if success:
                logger.info(f"SAN snapshot created: /dev/{vg}/{snapshot_name}")
            return {"snapshot": snapshot_name, "success": success,
                    "device": f"/dev/{vg}/{snapshot_name}"}
        except Exception as e:
            return {"snapshot": snapshot_name, "success": False, "error": str(e)}

    def get_usage(self) -> dict:
        """Get SAN storage usage."""
        import shutil
        try:
            total, used, free = shutil.disk_usage(str(self.mount_point))
            return {"total_gb": round(total/1e9,2), "used_gb": round(used/1e9,2),
                    "free_gb": round(free/1e9,2),
                    "usage_percent": round(used/total*100,2),
                    "device": self.device_path}
        except Exception:
            return {"device": self.device_path, "status": "not_mounted"}
