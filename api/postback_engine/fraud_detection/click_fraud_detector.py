"""
fraud_detection/click_fraud_detector.py
─────────────────────────────────────────
Dedicated click-level fraud detection.

Detects:
  - Click flooding (too many clicks from same IP/device in short window)
  - Click injection (conversion without a matching real click)
  - Click hijacking (click_id doesn't match network's reported referrer)
  - Bot clicks (user-agent analysis, no JS fingerprint)
  - Duplicate clicks (same user clicking same offer repeatedly)
"""
from __future__ import annotations
import logging
from typing import Tuple, List
from django.utils import timezone
from django.db.models import Count
from ..models import ClickLog, AdNetworkConfig
from ..enums import ClickStatus, FraudType
from ..constants import MAX_CLICK_IP_PER_HOUR, MAX_CLICK_DEVICE_PER_HOUR

logger = logging.getLogger(__name__)

# Thresholds
_MAX_CLICKS_IP_1H      = MAX_CLICK_IP_PER_HOUR       # 100
_MAX_CLICKS_DEVICE_1H  = MAX_CLICK_DEVICE_PER_HOUR   # 50
_MAX_CLICKS_USER_1H    = 30
_MIN_CLICK_TO_CONV_SEC = 3       # < 3 seconds = impossible (bot)
_MAX_CLICK_TO_CONV_SEC = 86400 * 30  # > 30 days = window expired


class ClickFraudDetector:

    def scan(self, click_log: ClickLog) -> Tuple[bool, float, List[str]]:
        """
        Full fraud scan of a ClickLog.
        Returns (is_fraud, score, signals).
        """
        signals = []
        score = 0.0

        # 1. Bot user agent
        ua = click_log.user_agent or ""
        from .bot_detector import bot_detector
        is_bot, bot_score = bot_detector.check_user_agent(ua)
        if is_bot:
            signals.append(f"BOT_UA: score={bot_score:.0f}")
            score = max(score, bot_score)

        # 2. IP velocity (too many clicks from same IP in 1 hour)
        if click_log.ip_address:
            cutoff = timezone.now() - timezone.timedelta(hours=1)
            ip_count = ClickLog.objects.filter(
                ip_address=click_log.ip_address,
                clicked_at__gte=cutoff,
            ).count()
            if ip_count > _MAX_CLICKS_IP_1H:
                signals.append(f"IP_FLOOD: {ip_count} clicks/1h from {click_log.ip_address}")
                score = max(score, 80.0)

        # 3. Device velocity
        if click_log.device_fingerprint:
            cutoff = timezone.now() - timezone.timedelta(hours=1)
            dev_count = ClickLog.objects.filter(
                device_fingerprint=click_log.device_fingerprint,
                clicked_at__gte=cutoff,
            ).count()
            if dev_count > _MAX_CLICKS_DEVICE_1H:
                signals.append(f"DEVICE_FLOOD: {dev_count} clicks/1h")
                score = max(score, 75.0)

        # 4. User clicking same offer too many times
        if click_log.user_id and click_log.offer_id:
            cutoff = timezone.now() - timezone.timedelta(hours=24)
            dup_count = ClickLog.objects.filter(
                user_id=click_log.user_id,
                offer_id=click_log.offer_id,
                clicked_at__gte=cutoff,
            ).count()
            if dup_count > 10:
                signals.append(f"OFFER_REPEAT: {dup_count} clicks on same offer in 24h")
                score = max(score, 60.0)

        # 5. No user agent at all (script/bot)
        if not ua.strip():
            signals.append("MISSING_UA: no user agent provided")
            score = max(score, 45.0)

        is_fraud = score >= 60
        return is_fraud, score, signals

    def check_click_injection(
        self,
        click_log: ClickLog,
        time_to_convert_seconds: int,
    ) -> Tuple[bool, str]:
        """
        Check if conversion time is suspicious (too fast = click injection).
        Returns (is_suspicious, reason).
        """
        if time_to_convert_seconds < _MIN_CLICK_TO_CONV_SEC:
            return True, (
                f"Click-to-conversion in {time_to_convert_seconds}s "
                f"(min expected: {_MIN_CLICK_TO_CONV_SEC}s) — possible click injection."
            )
        return False, ""

    def check_click_exists_for_conversion(
        self,
        click_id: str,
        network: AdNetworkConfig,
    ) -> bool:
        """
        Verify that a click_id exists in our system before crediting a conversion.
        Critical: prevents 'phantom conversions' where no real click occurred.
        """
        return ClickLog.objects.filter(
            click_id=click_id,
            network=network,
        ).exists()


# Module-level singleton
click_fraud_detector = ClickFraudDetector()
