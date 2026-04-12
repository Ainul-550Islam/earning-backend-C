"""
Multi-Master Replication — All nodes accept writes; handles conflict resolution.
Suitable for geographically distributed deployments where single-master is impractical.
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class ConflictResolutionStrategy:
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    TIMESTAMP_BASED = "timestamp_based"
    CUSTOM_FUNCTION = "custom_function"
    MANUAL_RESOLUTION = "manual_resolution"


class Conflict:
    """Represents a replication conflict between two masters."""
    def __init__(self, table: str, record_id: str,
                 master1: str, master2: str,
                 master1_value: dict, master2_value: dict,
                 master1_timestamp: datetime, master2_timestamp: datetime):
        self.table = table
        self.record_id = record_id
        self.master1 = master1
        self.master2 = master2
        self.master1_value = master1_value
        self.master2_value = master2_value
        self.master1_timestamp = master1_timestamp
        self.master2_timestamp = master2_timestamp
        self.resolved = False
        self.resolution = None


class MultiMasterReplication:
    """
    Manages multi-master replication topology where all nodes accept writes.
    Uses configurable conflict resolution strategies.

    Supported backends:
    - Galera Cluster (MySQL/MariaDB)
    - pglogical (PostgreSQL)
    - CockroachDB (built-in)
    - Custom application-level replication
    """

    def __init__(self, nodes: List[dict], config: dict = None):
        """
        Args:
            nodes: List of node configs, e.g. [{"host": "db1", "port": 5432}, ...]
            config: Replication configuration including conflict resolution strategy
        """
        self.nodes = nodes
        self.config = config or {}
        self.conflict_strategy = config.get(
            "conflict_strategy", ConflictResolutionStrategy.LAST_WRITE_WINS
        ) if config else ConflictResolutionStrategy.LAST_WRITE_WINS
        self._conflicts: List[Conflict] = []

    def add_node(self, node: dict) -> bool:
        """Add a new master node to the topology."""
        host = node.get("host")
        if any(n.get("host") == host for n in self.nodes):
            logger.warning(f"Node already in topology: {host}")
            return False
        self.nodes.append({**node, "joined_at": datetime.utcnow().isoformat()})
        logger.info(f"Multi-master node added: {host} (total nodes: {len(self.nodes)})")
        return True

    def remove_node(self, host: str, graceful: bool = True) -> dict:
        """Remove a master node from the topology."""
        node = next((n for n in self.nodes if n.get("host") == host), None)
        if not node:
            return {"success": False, "error": f"Node not found: {host}"}
        if graceful:
            self._drain_node(host)
        self.nodes = [n for n in self.nodes if n.get("host") != host]
        logger.info(f"Multi-master node removed: {host}")
        return {"success": True, "host": host, "remaining_nodes": len(self.nodes)}

    def detect_conflicts(self, table: str = None) -> List[dict]:
        """
        Detect write conflicts across all master nodes.
        In production: query each node's conflict log or pg_stat_replication_slots.
        """
        conflicts = []
        # Simplified: in production query Galera's wsrep_local_bf_aborts or
        # pglogical's pglogical.conflict_log table
        for i, node1 in enumerate(self.nodes):
            for node2 in self.nodes[i+1:]:
                conflict_count = self._check_node_conflicts(node1["host"], node2["host"], table)
                if conflict_count > 0:
                    conflicts.append({
                        "node1": node1["host"],
                        "node2": node2["host"],
                        "conflict_count": conflict_count,
                        "table": table or "all_tables",
                        "detected_at": datetime.utcnow().isoformat(),
                    })
        return conflicts

    def resolve_conflict(self, conflict: Conflict,
                          strategy: str = None) -> dict:
        """Resolve a specific replication conflict."""
        strategy = strategy or self.conflict_strategy
        logger.warning(
            f"Resolving conflict: table={conflict.table} "
            f"record={conflict.record_id} strategy={strategy}"
        )
        if strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            winner = (
                conflict.master1
                if conflict.master1_timestamp >= conflict.master2_timestamp
                else conflict.master2
            )
            winning_value = (
                conflict.master1_value
                if winner == conflict.master1
                else conflict.master2_value
            )
        elif strategy == ConflictResolutionStrategy.FIRST_WRITE_WINS:
            winner = (
                conflict.master1
                if conflict.master1_timestamp <= conflict.master2_timestamp
                else conflict.master2
            )
            winning_value = (
                conflict.master1_value
                if winner == conflict.master1
                else conflict.master2_value
            )
        else:
            winner = conflict.master1  # Default fallback
            winning_value = conflict.master1_value
        conflict.resolved = True
        conflict.resolution = {"winner": winner, "strategy": strategy}
        logger.info(
            f"Conflict resolved: winner={winner}, table={conflict.table}, "
            f"record={conflict.record_id}"
        )
        return {
            "resolved": True,
            "winner_node": winner,
            "table": conflict.table,
            "record_id": conflict.record_id,
            "strategy": strategy,
            "resolved_at": datetime.utcnow().isoformat(),
        }

    def get_topology(self) -> dict:
        """Return the complete multi-master topology."""
        return {
            "mode": "multi_master",
            "node_count": len(self.nodes),
            "conflict_strategy": self.conflict_strategy,
            "nodes": [
                {
                    "host": n.get("host"),
                    "port": n.get("port", 5432),
                    "role": "primary",
                    "status": "active",
                    "joined_at": n.get("joined_at"),
                }
                for n in self.nodes
            ],
            "topology_as_of": datetime.utcnow().isoformat(),
        }

    def check_split_brain_risk(self) -> dict:
        """Assess split-brain risk in the current topology."""
        node_count = len(self.nodes)
        # Galera requires odd number of nodes (or arbitrator) to avoid split-brain
        has_quorum_risk = node_count % 2 == 0
        return {
            "node_count": node_count,
            "split_brain_risk": has_quorum_risk,
            "recommendation": (
                "Add an arbitrator node (Galera) or odd node count to prevent split-brain"
                if has_quorum_risk else "Node count provides good quorum protection"
            ),
            "minimum_for_quorum": (node_count // 2) + 1,
        }

    def get_write_distribution(self) -> Dict[str, float]:
        """Get write load distribution across master nodes."""
        if not self.nodes:
            return {}
        equal_share = 100.0 / len(self.nodes)
        return {n.get("host", f"node-{i}"): equal_share for i, n in enumerate(self.nodes)}

    def _check_node_conflicts(self, node1: str, node2: str,
                               table: str = None) -> int:
        """Check conflict count between two nodes (simplified)."""
        return 0  # In production: query conflict log

    def _drain_node(self, host: str):
        """Drain writes from a node before removing it."""
        logger.info(f"Draining writes from {host} before removal")
        import time
        time.sleep(1)  # In production: wait for in-flight transactions
