"""
Capacity Planner — Forecasts infrastructure needs for DR system
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CapacityPlanner:
    """
    Analyzes historical usage trends and recommends infrastructure
    scaling actions before capacity limits are hit.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._history: List[dict] = []

    def record_metrics(self, metrics: dict):
        """Record a metrics snapshot for trend analysis."""
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            **metrics
        }
        self._history.append(snapshot)
        # Keep last 30 days of data (assuming hourly snapshots)
        max_records = 30 * 24
        if len(self._history) > max_records:
            self._history = self._history[-max_records:]

    def analyze_storage_growth(self, days_to_project: int = 30) -> dict:
        """Project storage usage N days into the future."""
        if len(self._history) < 2:
            return {"error": "Insufficient history for projection"}
        storage_values = [
            s.get("backup_storage_used_gb", 0)
            for s in self._history
            if "backup_storage_used_gb" in s
        ]
        if len(storage_values) < 2:
            return {"error": "No storage metrics in history"}
        # Linear regression (simple)
        n = len(storage_values)
        growth_per_snapshot = (storage_values[-1] - storage_values[0]) / max(n - 1, 1)
        # Determine snapshots per day (from config or default 24 for hourly)
        snapshots_per_day = self.config.get("metrics_per_day", 24)
        growth_per_day_gb = growth_per_snapshot * snapshots_per_day
        projected_gb = storage_values[-1] + (growth_per_day_gb * days_to_project)
        return {
            "current_storage_gb": round(storage_values[-1], 2),
            "growth_per_day_gb": round(growth_per_day_gb, 3),
            "projected_gb_in_{}_days".format(days_to_project): round(projected_gb, 2),
            "days_projected": days_to_project,
            "recommendation": self._storage_recommendation(projected_gb),
        }

    def _storage_recommendation(self, projected_gb: float) -> str:
        capacity_gb = self.config.get("total_storage_gb", 10240)
        pct = projected_gb / capacity_gb * 100
        if pct > 90:
            return f"CRITICAL: Projected to use {pct:.1f}% of capacity — expand storage immediately"
        elif pct > 75:
            return f"WARNING: Projected to use {pct:.1f}% of capacity — plan expansion"
        return f"OK: Projected to use {pct:.1f}% of capacity"

    def analyze_cpu_trend(self, window_hours: int = 24) -> dict:
        """Analyze CPU usage trend and recommend scaling."""
        recent = self._history[-window_hours:] if len(self._history) >= window_hours else self._history
        cpu_values = [s.get("cpu_percent", 0) for s in recent if "cpu_percent" in s]
        if not cpu_values:
            return {"error": "No CPU metrics"}
        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_cpu = max(cpu_values)
        p95_cpu = sorted(cpu_values)[int(len(cpu_values) * 0.95)]
        recommendation = "OK"
        if p95_cpu > 80:
            recommendation = f"Scale out: P95 CPU at {p95_cpu:.1f}% — add more nodes"
        elif avg_cpu < 20 and len(cpu_values) > 12:
            recommendation = f"Scale in: avg CPU only {avg_cpu:.1f}% — reduce nodes to save cost"
        return {
            "window_hours": window_hours,
            "avg_cpu_percent": round(avg_cpu, 2),
            "max_cpu_percent": round(max_cpu, 2),
            "p95_cpu_percent": round(p95_cpu, 2),
            "recommendation": recommendation,
        }

    def recommend_backup_storage(self, current_db_size_gb: float,
                                  retention_days: int = 30,
                                  compression_ratio: float = 0.4) -> dict:
        """Calculate how much backup storage is needed."""
        daily_full_gb = current_db_size_gb * compression_ratio
        daily_incremental_gb = daily_full_gb * 0.1     # ~10% of full
        # GFS retention: 1 full/week + 6 incrementals + monthly fulls
        weekly_storage = daily_full_gb + (6 * daily_incremental_gb)
        total_weeks = retention_days / 7
        total_storage_gb = weekly_storage * total_weeks
        # Add 30% buffer
        recommended_gb = total_storage_gb * 1.3
        return {
            "current_db_size_gb": current_db_size_gb,
            "compression_ratio": compression_ratio,
            "retention_days": retention_days,
            "estimated_storage_needed_gb": round(total_storage_gb, 2),
            "recommended_storage_gb": round(recommended_gb, 2),
            "breakdown": {
                "daily_full_backup_gb": round(daily_full_gb, 2),
                "daily_incremental_gb": round(daily_incremental_gb, 2),
                "weekly_storage_gb": round(weekly_storage, 2),
            }
        }

    def get_scaling_recommendations(self) -> List[dict]:
        """Return all current scaling recommendations."""
        recommendations = []
        storage = self.analyze_storage_growth()
        if "recommendation" in storage and "WARNING" in storage.get("recommendation", ""):
            recommendations.append({"type": "storage", "priority": "high", **storage})
        cpu = self.analyze_cpu_trend()
        if "Scale" in cpu.get("recommendation", ""):
            recommendations.append({"type": "compute", "priority": "medium", **cpu})
        return recommendations
