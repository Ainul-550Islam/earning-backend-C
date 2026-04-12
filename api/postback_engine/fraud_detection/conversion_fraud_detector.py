"""
fraud_detection/conversion_fraud_detector.py
──────────────────────────────────────────────
Conversion-level fraud detection.
Runs after a postback is received but before the conversion is created.
Detects: payout manipulation, offer farming, multi-account abuse, geo fraud.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Tuple, List
from django.utils import timezone
from datetime import timedelta
from ..models import Conversion, AdNetworkConfig, PostbackRawLog
from ..enums import ConversionStatus, FraudType

logger = logging.getLogger(__name__)


class ConversionFraudDetector:

    def scan(
        self,
        raw_log: PostbackRawLog,
        user=None,
        network: AdNetworkConfig = None,
    ) -> Tuple[bool, float, List[str]]:
        """
        Full fraud scan on a postback before conversion creation.
        Returns (is_fraud, score, signals).
        """
        signals = []
        score = 0.0

        # 1. Payout manipulation check
        payout_signal = self._check_payout(raw_log, network)
        if payout_signal:
            signals.append(payout_signal)
            score = max(score, 70.0)

        # 2. Offer farming (user converting same offer repeatedly)
        if user and raw_log.offer_id:
            farm_signal = self._check_offer_farming(user, raw_log.offer_id)
            if farm_signal:
                signals.append(farm_signal)
                score = max(score, 65.0)

        # 3. Multi-account (same IP, different users, same offer)
        if raw_log.source_ip and raw_log.offer_id:
            multi_signal = self._check_multi_account(raw_log.source_ip, raw_log.offer_id)
            if multi_signal:
                signals.append(multi_signal)
                score = max(score, 75.0)

        # 4. Abnormally high payout (network error or injection)
        if raw_log.payout > Decimal("50"):
            signals.append(f"HIGH_PAYOUT: {raw_log.payout} USD — exceeds expected range")
            score = max(score, 50.0)

        # 5. Zero payout with reward rules (network error)
        if raw_log.payout == 0 and network and network.default_reward_points > 0:
            signals.append("ZERO_PAYOUT: network reports $0 but reward rules exist")
            score = max(score, 30.0)

        is_fraud = score >= 60
        return is_fraud, score, signals

    def _check_payout(self, raw_log: PostbackRawLog, network: AdNetworkConfig) -> str:
        """Check if payout is within expected range for this offer."""
        if not network or raw_log.payout <= 0:
            return ""
        expected = network.get_reward_for_offer(raw_log.offer_id)
        expected_usd = Decimal(str(expected.get("usd", 0)))
        if expected_usd > 0 and raw_log.payout > expected_usd * Decimal("3"):
            return (
                f"PAYOUT_INFLATED: received {raw_log.payout} USD, "
                f"expected ≤ {expected_usd * 3} USD for offer {raw_log.offer_id}"
            )
        return ""

    def _check_offer_farming(self, user, offer_id: str) -> str:
        """Check if user has converted same offer too many times recently."""
        cutoff = timezone.now() - timedelta(hours=24)
        count = Conversion.objects.filter(
            user=user,
            offer_id=offer_id,
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        ).count()
        if count >= 3:
            return f"OFFER_FARMING: user has {count} conversions for offer {offer_id} in 24h"
        return ""

    def _check_multi_account(self, ip: str, offer_id: str) -> str:
        """Check if multiple different users converted from same IP for same offer."""
        cutoff = timezone.now() - timedelta(hours=24)
        distinct_users = (
            Conversion.objects.filter(
                source_ip=ip,
                offer_id=offer_id,
                converted_at__gte=cutoff,
            )
            .values("user_id")
            .distinct()
            .count()
        )
        if distinct_users >= 3:
            return f"MULTI_ACCOUNT: {distinct_users} different users converted from IP {ip} for offer {offer_id} in 24h"
        return ""


conversion_fraud_detector = ConversionFraudDetector()
