"""
fraud_detection/fraud_scoring.py
─────────────────────────────────
Composite fraud score calculator.
Aggregates signals from all detectors into a single 0-100 score.

Score tiers:
  0-39  → Clean (allow)
  40-59 → Suspicious (allow but flag for review)
  60-79 → High risk (flag + log FraudAttemptLog)
  80-100 → Block (reject + auto-blacklist if ≥ 90)
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FraudSignal:
    name: str
    score: float          # Contribution to total score (0-100)
    weight: float = 1.0   # Multiplier (signals with weight > 1 are more important)
    description: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        return min(self.score * self.weight, 100.0)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "weight": self.weight,
            "description": self.description,
            "evidence": self.evidence,
        }


class FraudScoreCalculator:
    """
    Composite fraud score = weighted average of all signals, capped at 100.
    Signals with weight=2 count double (e.g. blacklisted IP is very definitive).
    """

    # Maximum single-signal score that can result in auto-block
    AUTO_BLOCK_THRESHOLD = 90.0
    # If any individual signal is above this, immediately return that score
    INSTANT_BLOCK_SCORE = 100.0

    def calculate(
        self,
        ip: str = "",
        user_agent: str = "",
        headers: dict = None,
        device_fingerprint: str = "",
        user=None,
        network=None,
        time_to_convert_seconds: Optional[int] = None,
        raw_log=None,
    ) -> tuple:
        """
        Run all fraud signal detectors and return (score, signals).
        """
        signals: List[FraudSignal] = []
        headers = headers or {}

        # 1. Blacklisted IP (weight=2 — very high confidence)
        if ip:
            from .ip_blacklist_checker import ip_blacklist_checker
            is_bl, _ = ip_blacklist_checker.is_blacklisted(ip)
            if is_bl:
                signals.append(FraudSignal(
                    name="blacklisted_ip", score=100.0, weight=2.0,
                    description=f"IP {ip} is blacklisted.",
                ))

        # 2. Bot user-agent
        if user_agent:
            from .bot_detector import bot_detector
            is_bot, bot_score = bot_detector.check_user_agent(user_agent)
            if bot_score > 0:
                signals.append(FraudSignal(
                    name="bot_ua", score=bot_score, weight=1.5,
                    description=f"Bot UA detected (score={bot_score:.0f})",
                ))

        # 3. Suspicious headers (missing Accept, Accept-Language)
        if headers:
            from .bot_detector import bot_detector
            is_bot, hdr_score = bot_detector.check_headers(headers)
            if hdr_score > 0:
                signals.append(FraudSignal(
                    name="suspicious_headers", score=hdr_score, weight=1.0,
                    description=f"Missing browser headers (score={hdr_score:.0f})",
                ))

        # 4. Proxy / VPN / Tor
        if ip:
            from .proxy_detector import proxy_detector
            is_proxy, proxy_reason = proxy_detector.check(ip)
            if is_proxy:
                signals.append(FraudSignal(
                    name="proxy_vpn", score=65.0, weight=1.2,
                    description=proxy_reason or "VPN/Proxy detected",
                ))

        # 5. Velocity check (IP, user, device)
        from .velocity_checker import velocity_checker
        try:
            vel_result = velocity_checker.check(
                ip=ip, user=user, network=network,
                device_fingerprint=device_fingerprint,
            )
            for violation in vel_result.violations:
                signals.append(FraudSignal(
                    name="velocity", score=70.0 if vel_result.blocked else 45.0,
                    weight=1.0, description=violation,
                ))
        except Exception:
            pass   # VelocityLimitException is handled by the pipeline

        # 6. Click timing (too fast = bot)
        if time_to_convert_seconds is not None:
            from .bot_detector import bot_detector
            is_fast, timing_score = bot_detector.check_timing(time_to_convert_seconds)
            if timing_score > 0:
                signals.append(FraudSignal(
                    name="fast_conversion", score=timing_score, weight=1.5,
                    description=f"Conversion in {time_to_convert_seconds}s",
                ))

        # Aggregate score
        if not signals:
            return 0.0, signals

        # Instant block: any signal at 100 with weight ≥ 2
        for s in signals:
            if s.weighted_score >= self.INSTANT_BLOCK_SCORE:
                return 100.0, signals

        total_weight = sum(s.weight for s in signals)
        weighted_sum = sum(s.weighted_score for s in signals)
        final_score = min(weighted_sum / total_weight, 100.0)

        return round(final_score, 1), signals


# Module-level singleton
fraud_score_calculator = FraudScoreCalculator()
