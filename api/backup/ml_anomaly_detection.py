"""
ML-Based Anomaly Detection
Inspired by: Rubrik ML anomaly detection, Cohesity GenAI tools, Druva Dru Investigate
Detects abnormal backup patterns using statistical and ML-based methods.
"""

import math
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    SIZE_SPIKE         = "size_spike"          # backup size jumped unexpectedly
    SIZE_DROP          = "size_drop"           # backup size dropped (data loss?)
    DURATION_SPIKE     = "duration_spike"      # took much longer than usual
    FREQUENCY_GAP      = "frequency_gap"       # backup missed scheduled window
    SUCCESS_RATE_DROP  = "success_rate_drop"   # failure rate increased
    ENTROPY_ANOMALY    = "entropy_anomaly"     # entropy suggests encryption
    CHANGE_RATE_SPIKE  = "change_rate_spike"   # data change rate unusually high


class AnomalySeverity(str, Enum):
    INFO     = "info"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyAlert:
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    backup_id: str
    detected_at: datetime = field(default_factory=datetime.utcnow)
    value: float = 0.0          # observed value
    baseline: float = 0.0       # expected value
    deviation_pct: float = 0.0
    description: str = ""
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.anomaly_type.value,
            "severity": self.severity.value,
            "backup_id": self.backup_id,
            "detected_at": self.detected_at.isoformat(),
            "value": self.value,
            "baseline": self.baseline,
            "deviation_pct": round(self.deviation_pct, 2),
            "description": self.description,
        }


@dataclass
class BackupMetricSample:
    """One backup's metrics snapshot for ML analysis"""
    backup_id: str
    timestamp: datetime
    size_bytes: int
    duration_seconds: float
    files_changed: int
    success: bool
    entropy_score: float = 0.0    # 0-8 Shannon entropy
    change_rate_pct: float = 0.0


class BaselineModel:
    """
    Rolling-window statistical baseline model.
    Computes mean and stddev over recent N samples.
    """

    def __init__(self, window: int = 30):
        self.window = window
        self._samples: List[float] = []

    def add(self, value: float) -> None:
        self._samples.append(value)
        if len(self._samples) > self.window:
            self._samples.pop(0)

    def has_baseline(self) -> bool:
        return len(self._samples) >= 5

    def mean(self) -> float:
        return statistics.mean(self._samples) if self._samples else 0.0

    def stddev(self) -> float:
        return statistics.stdev(self._samples) if len(self._samples) >= 2 else 0.0

    def z_score(self, value: float) -> float:
        sd = self.stddev()
        if sd == 0:
            return 0.0
        return (value - self.mean()) / sd

    def deviation_pct(self, value: float) -> float:
        mean = self.mean()
        if mean == 0:
            return 0.0
        return ((value - mean) / mean) * 100


