"""
Cluster Model — SQLAlchemy model for HA cluster state.
Tracks current cluster topology: which node is primary,
replication status, and cluster health history.
"""
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Integer
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid
from ..sa_models import Base


class ClusterState(Base):
    """
    Snapshot of cluster state at a point in time.
    Written on every topology change (failover, node addition/removal).
    """
    __tablename__ = "cluster_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    cluster_name = Column(String(200), nullable=False)
    cluster_mode = Column(String(50))       # active_active, active_passive
    primary_node = Column(String(300))
    total_nodes = Column(Integer, default=0)
    healthy_nodes = Column(Integer, default=0)
    nodes = Column(JSON, default=list)      # Full node list snapshot
    is_healthy = Column(Boolean, default=True)
    quorum_met = Column(Boolean, default=True)
    change_reason = Column(String(500))     # What triggered this state change

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recorded_at": self.recorded_at.isoformat(),
            "cluster_name": self.cluster_name,
            "cluster_mode": self.cluster_mode,
            "primary_node": self.primary_node,
            "total_nodes": self.total_nodes,
            "healthy_nodes": self.healthy_nodes,
            "is_healthy": self.is_healthy,
            "quorum_met": self.quorum_met,
        }


__all__ = ["ClusterState"]
