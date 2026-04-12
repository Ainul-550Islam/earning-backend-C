"""
Quorum Manager — Ensures distributed consensus for HA decisions
Uses majority quorum to prevent split-brain scenarios.
"""
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class QuorumManager:
    """
    Implements quorum-based consensus for critical HA decisions:
    - Failover approval
    - Leader election
    - Configuration changes

    Quorum = floor(N/2) + 1 nodes must agree for an action to proceed.
    This prevents split-brain in network partitions.
    """

    def __init__(self, nodes: List[str], config: dict = None):
        """
        nodes: list of node IDs participating in quorum
        """
        self.config = config or {}
        self._nodes: Set[str] = set(nodes)
        self._votes: Dict[str, Dict[str, bool]] = {}  # proposal_id -> {node_id: vote}
        self._leader: Optional[str] = None
        self._lock = threading.Lock()
        self._epoch: int = 0   # Increments on every leader change

    # ── Quorum math ───────────────────────────────────────────────────────────

    @property
    def quorum_size(self) -> int:
        """Minimum votes needed for a quorum decision."""
        return len(self._nodes) // 2 + 1

    def has_quorum(self, participating_nodes: List[str]) -> bool:
        """Check if a set of nodes constitutes quorum."""
        active = set(participating_nodes) & self._nodes
        result = len(active) >= self.quorum_size
        logger.debug(f"Quorum check: {len(active)}/{len(self._nodes)} nodes, need {self.quorum_size} → {'YES' if result else 'NO'}")
        return result

    # ── Voting ────────────────────────────────────────────────────────────────

    def propose(self, proposal_id: str, proposer: str) -> str:
        """Start a new proposal that requires quorum approval."""
        with self._lock:
            self._votes[proposal_id] = {}
            logger.info(f"Proposal started: {proposal_id} by {proposer} (need {self.quorum_size} votes)")
        return proposal_id

    def vote(self, proposal_id: str, node_id: str, approve: bool) -> dict:
        """Cast a vote for a proposal."""
        with self._lock:
            if proposal_id not in self._votes:
                return {"error": "Unknown proposal"}
            if node_id not in self._nodes:
                return {"error": f"Node {node_id} not in quorum"}
            self._votes[proposal_id][node_id] = approve
            yes_votes = sum(1 for v in self._votes[proposal_id].values() if v)
            no_votes = sum(1 for v in self._votes[proposal_id].values() if not v)
            quorum_reached = yes_votes >= self.quorum_size
            rejected = no_votes >= self.quorum_size
            result = {
                "proposal_id": proposal_id,
                "yes_votes": yes_votes,
                "no_votes": no_votes,
                "quorum_size": self.quorum_size,
                "quorum_reached": quorum_reached,
                "rejected": rejected,
                "total_votes": len(self._votes[proposal_id]),
            }
            if quorum_reached:
                logger.info(f"Proposal {proposal_id} APPROVED ({yes_votes}/{self.quorum_size} votes)")
            elif rejected:
                logger.warning(f"Proposal {proposal_id} REJECTED ({no_votes} no-votes)")
            return result

    def get_proposal_status(self, proposal_id: str) -> dict:
        with self._lock:
            if proposal_id not in self._votes:
                return {"error": "Unknown proposal"}
            votes = self._votes[proposal_id]
            yes = sum(1 for v in votes.values() if v)
            no = sum(1 for v in votes.values() if not v)
            pending = len(self._nodes) - len(votes)
            return {"proposal_id": proposal_id, "yes": yes, "no": no,
                    "pending": pending, "quorum_size": self.quorum_size,
                    "approved": yes >= self.quorum_size, "rejected": no >= self.quorum_size}

    # ── Leader election ───────────────────────────────────────────────────────

    def elect_leader(self, candidates: List[str]) -> Optional[str]:
        """
        Simple leader election: highest-priority healthy candidate with quorum support.
        Returns the elected leader node_id, or None if no quorum.
        """
        valid_candidates = [c for c in candidates if c in self._nodes]
        if not valid_candidates:
            logger.error("No valid candidates for leader election")
            return None
        if not self.has_quorum(valid_candidates):
            logger.error(f"Insufficient nodes for leader election: {len(valid_candidates)} < {self.quorum_size}")
            return None
        # Select the first candidate (priority-ordered list assumed)
        elected = valid_candidates[0]
        with self._lock:
            self._leader = elected
            self._epoch += 1
        logger.warning(f"Leader elected: {elected} (epoch={self._epoch})")
        return elected

    def get_leader(self) -> Optional[str]:
        return self._leader

    def get_epoch(self) -> int:
        return self._epoch

    def add_node(self, node_id: str):
        with self._lock:
            self._nodes.add(node_id)
        logger.info(f"Node added to quorum: {node_id} (new size={len(self._nodes)})")

    def remove_node(self, node_id: str):
        with self._lock:
            self._nodes.discard(node_id)
            if self._leader == node_id:
                self._leader = None
                logger.warning(f"Leader {node_id} removed from quorum — re-election needed")
        logger.info(f"Node removed from quorum: {node_id} (new size={len(self._nodes)})")

    def get_status(self) -> dict:
        with self._lock:
            return {
                "nodes": list(self._nodes),
                "quorum_size": self.quorum_size,
                "leader": self._leader,
                "epoch": self._epoch,
                "active_proposals": len(self._votes),
            }
