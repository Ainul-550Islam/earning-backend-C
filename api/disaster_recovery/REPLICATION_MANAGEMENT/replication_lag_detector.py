"""
Replication Lag Detector — Real-time detection and alerting for replication lag.
Monitors lag against configurable thresholds and escalates alerts.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class ReplicationLagDetector:
    """
    Continuously monitors replication lag between primary and replica databases.
    Features:
    - Multi-level threshold alerting (warning / critical)
    - Trend detection (is lag increasing or decreasing?)
    - Automatic escalation recommendations
    - Historical lag tracking for SLA reporting
    """

    def __init__(self, warning_seconds: float = 30.0,
                  critical_seconds: float = 120.0,
                  emergency_seconds: float = 600.0):
        self.warning_seconds = warning_seconds
        self.critical_seconds = critical_seconds
        self.emergency_seconds = emergency_seconds
        self._lag_history: Dict[str, List[dict]] = {}  # key: "primary->replica"
        self._max_history = 100

    def assess(self, lag_seconds: float,
               primary: str = "primary",
               replica: str = "replica") -> dict:
        """
        Assess the current replication lag and determine alert level.
        Returns assessment dict with level, recommended actions, and trend.
        """
        if lag_seconds >= self.emergency_seconds:
            level = "emergency"
            message = f"EMERGENCY: Replication lag {lag_seconds:.1f}s — IMMEDIATE ACTION REQUIRED"
            actions = [
                "Consider immediate failover",
                "Check network connectivity between primary and replica",
                "Verify replica I/O process is running",
                "Check for long-running transactions on primary",
            ]
        elif lag_seconds >= self.critical_seconds:
            level = "critical"
            message = f"CRITICAL: Replication lag {lag_seconds:.1f}s exceeds {self.critical_seconds}s threshold"
            actions = [
                "Alert on-call team immediately",
                "Monitor for further increase",
                "Prepare for potential failover",
                "Check replica server resources (CPU/IO)",
            ]
        elif lag_seconds >= self.warning_seconds:
            level = "warning"
            message = f"WARNING: Replication lag {lag_seconds:.1f}s exceeds {self.warning_seconds}s threshold"
            actions = [
                "Monitor lag trend closely",
                "Check for heavy write load on primary",
                "Verify replica network bandwidth",
            ]
        else:
            level = "ok"
            message = f"Replication lag {lag_seconds:.1f}s is within acceptable limits"
            actions = []

        # Record for trend analysis
        key = f"{primary}->{replica}"
        if key not in self._lag_history:
            self._lag_history[key] = []
        self._lag_history[key].append({
            "timestamp": datetime.utcnow().isoformat(),
            "lag_seconds": lag_seconds,
            "level": level,
        })
        if len(self._lag_history[key]) > self._max_history:
            self._lag_history[key].pop(0)

        trend = self._calculate_trend(key)
        if level != "ok":
            logger.warning(f"Replication lag alert [{level.upper()}]: {primary}->{replica} = {lag_seconds:.1f}s")

        return {
            "lag_seconds": lag_seconds,
            "level": level,
            "message": message,
            "warning_threshold": self.warning_seconds,
            "critical_threshold": self.critical_seconds,
            "emergency_threshold": self.emergency_seconds,
            "trend": trend,
            "recommended_actions": actions,
            "assessed_at": datetime.utcnow().isoformat(),
        }

    def is_acceptable(self, lag_seconds: float) -> bool:
        """Quick check: is the lag within acceptable bounds?"""
        return lag_seconds < self.warning_seconds

    def is_safe_for_failover(self, lag_seconds: float,
                               max_acceptable_lag: float = None) -> dict:
        """
        Determine if replication lag is low enough for a safe failover.
        Low lag = less data loss (better RPO).
        """
        max_lag = max_acceptable_lag or self.critical_seconds
        safe = lag_seconds <= max_lag
        data_loss_estimate = lag_seconds  # seconds of data potentially lost
        return {
            "safe_for_failover": safe,
            "lag_seconds": lag_seconds,
            "max_acceptable_lag": max_lag,
            "estimated_data_loss_seconds": data_loss_estimate,
            "recommendation": (
                "Safe to failover — minimal data loss expected"
                if safe else
                f"NOT safe to failover — {lag_seconds:.1f}s of data may be lost. "
                f"Wait for lag to drop below {max_lag}s"
            ),
        }

    def get_trend(self, primary: str, replica: str,
                  window_minutes: int = 15) -> dict:
        """Get lag trend for a specific replication pair."""
        key = f"{primary}->{replica}"
        return self._calculate_trend(key, window_minutes)

    def get_all_pairs_status(self) -> List[dict]:
        """Get current status for all monitored replication pairs."""
        statuses = []
        for key, history in self._lag_history.items():
            if not history:
                continue
            latest = history[-1]
            statuses.append({
                "pair": key,
                "latest_lag_seconds": latest["lag_seconds"],
                "latest_level": latest["level"],
                "latest_measured": latest["timestamp"],
                "trend": self._calculate_trend(key),
            })
        return statuses

    def get_lag_statistics(self, primary: str, replica: str) -> dict:
        """Get statistical summary of lag for a pair."""
        key = f"{primary}->{replica}"
        history = self._lag_history.get(key, [])
        if not history:
            return {"pair": key, "samples": 0}
        lags = [h["lag_seconds"] for h in history]
        sorted_lags = sorted(lags)
        n = len(sorted_lags)
        return {
            "pair": key,
            "samples": n,
            "avg_seconds": round(sum(lags) / n, 2),
            "min_seconds": round(sorted_lags[0], 2),
            "max_seconds": round(sorted_lags[-1], 2),
            "p50_seconds": round(sorted_lags[n // 2], 2),
            "p95_seconds": round(sorted_lags[int(n * 0.95)], 2),
            "above_warning_pct": round(
                sum(1 for l in lags if l >= self.warning_seconds) / n * 100, 2
            ),
            "above_critical_pct": round(
                sum(1 for l in lags if l >= self.critical_seconds) / n * 100, 2
            ),
        }

    def _calculate_trend(self, key: str, window_size: int = 10) -> str:
        """Calculate if lag is increasing, decreasing, or stable."""
        history = self._lag_history.get(key, [])
        if len(history) < 3:
            return "insufficient_data"
        recent = [h["lag_seconds"] for h in history[-window_size:]]
        if len(recent) < 3:
            return "stable"
        # Compare first half vs second half average
        mid = len(recent) // 2
        first_half_avg = sum(recent[:mid]) / mid
        second_half_avg = sum(recent[mid:]) / len(recent[mid:])
        change_pct = ((second_half_avg - first_half_avg) / max(first_half_avg, 0.001)) * 100
        if change_pct > 20:
            return "increasing"
        elif change_pct < -20:
            return "decreasing"
        return "stable"
