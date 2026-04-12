"""
fraud_detection/time_anomaly_detector.py
──────────────────────────────────────────
Time-based anomaly detection for postback fraud.

Detects:
  - Click-to-conversion time too short (bot/injection)
  - Conversions clustering at exact same timestamps (scripted)
  - Off-hours traffic spikes (bot-driven batch processing)
  - Timestamp manipulation (future or past timestamps)
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Tuple, List, Optional
from django.utils import timezone
from ..models import PostbackRawLog, ClickLog

logger = logging.getLogger(__name__)

# Thresholds
_MIN_CLICK_TO_CONV_SECONDS = 3       # < 3s = almost certainly injection
_SUSPICIOUS_FAST_SECONDS   = 30      # < 30s = suspicious
_MAX_FUTURE_SECONDS        = 60      # Allow 60s clock skew
_MAX_PAST_SECONDS          = 86400   # 24h in the past = suspicious
_BURST_WINDOW_SECONDS      = 60      # Window for burst detection
_BURST_THRESHOLD           = 10      # N postbacks in window = burst


class TimeAnomalyDetector:

    def check_click_to_conversion(
        self,
        click_log: ClickLog,
        conversion_time: datetime = None,
    ) -> Tuple[bool, float, str]:
        """
        Check if click-to-conversion time is suspicious.
        Returns (is_suspicious, score, signal).
        """
        conv_time = conversion_time or timezone.now()
        delta_seconds = int((conv_time - click_log.clicked_at).total_seconds())

        if delta_seconds < _MIN_CLICK_TO_CONV_SECONDS:
            return True, 95.0, (
                f"IMPOSSIBLE_TIMING: conversion {delta_seconds}s after click "
                f"(min: {_MIN_CLICK_TO_CONV_SECONDS}s) — click injection detected"
            )
        if delta_seconds < _SUSPICIOUS_FAST_SECONDS:
            return True, 55.0, (
                f"FAST_CONVERSION: {delta_seconds}s after click — suspiciously fast"
            )
        return False, 0.0, ""

    def check_timestamp_validity(self, timestamp_str: str) -> Tuple[bool, str]:
        """
        Validate that a postback timestamp is not manipulated.
        Returns (is_valid, reason).
        """
        try:
            ts = float(timestamp_str)
            ts_time = datetime.fromtimestamp(ts, tz=timezone.utc)
            now = timezone.now()

            future_diff = (ts_time - now).total_seconds()
            past_diff = (now - ts_time).total_seconds()

            if future_diff > _MAX_FUTURE_SECONDS:
                return False, f"FUTURE_TIMESTAMP: {future_diff:.0f}s in the future"
            if past_diff > _MAX_PAST_SECONDS:
                return False, f"OLD_TIMESTAMP: {past_diff / 3600:.1f}h old"
            return True, ""
        except (ValueError, TypeError, OSError):
            return False, "INVALID_TIMESTAMP: cannot parse timestamp"

    def check_burst(
        self,
        network,
        window_seconds: int = _BURST_WINDOW_SECONDS,
        threshold: int = _BURST_THRESHOLD,
    ) -> Tuple[bool, str]:
        """
        Check if there is a burst of postbacks within a short window.
        Returns (is_burst, signal).
        """
        cutoff = timezone.now() - timedelta(seconds=window_seconds)
        count = PostbackRawLog.objects.filter(
            network=network,
            received_at__gte=cutoff,
        ).count()
        if count >= threshold:
            return True, (
                f"POSTBACK_BURST: {count} postbacks in {window_seconds}s "
                f"(threshold: {threshold})"
            )
        return False, ""

    def check_clustering(
        self,
        network,
        window_seconds: int = 5,
        min_cluster_size: int = 5,
    ) -> Tuple[bool, str]:
        """
        Check if postbacks are clustering at exact same timestamp (scripted batch).
        """
        cutoff = timezone.now() - timedelta(minutes=10)
        from django.db.models import Count
        from django.db.models.functions import TruncSecond
        clusters = (
            PostbackRawLog.objects.filter(
                network=network,
                received_at__gte=cutoff,
            )
            .annotate(second=TruncSecond("received_at"))
            .values("second")
            .annotate(count=Count("id"))
            .filter(count__gte=min_cluster_size)
        )
        if clusters.exists():
            max_cluster = max(c["count"] for c in clusters)
            return True, f"TIMESTAMP_CLUSTERING: {max_cluster} postbacks at exact same second"
        return False, ""

    def is_off_hours_spike(self, network, spike_multiplier: float = 5.0) -> bool:
        """
        Check if current hour has unusual traffic vs same hour on previous days.
        """
        now = timezone.now()
        current_hour = now.hour
        cutoff_now = now - timedelta(hours=1)

        current_count = PostbackRawLog.objects.filter(
            network=network,
            received_at__gte=cutoff_now,
        ).count()

        # Average count for this hour over last 7 days
        daily_avgs = []
        for days_back in range(1, 8):
            day_cutoff = now - timedelta(days=days_back)
            hour_start = day_cutoff.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            cnt = PostbackRawLog.objects.filter(
                network=network,
                received_at__gte=hour_start,
                received_at__lt=hour_end,
            ).count()
            daily_avgs.append(cnt)

        avg = sum(daily_avgs) / len(daily_avgs) if daily_avgs else 0
        if avg > 0 and current_count > avg * spike_multiplier:
            logger.warning(
                "Off-hours spike: network=%s hour=%d current=%d avg=%.1f",
                network.network_key, current_hour, current_count, avg,
            )
            return True
        return False


time_anomaly_detector = TimeAnomalyDetector()
