"""
Node Manager — Manages individual cluster nodes (add, remove, drain, health tracking)
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NodeInfo:
    node_id: str
    host: str
    port: int
    role: str = "worker"          # primary, replica, worker, coordinator
    status: str = "unknown"       # healthy, degraded, draining, offline
    weight: int = 100
    added_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def is_healthy(self) -> bool:
        if self.status not in ("healthy", "degraded"):
            return False
        if self.last_seen is None:
            return False
        return (datetime.utcnow() - self.last_seen).total_seconds() < 60

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "role": self.role,
            "status": self.status,
            "weight": self.weight,
            "added_at": self.added_at.isoformat(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_healthy": self.is_healthy(),
            "metadata": self.metadata,
        }


class NodeManager:
    """
    Manages the lifecycle of all cluster nodes.
    Tracks health, handles graceful draining before removal,
    and provides node discovery for load balancers.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._nodes: Dict[str, NodeInfo] = {}
        self._lock = threading.RLock()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_node(self, node_id: str, host: str, port: int,
                 role: str = "worker", weight: int = 100, metadata: dict = None) -> NodeInfo:
        """Register a new node in the cluster."""
        with self._lock:
            if node_id in self._nodes:
                logger.warning(f"Node {node_id} already registered — updating")
            node = NodeInfo(
                node_id=node_id, host=host, port=port,
                role=role, weight=weight, metadata=metadata or {}
            )
            self._nodes[node_id] = node
            logger.info(f"Node added: {node_id} ({host}:{port}) role={role}")
            return node

    def remove_node(self, node_id: str, force: bool = False) -> bool:
        """Remove a node — drains first unless force=True."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                logger.warning(f"Node not found: {node_id}")
                return False
            if not force and node.status not in ("offline", "draining"):
                self.drain_node(node_id)
            del self._nodes[node_id]
            logger.info(f"Node removed: {node_id}")
            return True

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        return self._nodes.get(node_id)

    def list_nodes(self, role: str = None, status: str = None) -> List[NodeInfo]:
        with self._lock:
            nodes = list(self._nodes.values())
            if role:
                nodes = [n for n in nodes if n.role == role]
            if status:
                nodes = [n for n in nodes if n.status == status]
            return nodes

    # ── Status management ─────────────────────────────────────────────────────

    def update_status(self, node_id: str, status: str, last_seen: datetime = None) -> bool:
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            old_status = node.status
            node.status = status
            node.last_seen = last_seen or datetime.utcnow()
            if old_status != status:
                logger.info(f"Node {node_id} status: {old_status} -> {status}")
            return True

    def heartbeat(self, node_id: str) -> bool:
        """Record a heartbeat from a node."""
        return self.update_status(node_id, "healthy", datetime.utcnow())

    def drain_node(self, node_id: str) -> bool:
        """
        Mark node as draining — stops new connections but allows
        existing ones to finish. Used before maintenance or removal.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            node.status = "draining"
            node.weight = 0       # Remove from load balancing rotation
            logger.info(f"Node {node_id} is draining (weight set to 0)")
            return True

    def promote_node(self, node_id: str, new_role: str = "primary") -> bool:
        """Promote a node to a new role (e.g., replica -> primary during failover)."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            old_role = node.role
            node.role = new_role
            logger.warning(f"Node {node_id} promoted: {old_role} -> {new_role}")
            return True

    def set_weight(self, node_id: str, weight: int) -> bool:
        """Adjust node weight for load balancing (0 = remove from rotation)."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            node.weight = max(0, min(1000, weight))
            logger.info(f"Node {node_id} weight set to {node.weight}")
            return True

    # ── Querying ──────────────────────────────────────────────────────────────

    def get_primary(self) -> Optional[NodeInfo]:
        """Return the current primary node."""
        primaries = self.list_nodes(role="primary", status="healthy")
        return primaries[0] if primaries else None

    def get_healthy_nodes(self) -> List[NodeInfo]:
        """Return all nodes currently healthy and in rotation."""
        with self._lock:
            return [n for n in self._nodes.values() if n.is_healthy() and n.weight > 0]

    def get_offline_nodes(self) -> List[NodeInfo]:
        """Return nodes that appear to be offline."""
        cutoff = datetime.utcnow() - timedelta(seconds=60)
        with self._lock:
            return [
                n for n in self._nodes.values()
                if n.last_seen is None or n.last_seen < cutoff
            ]

    def get_cluster_summary(self) -> dict:
        """Return a summary of the cluster state."""
        with self._lock:
            all_nodes = list(self._nodes.values())
            healthy = [n for n in all_nodes if n.is_healthy()]
            return {
                "total_nodes": len(all_nodes),
                "healthy_nodes": len(healthy),
                "draining_nodes": len([n for n in all_nodes if n.status == "draining"]),
                "offline_nodes": len([n for n in all_nodes if not n.is_healthy()]),
                "primary": self.get_primary().node_id if self.get_primary() else None,
                "nodes": [n.to_dict() for n in all_nodes],
            }
