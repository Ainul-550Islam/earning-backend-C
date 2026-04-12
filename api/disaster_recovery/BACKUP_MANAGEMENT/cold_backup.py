"""Cold Backup — Offline backup requiring service shutdown."""
import logging
import subprocess
from datetime import datetime
logger = logging.getLogger(__name__)

class ColdBackupManager:
    """
    Cold backups require stopping the service.
    Simpler and always consistent — used for critical migrations.
    """
    def __init__(self, service_name: str, config: dict):
        self.service_name = service_name
        self.config = config

    def stop_service(self) -> bool:
        logger.warning(f"STOPPING SERVICE: {self.service_name}")
        try:
            subprocess.run(["systemctl", "stop", self.service_name], timeout=60)
            return True
        except Exception as e:
            logger.error(f"Failed to stop {self.service_name}: {e}")
            return False

    def start_service(self) -> bool:
        logger.info(f"STARTING SERVICE: {self.service_name}")
        try:
            subprocess.run(["systemctl", "start", self.service_name], timeout=60)
            return True
        except Exception as e:
            logger.error(f"Failed to start {self.service_name}: {e}")
            return False

    def backup_with_downtime(self, source: str, destination: str) -> dict:
        import shutil, os
        started = datetime.utcnow()
        stopped = self.stop_service()
        try:
            shutil.copytree(source, destination, dirs_exist_ok=True)
            size = sum(
                os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(destination) for f in fs
            )
        finally:
            self.start_service()
        duration = (datetime.utcnow() - started).total_seconds()
        logger.info(f"Cold backup done: {duration:.1f}s downtime")
        return {"destination": destination, "size_bytes": size, "downtime_seconds": duration, "stopped": stopped}