class BackupAnomalyDetector:
    """
    Detects anomalies in backup patterns using rolling statistical baselines.
    Each metric (size, duration, change rate) has its own baseline model.
    """

    # Z-score thresholds for severity classification
    Z_WARN     = 2.0
    Z_HIGH     = 3.0
    Z_CRITICAL = 4.5

    def __init__(self, baseline_window: int = 30):
        self._size_baseline     = BaselineModel(baseline_window)
        self._duration_baseline = BaselineModel(baseline_window)
        self._change_baseline   = BaselineModel(baseline_window)
        self._entropy_baseline  = BaselineModel(baseline_window)
        self._alerts: List[AnomalyAlert] = []

    def ingest(self, sample: BackupMetricSample) -> List[AnomalyAlert]:
        """Process one backup sample and return any anomalies detected"""
        alerts: List[AnomalyAlert] = []

        if self._size_baseline.has_baseline():
            alerts += self._check_size(sample)
            alerts += self._check_duration(sample)
            alerts += self._check_entropy(sample)
            alerts += self._check_change_rate(sample)

        # Always update baselines (only from successful backups for size/duration)
        if sample.success:
            self._size_baseline.add(sample.size_bytes)
            self._duration_baseline.add(sample.duration_seconds)
        self._change_baseline.add(sample.change_rate_pct)
        self._entropy_baseline.add(sample.entropy_score)

        self._alerts.extend(alerts)
        for alert in alerts:
            logger.warning("Anomaly detected: %s [%s] backup=%s dev=%.1f%%",
                           alert.anomaly_type.value, alert.severity.value,
                           sample.backup_id, alert.deviation_pct)
        return alerts

    def _severity_from_z(self, z: float) -> AnomalySeverity:
        z = abs(z)
        if z >= self.Z_CRITICAL:
            return AnomalySeverity.CRITICAL
        if z >= self.Z_HIGH:
            return AnomalySeverity.HIGH
        if z >= self.Z_WARN:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def _check_size(self, s: BackupMetricSample) -> List[AnomalyAlert]:
        z = self._size_baseline.z_score(s.size_bytes)
        alerts = []
        if abs(z) >= self.Z_WARN:
            anomaly_type = AnomalyType.SIZE_SPIKE if z > 0 else AnomalyType.SIZE_DROP
            severity = self._severity_from_z(z)
            dev = self._size_baseline.deviation_pct(s.size_bytes)
            action = (
                "Investigate unexpected data growth — possible ransomware encryption."
                if z > 0 else
                "Investigate data loss — backup is much smaller than baseline."
            )
            alerts.append(AnomalyAlert(
                anomaly_type=anomaly_type,
                severity=severity,
                backup_id=s.backup_id,
                value=s.size_bytes,
                baseline=self._size_baseline.mean(),
                deviation_pct=dev,
                description=f"Backup size {s.size_bytes:,} bytes deviates {dev:+.1f}% from baseline",
                recommended_action=action,
            ))
        return alerts

    def _check_duration(self, s: BackupMetricSample) -> List[AnomalyAlert]:
        z = self._duration_baseline.z_score(s.duration_seconds)
        if z < self.Z_WARN:
            return []
        dev = self._duration_baseline.deviation_pct(s.duration_seconds)
        return [AnomalyAlert(
            anomaly_type=AnomalyType.DURATION_SPIKE,
            severity=self._severity_from_z(z),
            backup_id=s.backup_id,
            value=s.duration_seconds,
            baseline=self._duration_baseline.mean(),
            deviation_pct=dev,
            description=f"Backup took {s.duration_seconds:.0f}s vs baseline {self._duration_baseline.mean():.0f}s",
            recommended_action="Check network throughput and storage I/O performance.",
        )]

    def _check_entropy(self, s: BackupMetricSample) -> List[AnomalyAlert]:
        """High entropy spike may indicate ransomware encrypting data"""
        z = self._entropy_baseline.z_score(s.entropy_score)
        if z < self.Z_HIGH or s.entropy_score < 7.0:
            return []
        dev = self._entropy_baseline.deviation_pct(s.entropy_score)
        return [AnomalyAlert(
            anomaly_type=AnomalyType.ENTROPY_ANOMALY,
            severity=AnomalySeverity.CRITICAL,
            backup_id=s.backup_id,
            value=s.entropy_score,
            baseline=self._entropy_baseline.mean(),
            deviation_pct=dev,
            description=f"Entropy score {s.entropy_score:.2f} is critically high — possible ransomware",
            recommended_action="Immediately quarantine backup. Run ransomware scan before restore.",
        )]

    def _check_change_rate(self, s: BackupMetricSample) -> List[AnomalyAlert]:
        z = self._change_baseline.z_score(s.change_rate_pct)
        if z < self.Z_HIGH:
            return []
        dev = self._change_baseline.deviation_pct(s.change_rate_pct)
        return [AnomalyAlert(
            anomaly_type=AnomalyType.CHANGE_RATE_SPIKE,
            severity=self._severity_from_z(z),
            backup_id=s.backup_id,
            value=s.change_rate_pct,
            baseline=self._change_baseline.mean(),
            deviation_pct=dev,
            description=f"Data change rate {s.change_rate_pct:.1f}% is {dev:+.1f}% above baseline",
            recommended_action="High change rate may indicate bulk file encryption. Investigate immediately.",
        )]

    def get_recent_alerts(self, hours: int = 24) -> List[AnomalyAlert]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [a for a in self._alerts if a.detected_at >= cutoff]

    def get_summary(self) -> Dict[str, Any]:
        alerts_24h = self.get_recent_alerts(24)
        return {
            "total_alerts_24h": len(alerts_24h),
            "critical": sum(1 for a in alerts_24h if a.severity == AnomalySeverity.CRITICAL),
            "high": sum(1 for a in alerts_24h if a.severity == AnomalySeverity.HIGH),
            "size_baseline_mean_gb": round(self._size_baseline.mean() / 1024**3, 2),
            "duration_baseline_mean_min": round(self._duration_baseline.mean() / 60, 1),
            "samples_in_window": len(self._size_baseline._samples),
        }
