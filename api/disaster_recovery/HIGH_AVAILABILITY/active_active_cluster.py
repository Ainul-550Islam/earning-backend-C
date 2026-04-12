"""
Active-Active Cluster — All nodes handle traffic simultaneously
"""
import logging
import random
import threading
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ActiveActiveCluster:
    """
    Manages an active-active HA cluster where all nodes process requests
    simultaneously. Uses consistent hashing or round-robin for routing.
    All nodes are writeable — conflict resolution is required.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._nodes: List[dict] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._request_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}

    def add_node(self, node_id: str, host: str, port: int,
                 weight: int = 100, zone: str = "default") -> dict:
        with self._lock:
            node = {
                "id": node_id, "host": host, "port": port,
                "weight": weight, "zone": zone,
                "healthy": True, "added_at": datetime.utcnow().isoformat(),
                "connections": 0,
            }
            self._nodes.append(node)
            self._request_counts[node_id] = 0
            self._error_counts[node_id] = 0
            logger.info(f"Active-Active: node added {node_id} ({host}:{port})")
            return node

    def remove_node(self, node_id: str):
        with self._lock:
            self._nodes = [n for n in self._nodes if n["id"] != node_id]
            logger.info(f"Active-Active: node removed {node_id}")

    def mark_node_unhealthy(self, node_id: str):
        with self._lock:
            for n in self._nodes:
                if n["id"] == node_id:
                    n["healthy"] = False
                    logger.warning(f"Active-Active: node {node_id} marked unhealthy")

    def mark_node_healthy(self, node_id: str):
        with self._lock:
            for n in self._nodes:
                if n["id"] == node_id:
                    n["healthy"] = True
                    logger.info(f"Active-Active: node {node_id} restored to healthy")

    def get_next_node(self, strategy: str = "round_robin") -> Optional[dict]:
        """Select next node using the specified load-balancing strategy."""
        with self._lock:
            healthy = [n for n in self._nodes if n["healthy"]]
            if not healthy:
                logger.error("Active-Active: no healthy nodes available!")
                return None
            if strategy == "round_robin":
                node = healthy[self._current_index % len(healthy)]
                self._current_index += 1
            elif strategy == "least_connections":
                node = min(healthy, key=lambda n: n["connections"])
            elif strategy == "weighted_random":
                total = sum(n["weight"] for n in healthy)
                r = random.uniform(0, total)
                cumulative = 0
                node = healthy[-1]
                for n in healthy:
                    cumulative += n["weight"]
                    if r <= cumulative:
                        node = n
                        break
            elif strategy == "random":
                node = random.choice(healthy)
            else:
                node = healthy[0]
            node["connections"] += 1
            self._request_counts[node["id"]] = self._request_counts.get(node["id"], 0) + 1
            return node

    def release_connection(self, node_id: str):
        """Call when a request completes to decrement connection count."""
        with self._lock:
            for n in self._nodes:
                if n["id"] == node_id and n["connections"] > 0:
                    n["connections"] -= 1

    def record_error(self, node_id: str, auto_disable_threshold: int = 10):
        with self._lock:
            self._error_counts[node_id] = self._error_counts.get(node_id, 0) + 1
            if self._error_counts[node_id] >= auto_disable_threshold:
                self.mark_node_unhealthy(node_id)
                logger.error(f"Node {node_id} auto-disabled after {auto_disable_threshold} errors")

    def get_cluster_stats(self) -> dict:
        with self._lock:
            healthy = [n for n in self._nodes if n["healthy"]]
            return {
                "mode": "active_active",
                "total_nodes": len(self._nodes),
                "healthy_nodes": len(healthy),
                "total_requests_served": sum(self._request_counts.values()),
                "total_errors": sum(self._error_counts.values()),
                "nodes": [
                    {**n, "requests": self._request_counts.get(n["id"], 0),
                     "errors": self._error_counts.get(n["id"], 0)}
                    for n in self._nodes
                ],
            }

    def is_cluster_healthy(self) -> bool:
        healthy = [n for n in self._nodes if n["healthy"]]
        return len(healthy) >= max(1, len(self._nodes) // 2)
