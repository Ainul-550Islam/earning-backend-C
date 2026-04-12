"""
fraud_detection/device_fingerprint_checker.py
───────────────────────────────────────────────
Device fingerprint-based fraud detection.
Identifies device farms, emulators, and shared devices used for fraud.

Detects:
  - Same device fingerprint across multiple user accounts
  - Device fingerprints matching known fraud device databases
  - Emulator signatures in device fingerprint data
  - Abnormal click velocity per device
"""
from __future__ import annotations
import hashlib
import logging
from typing import Tuple, List
from django.utils import timezone
from datetime import timedelta
from ..models import ClickLog, FraudAttemptLog

logger = logging.getLogger(__name__)

# Known emulator/bot device indicators
_EMULATOR_INDICATORS = [
    "generic", "emulator", "sdk_gphone", "android sdk", "goldfish",
    "ranchu", "vbox", "virtual", "genymotion", "bluestacks",
    "nox", "ldplayer", "memu", "gameloop",
]


class DeviceFingerprintChecker:

    def check(
        self,
        fingerprint: str,
        user_agent: str = "",
        device_id: str = "",
        user=None,
    ) -> Tuple[bool, float, List[str]]:
        """
        Full device fingerprint fraud check.
        Returns (is_fraud, score, signals).
        """
        if not fingerprint:
            return False, 0.0, []

        signals = []
        score = 0.0

        # 1. Known emulator check
        emulator_signal = self._check_emulator(user_agent, device_id)
        if emulator_signal:
            signals.append(emulator_signal)
            score = max(score, 85.0)

        # 2. Multiple users on same device
        multi_user_signal = self._check_multi_user(fingerprint)
        if multi_user_signal:
            signals.append(multi_user_signal)
            score = max(score, 75.0)

        # 3. Device velocity (too many clicks in short time)
        velocity_signal = self._check_device_velocity(fingerprint)
        if velocity_signal:
            signals.append(velocity_signal)
            score = max(score, 65.0)

        # 4. Device previously flagged for fraud
        history_signal = self._check_fraud_history(fingerprint)
        if history_signal:
            signals.append(history_signal)
            score = max(score, 90.0)

        is_fraud = score >= 60
        return is_fraud, score, signals

    def _check_emulator(self, user_agent: str, device_id: str) -> str:
        """Check if device appears to be an emulator or virtual device."""
        ua = (user_agent or "").lower()
        did = (device_id or "").lower()
        for indicator in _EMULATOR_INDICATORS:
            if indicator in ua or indicator in did:
                return f"EMULATOR_DETECTED: indicator='{indicator}' in UA/device_id"
        return ""

    def _check_multi_user(self, fingerprint: str) -> str:
        """Check if this fingerprint is shared across multiple user accounts."""
        cutoff = timezone.now() - timedelta(hours=24)
        distinct_users = (
            ClickLog.objects.filter(
                device_fingerprint=fingerprint,
                clicked_at__gte=cutoff,
            )
            .exclude(user=None)
            .values("user_id")
            .distinct()
            .count()
        )
        if distinct_users >= 3:
            return f"SHARED_DEVICE: {distinct_users} different users on same device in 24h"
        return ""

    def _check_device_velocity(self, fingerprint: str) -> str:
        """Check click velocity for this device."""
        cutoff = timezone.now() - timedelta(hours=1)
        count = ClickLog.objects.filter(
            device_fingerprint=fingerprint,
            clicked_at__gte=cutoff,
        ).count()
        if count >= 20:
            return f"DEVICE_VELOCITY: {count} clicks from device in 1h"
        return ""

    def _check_fraud_history(self, fingerprint: str) -> str:
        """Check if this fingerprint was previously involved in fraud."""
        fp_short = fingerprint[:32]
        was_fraud = FraudAttemptLog.objects.filter(
            device_fingerprint__startswith=fp_short
        ).exists()
        if was_fraud:
            return f"FRAUD_HISTORY: device fingerprint previously flagged for fraud"
        return ""

    def generate_fingerprint(
        self,
        ip: str,
        user_agent: str,
        device_id: str = "",
        accept_language: str = "",
    ) -> str:
        """Generate a consistent device fingerprint."""
        raw = f"{ip}|{user_agent}|{device_id}|{accept_language}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


device_fingerprint_checker = DeviceFingerprintChecker()
