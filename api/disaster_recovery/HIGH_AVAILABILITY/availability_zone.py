"""
Availability Zone Manager — Multi-AZ placement and failover routing
"""
import logging
import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AZNode:
    node_id: str
    az: str
    region: str
    host: str
    port: int
    healthy: bool = True
    weight: int = 100


class AvailabilityZoneManager:
    """
    Manages multi-AZ deployment topology.
    Ensures workload is distributed across AZs for HA,
    and handles routing when entire AZs go down.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._nodes: List[AZNode] = []
        self._az_status: Dict[str, bool] = {}   # az_name -> is_healthy

    def register_node(self, node_id: str, az: str, region: str,
                      host: str, port: int, weight: int = 100) -> AZNode:
        node = AZNode(node_id=node_id, az=az, region=region,
                      host=host, port=port, weight=weight)
        self._nodes.append(node)
        self._az_status.setdefault(az, True)
        logger.info(f"Registered node {node_id} in AZ={az} region={region}")
        return node

    def mark_az_down(self, az: str):
        """Mark an entire AZ as unavailable."""
        self._az_status[az] = False
        for n in self._nodes:
            if n.az == az:
                n.healthy = False
        logger.critical(f"AZ {az} marked DOWN — {self._count_nodes_in_az(az)} nodes affected")

    def mark_az_healthy(self, az: str):
        self._az_status[az] = True
        for n in self._nodes:
            if n.az == az:
                n.healthy = True
        logger.info(f"AZ {az} marked HEALTHY")

    def _count_nodes_in_az(self, az: str) -> int:
        return sum(1 for n in self._nodes if n.az == az)

    def get_healthy_nodes(self, az: str = None) -> List[AZNode]:
        nodes = [n for n in self._nodes if n.healthy and self._az_status.get(n.az, True)]
        if az:
            nodes = [n for n in nodes if n.az == az]
        return nodes

    def get_nodes_excluding_az(self, excluded_az: str) -> List[AZNode]:
        """Get healthy nodes NOT in the given AZ — for failover routing."""
        return [n for n in self._nodes
                if n.az != excluded_az and n.healthy and self._az_status.get(n.az, True)]

    def get_az_distribution(self) -> Dict[str, dict]:
        """Return node counts per AZ."""
        result = {}
        for az in self._az_status:
            az_nodes = [n for n in self._nodes if n.az == az]
            healthy = [n for n in az_nodes if n.healthy]
            result[az] = {
                "total": len(az_nodes), "healthy": len(healthy),
                "is_up": self._az_status[az],
                "nodes": [n.node_id for n in az_nodes],
            }
        return result

    def select_node_weighted(self, exclude_az: str = None) -> Optional[AZNode]:
        """Select a node using weighted random — respects AZ exclusion."""
        candidates = (
            self.get_nodes_excluding_az(exclude_az)
            if exclude_az else self.get_healthy_nodes()
        )
        if not candidates:
            return None
        total_weight = sum(n.weight for n in candidates)
        if total_weight == 0:
            return random.choice(candidates)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for node in candidates:
            cumulative += node.weight
            if r <= cumulative:
                return node
        return candidates[-1]

    def get_recommended_primary_az(self) -> Optional[str]:
        """Return the AZ with most healthy nodes — ideal for primary placement."""
        dist = self.get_az_distribution()
        healthy_azs = {az: info for az, info in dist.items() if info["is_up"] and info["healthy"] > 0}
        if not healthy_azs:
            return None
        return max(healthy_azs, key=lambda az: healthy_azs[az]["healthy"])

    def validate_multi_az(self) -> dict:
        """Validate that the deployment is truly multi-AZ."""
        healthy_azs = [az for az, up in self._az_status.items() if up]
        is_multi_az = len(healthy_azs) >= 2
        return {
            "is_multi_az": is_multi_az,
            "healthy_az_count": len(healthy_azs),
            "healthy_azs": healthy_azs,
            "recommendation": "OK" if is_multi_az else "WARNING: Deploy to at least 2 AZs for HA",
        }

    def get_status(self) -> dict:
        return {
            "total_nodes": len(self._nodes),
            "healthy_nodes": len(self.get_healthy_nodes()),
            "az_count": len(self._az_status),
            "az_distribution": self.get_az_distribution(),
            "multi_az_valid": self.validate_multi_az(),
        }
