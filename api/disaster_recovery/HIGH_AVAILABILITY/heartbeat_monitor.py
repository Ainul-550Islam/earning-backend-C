"""Heartbeat Monitor — Sends and monitors heartbeat signals between nodes."""
import logging
import threading
import time
logger = logging.getLogger(__name__)

class HeartbeatMonitor:
    def __init__(self, interval: int = 5, timeout: int = 15):
        self.interval = interval
        self.timeout = timeout
        self._heartbeats: dict = {}
        self._running = False

    def record_heartbeat(self, node_id: str):
        self._heartbeats[node_id] = time.time()

    def is_alive(self, node_id: str) -> bool:
        last = self._heartbeats.get(node_id)
        if not last:
            return False
        return time.time() - last <= self.timeout

    def get_dead_nodes(self) -> list:
        return [nid for nid in self._heartbeats if not self.is_alive(nid)]

    def send_heartbeat(self, target_host: str, target_port: int = 9000) -> bool:
        import socket
        try:
            with socket.create_connection((target_host, target_port), timeout=3):
                return True
        except Exception:
            return False
