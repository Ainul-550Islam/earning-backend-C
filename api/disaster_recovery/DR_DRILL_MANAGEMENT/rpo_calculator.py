"""
RPO Calculator — Calculates and tracks Recovery Point Objective metrics.
RPO measures how much data (time) can be lost during a disaster.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class RPOCalculator:
    """
    Calculates Recovery Point Objective (RPO) metrics from multiple data sources:
    - Backup completion times vs. failure time
    - Replication lag measurements
    - WAL/binlog timestamps
    - Historical trend analysis
    """

    def __init__(self, target_rpo_seconds: int = 900):
        """
        Args:
            target_rpo_seconds: Target RPO in seconds (default: 15 minutes)
        """
        self.target_rpo_seconds = target_rpo_seconds

    def calculate(self, last_backup_time: datetime,
                   failure_time: datetime) -> float:
        """
        Calculate RPO as the time between last successful backup and failure.
        This is the maximum amount of data that was lost.
        """
        rpo_seconds = (failure_time - last_backup_time).total_seconds()
        logger.info(
            f"RPO calculated: {rpo_seconds:.1f}s "
            f"(last_backup={last_backup_time.isoformat()}, "
            f"failure={failure_time.isoformat()})"
        )
        return max(rpo_seconds, 0.0)

    def calculate_from_replication_lag(self, lag_seconds: float) -> float:
        """
        Calculate effective RPO from current replication lag.
        The lag represents how far behind the replica is — i.e., potential data loss
        if primary fails right now.
        """
        return max(lag_seconds, 0.0)

    def calculate_from_wal_lsn(self, primary_lsn: str, replica_lsn: str,
                                  wal_rate_bytes_per_second: float = 1e6) -> float:
        """
        Calculate RPO from WAL Log Sequence Numbers.
        Converts byte gap to estimated time based on WAL generation rate.
        """
        try:
            # Parse LSN format: "0/3000060" -> integer
            def lsn_to_int(lsn: str) -> int:
                parts = lsn.strip().split("/")
                if len(parts) == 2:
                    return int(parts[0], 16) * (2**32) + int(parts[1], 16)
                return 0
            primary_pos = lsn_to_int(primary_lsn)
            replica_pos = lsn_to_int(replica_lsn)
            byte_gap = max(primary_pos - replica_pos, 0)
            estimated_seconds = byte_gap / max(wal_rate_bytes_per_second, 1)
            return round(estimated_seconds, 2)
        except Exception as e:
            logger.warning(f"LSN RPO calculation failed: {e}")
            return 0.0

    def check_target_met(self, actual_rpo_seconds: float,
                          target_rpo_seconds: int = None) -> dict:
        """Check if actual RPO meets the target."""
        target = target_rpo_seconds or self.target_rpo_seconds
        met = actual_rpo_seconds <= target
        gap = target - actual_rpo_seconds
        data_loss_description = self._describe_data_loss(actual_rpo_seconds)
        if met:
            logger.info(
                f"RPO target MET: actual={actual_rpo_seconds:.1f}s "
                f"target={target}s (ahead by {gap:.1f}s)"
            )
        else:
            logger.warning(
                f"RPO target EXCEEDED: actual={actual_rpo_seconds:.1f}s "
                f"target={target}s (over by {abs(gap):.1f}s)"
            )
        return {
            "rpo_seconds": actual_rpo_seconds,
            "target_seconds": target,
            "met": met,
            "gap_seconds": gap,
            "performance": "ahead" if gap > 0 else "behind",
            "data_loss_description": data_loss_description,
            "checked_at": datetime.utcnow().isoformat(),
        }

    def calculate_historical_average(self, rpo_measurements: List[float]) -> dict:
        """Analyze historical RPO measurements."""
        if not rpo_measurements:
            return {"samples": 0, "avg": None, "min": None, "max": None}
        return {
            "samples": len(rpo_measurements),
            "avg_seconds": round(sum(rpo_measurements) / len(rpo_measurements), 2),
            "min_seconds": round(min(rpo_measurements), 2),
            "max_seconds": round(max(rpo_measurements), 2),
            "p95_seconds": round(sorted(rpo_measurements)[int(len(rpo_measurements) * 0.95)], 2),
            "target_met_count": sum(1 for r in rpo_measurements if r <= self.target_rpo_seconds),
            "compliance_percent": round(
                sum(1 for r in rpo_measurements if r <= self.target_rpo_seconds)
                / len(rpo_measurements) * 100, 2
            ),
        }

    def get_rpo_trend(self, db_session, days: int = 30) -> List[dict]:
        """Fetch RPO trend data from the database."""
        if not db_session:
            return []
        from ..sa_models import RTO_RPO_Metric
        from sqlalchemy import desc
        cutoff = datetime.utcnow() - timedelta(days=days)
        metrics = db_session.query(RTO_RPO_Metric).filter(
            RTO_RPO_Metric.measured_at >= cutoff,
            RTO_RPO_Metric.rpo_actual_seconds.isnot(None)
        ).order_by(RTO_RPO_Metric.measured_at).all()
        return [
            {
                "measured_at": m.measured_at.isoformat(),
                "rpo_seconds": m.rpo_actual_seconds,
                "target_seconds": m.rpo_target_seconds,
                "met": m.rpo_met,
            }
            for m in metrics
        ]

    def _describe_data_loss(self, rpo_seconds: float) -> str:
        """Human-readable description of the data loss window."""
        if rpo_seconds < 60:
            return f"Up to {rpo_seconds:.0f} seconds of data could be lost"
        elif rpo_seconds < 3600:
            return f"Up to {rpo_seconds / 60:.1f} minutes of data could be lost"
        else:
            return f"Up to {rpo_seconds / 3600:.1f} hours of data could be lost"
