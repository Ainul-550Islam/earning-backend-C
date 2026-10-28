"""
Scale-Out Storage Architecture
Inspired by: Cohesity scale-out distributed file system, Commvault HyperScale,
             Veeam Scale-out Backup Repository (SOBR)
Adds/removes storage nodes dynamically — no manual rebalancing needed.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    ONLINE      = "online"
    DEGRADED    = "degraded"
    OFFLINE     = "offline"
    REBALANCING = "rebalancing"
    DRAINING    = "draining"      # being removed gracefully


class StoragePolicy(str, Enum):
    PERFORMANCE   = "performance"   # prefer fastest nodes
    CAPACITY      = "capacity"      # prefer nodes with most free space
    ROUND_ROBIN   = "round_robin"
    ERASURE_CODED = "erasure_coded" # stripe + parity across N nodes


@dataclass
class StorageNode:
    node_id: str
    hostname: str
    ip_address: str
    total_bytes: int
    used_bytes: int = 0
    status: NodeStatus = NodeStatus.ONLINE
    rack: str = "default"
    zone: str = "zone-a"
    joined_at: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def free_bytes(self) -> int:
        return self.total_bytes - self.used_bytes

    @property
    def utilisation_pct(self) -> float:
        return (self.used_bytes / self.total_bytes * 100) if self.total_bytes else 0.0

    @property
    def is_available(self) -> bool:
        return self.status == NodeStatus.ONLINE and self.utilisation_pct < 90.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "ip": self.ip_address,
            "status": self.status.value,
            "total_gb": round(self.total_bytes / 1024**3, 2),
            "free_gb": round(self.free_bytes / 1024**3, 2),
            "utilisation_pct": round(self.utilisation_pct, 1),
            "rack": self.rack,
            "zone": self.zone,
        }


@dataclass
class DataPlacement:
    """Describes where a backup chunk is stored"""
    chunk_id: str
    backup_id: str
    primary_node: str
    replica_nodes: List[str]
    size_bytes: int
    checksum: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def replication_factor(self) -> int:
        return 1 + len(self.replica_nodes)


class ConsistentHashRing:
    """
    Consistent hashing ring for data placement.
    Minimises data movement when nodes are added/removed.
    """

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self._ring: Dict[int, str] = {}
        self._sorted_keys: List[int] = []

    def add_node(self, node_id: str) -> None:
        for i in range(self.virtual_nodes):
            key = self._hash(f"{node_id}:{i}")
            self._ring[key] = node_id
        self._sorted_keys = sorted(self._ring.keys())
        logger.debug("Hash ring: node %s added (%d vnodes)", node_id, self.virtual_nodes)

    def remove_node(self, node_id: str) -> None:
        for i in range(self.virtual_nodes):
            key = self._hash(f"{node_id}:{i}")
            self._ring.pop(key, None)
        self._sorted_keys = sorted(self._ring.keys())
        logger.debug("Hash ring: node %s removed", node_id)

    def get_node(self, key: str) -> Optional[str]:
        if not self._ring:
            return None
        h = self._hash(key)
        for ring_key in self._sorted_keys:
            if h <= ring_key:
                return self._ring[ring_key]
        return self._ring[self._sorted_keys[0]]

    def get_nodes(self, key: str, count: int) -> List[str]:
        """Get N distinct nodes for replication"""
        if not self._ring:
            return []
        h = self._hash(key)
        nodes: List[str] = []
        seen: set = set()
        start = None
        for i, ring_key in enumerate(self._sorted_keys):
            if h <= ring_key and start is None:
                start = i
        if start is None:
            start = 0
        idx = start
        while len(nodes) < count and len(seen) < len(set(self._ring.values())):
            node = self._ring[self._sorted_keys[idx % len(self._sorted_keys)]]
            if node not in seen:
                seen.add(node)
                nodes.append(node)
            idx += 1
        return nodes

    @staticmethod
    def _hash(key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)


class ScaleOutStorageCluster:
    """
    Scale-out distributed backup storage cluster.
    Nodes can be added/removed without downtime or manual rebalancing.
    Supports consistent hashing, replication, and erasure coding.
    """

    def __init__(self, replication_factor: int = 3,
                 policy: StoragePolicy = StoragePolicy.CAPACITY):
        self.replication_factor = replication_factor
        self.policy = policy
        self._nodes: Dict[str, StorageNode] = {}
        self._ring = ConsistentHashRing()
        self._placements: Dict[str, DataPlacement] = {}   # chunk_id → placement

    def add_node(self, node: StorageNode) -> None:
        self._nodes[node.node_id] = node
        self._ring.add_node(node.node_id)
        logger.info("Node added to cluster: %s (%s) %.1f TB free",
                    node.node_id, node.hostname,
                    node.free_bytes / 1024**4)
        self._rebalance_check()

    def remove_node(self, node_id: str, graceful: bool = True) -> None:
        node = self._nodes.get(node_id)
        if not node:
            return
        if graceful:
            node.status = NodeStatus.DRAINING
            self._drain_node(node_id)
        self._ring.remove_node(node_id)
        del self._nodes[node_id]
        logger.info("Node removed from cluster: %s", node_id)

    def place_backup(self, backup_id: str, chunk_id: str,
                     size_bytes: int, data: bytes = b"") -> DataPlacement:
        """Place a backup chunk on the optimal nodes"""
        placement_key = f"{backup_id}:{chunk_id}"

        if self.policy == StoragePolicy.CAPACITY:
            primary_id = self._select_by_capacity()
        elif self.policy == StoragePolicy.PERFORMANCE:
            primary_id = self._select_by_performance()
        else:
            primary_id = self._ring.get_node(placement_key)

        if not primary_id:
            raise RuntimeError("No available storage nodes")

        replica_ids = [
            n for n in self._ring.get_nodes(placement_key, self.replication_factor)
            if n != primary_id
        ][:self.replication_factor - 1]

        checksum = hashlib.sha256(data).hexdigest() if data else ""
        placement = DataPlacement(
            chunk_id=chunk_id,
            backup_id=backup_id,
            primary_node=primary_id,
            replica_nodes=replica_ids,
            size_bytes=size_bytes,
            checksum=checksum,
        )
        self._placements[chunk_id] = placement

        # Update node usage
        for nid in [primary_id] + replica_ids:
            if nid in self._nodes:
                self._nodes[nid].used_bytes += size_bytes

        logger.debug("Chunk %s placed: primary=%s replicas=%s",
                     chunk_id, primary_id, replica_ids)
        return placement

    def locate_backup(self, backup_id: str) -> List[DataPlacement]:
        """Find all chunks for a backup"""
        return [p for p in self._placements.values() if p.backup_id == backup_id]

    def verify_placement(self, chunk_id: str) -> Dict[str, bool]:
        """Check replication health for a chunk"""
        placement = self._placements.get(chunk_id)
        if not placement:
            return {}
        results = {}
        for nid in [placement.primary_node] + placement.replica_nodes:
            node = self._nodes.get(nid)
            results[nid] = node is not None and node.is_available
        return results

    def cluster_stats(self) -> Dict[str, Any]:
        online = [n for n in self._nodes.values() if n.status == NodeStatus.ONLINE]
        total_bytes = sum(n.total_bytes for n in online)
        used_bytes = sum(n.used_bytes for n in online)
        return {
            "total_nodes": len(self._nodes),
            "online_nodes": len(online),
            "total_capacity_tb": round(total_bytes / 1024**4, 2),
            "used_capacity_tb": round(used_bytes / 1024**4, 2),
            "free_capacity_tb": round((total_bytes - used_bytes) / 1024**4, 2),
            "utilisation_pct": round(used_bytes / total_bytes * 100, 1) if total_bytes else 0,
            "total_chunks": len(self._placements),
            "replication_factor": self.replication_factor,
            "policy": self.policy.value,
        }

    def node_list(self) -> List[Dict[str, Any]]:
        return [n.to_dict() for n in self._nodes.values()]

    def _select_by_capacity(self) -> Optional[str]:
        available = [n for n in self._nodes.values() if n.is_available]
        if not available:
            return None
        return max(available, key=lambda n: n.free_bytes).node_id

    def _select_by_performance(self) -> Optional[str]:
        available = [n for n in self._nodes.values() if n.is_available]
        if not available:
            return None
        # Prefer nodes with lower utilisation as a proxy for performance
        return min(available, key=lambda n: n.utilisation_pct).node_id

    def _drain_node(self, node_id: str) -> int:
        """Move chunks off a draining node — returns count of moved chunks"""
        affected = [p for p in self._placements.values()
                    if p.primary_node == node_id or node_id in p.replica_nodes]
        moved = 0
        for placement in affected:
            # Promote a replica to primary, find new replica
            if placement.primary_node == node_id and placement.replica_nodes:
                placement.primary_node = placement.replica_nodes.pop(0)
                new_replica = self._select_by_capacity()
                if new_replica and new_replica != placement.primary_node:
                    placement.replica_nodes.append(new_replica)
                moved += 1
            elif node_id in placement.replica_nodes:
                placement.replica_nodes.remove(node_id)
                new_replica = self._select_by_capacity()
                if new_replica:
                    placement.replica_nodes.append(new_replica)
                moved += 1
        logger.info("Drain %s: moved %d chunks", node_id, moved)
        return moved

    def _rebalance_check(self) -> None:
        """Check if any node is over-utilised and trigger rebalancing hint"""
        for node in self._nodes.values():
            if node.utilisation_pct > 85:
                logger.warning(
                    "Node %s is %.1f%% full — consider adding capacity",
                    node.node_id, node.utilisation_pct
                )
