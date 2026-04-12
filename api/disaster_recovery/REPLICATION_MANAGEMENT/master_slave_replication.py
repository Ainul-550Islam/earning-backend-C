"""Master-Slave Replication Manager."""
import logging
logger = logging.getLogger(__name__)

class MasterSlaveReplication:
    """Manages single-master, multiple-slave PostgreSQL replication."""
    def __init__(self, master_config: dict, slave_configs: list):
        self.master = master_config
        self.slaves = slave_configs

    def get_replication_status(self) -> list:
        import subprocess
        try:
            result = subprocess.run(
                ["psql", "-h", self.master["host"], "-U", self.master["user"],
                 "-c", "SELECT * FROM pg_stat_replication;", "-t"],
                capture_output=True, text=True, timeout=10
            )
            return [{"raw": result.stdout}]
        except Exception:
            return [{"status": "unknown"}]

    def add_slave(self, slave_config: dict) -> bool:
        logger.info(f"Adding slave: {slave_config.get('host')}")
        self.slaves.append(slave_config)
        return True

    def remove_slave(self, slave_host: str) -> bool:
        self.slaves = [s for s in self.slaves if s.get("host") != slave_host]
        logger.info(f"Removed slave: {slave_host}")
        return True
