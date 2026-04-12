"""Read Replica Manager — Manages read-only replicas for query distribution."""
import logging
import random
logger = logging.getLogger(__name__)

class ReadReplicaManager:
    """Routes read queries across available replicas using round-robin or least-connections."""
    def __init__(self, replicas: list, strategy: str = "round_robin"):
        self.replicas = replicas
        self.strategy = strategy
        self._current = 0

    def get_replica(self) -> dict:
        healthy = [r for r in self.replicas if r.get("healthy", True)]
        if not healthy:
            raise Exception("No healthy read replicas available")
        if self.strategy == "round_robin":
            replica = healthy[self._current % len(healthy)]
            self._current += 1
        elif self.strategy == "random":
            replica = random.choice(healthy)
        else:
            replica = healthy[0]
        return replica

    def mark_unhealthy(self, replica_host: str):
        for r in self.replicas:
            if r.get("host") == replica_host:
                r["healthy"] = False
                logger.warning(f"Replica marked unhealthy: {replica_host}")

    def mark_healthy(self, replica_host: str):
        for r in self.replicas:
            if r.get("host") == replica_host:
                r["healthy"] = True
                logger.info(f"Replica marked healthy: {replica_host}")
