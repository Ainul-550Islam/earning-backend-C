"""
fraud_detection/fraud_detector.py – Main Fraud Detection Orchestrator.
"""
import logging
from typing import List, Tuple

from django.utils import timezone

from ..constants import (
    FRAUD_SCORE_THRESHOLD_FLAG,
    FRAUD_SCORE_THRESHOLD_BLOCK,
    MAX_CONVERSIONS_SAME_IP_HOUR,
    MAX_CONVERSIONS_SAME_DEVICE_DAY,
    BOT_VELOCITY_THRESHOLD,
    KNOWN_BOT_USER_AGENTS,
)
from ..enums import FraudType
from ..models import ClickLog, FraudAttemptLog, IPBlacklist, PostbackRawLog
from ..signals import fraud_detected, fraud_auto_blocked

logger = logging.getLogger(__name__)


class FraudSignal:
    """Represents a single fraud signal with a score contribution."""
    def __init__(self, signal_type: str, score: float, description: str):
        self.signal_type = signal_type
        self.score = score
        self.description = description

    def to_dict(self):
        return {
            "type": self.signal_type,
            "score": self.score,
            "description": self.description,
        }


def calculate_fraud_score(
    ip_address: str = "",
    user_agent: str = "",
    device_fingerprint: str = "",
    user=None,
    network=None,
    raw_log: PostbackRawLog = None,
) -> Tuple[float, List[FraudSignal]]:
    """
    Calculate a fraud score (0–100) for a given request.
    Returns (score, signals).
    """
    signals: List[FraudSignal] = []

    # ── Signal 1: Known Bot User Agent ────────────────────────────────────────
    if user_agent:
        for bot_ua in KNOWN_BOT_USER_AGENTS:
            if bot_ua.lower() in user_agent.lower():
                signals.append(FraudSignal(
                    "known_bot_ua", 90,
                    f"User-Agent matches known bot: {bot_ua}",
                ))
                break

    # ── Signal 2: IP Blacklist ────────────────────────────────────────────────
    if ip_address:
        from ..enums import BlacklistType
        if IPBlacklist.objects.is_blacklisted(ip_address, BlacklistType.IP):
            signals.append(FraudSignal(
                "blacklisted_ip", 100,
                f"IP {ip_address} is blacklisted.",
            ))

    # ── Signal 3: IP Velocity (too many conversions from same IP) ────────────
    if ip_address:
        cutoff = timezone.now() - timezone.timedelta(hours=1)
        ip_conv_count = PostbackRawLog.objects.filter(
            source_ip=ip_address,
            received_at__gte=cutoff,
        ).count()
        if ip_conv_count >= MAX_CONVERSIONS_SAME_IP_HOUR:
            signals.append(FraudSignal(
                "ip_velocity", 70,
                f"IP {ip_address} has {ip_conv_count} postbacks in last hour.",
            ))

    # ── Signal 4: Device Velocity ─────────────────────────────────────────────
    if device_fingerprint:
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        dev_count = ClickLog.objects.filter(
            device_fingerprint=device_fingerprint,
            clicked_at__gte=cutoff,
        ).count()
        if dev_count >= MAX_CONVERSIONS_SAME_DEVICE_DAY:
            signals.append(FraudSignal(
                "device_velocity", 65,
                f"Device {device_fingerprint[:16]}... has {dev_count} clicks in 24h.",
            ))

    # ── Signal 5: Proxy / VPN (placeholder — integrate ipinfo.io or similar) ──
    # In production: call an IP intelligence API and check for VPN/proxy/TOR
    # if is_vpn_or_proxy(ip_address):
    #     signals.append(FraudSignal("vpn_proxy", 40, "VPN/Proxy detected."))

    # ── Signal 6: Missing User Agent ─────────────────────────────────────────
    if not user_agent:
        signals.append(FraudSignal(
            "missing_ua", 30, "No User-Agent provided (programmatic request).",
        ))

    # Aggregate score (cap at 100)
    total_score = min(sum(s.score for s in signals) / max(len(signals), 1) if signals else 0, 100)

    return total_score, signals


def scan_click(click_log: ClickLog) -> bool:
    """
    Run fraud checks on a ClickLog after generation.
    Returns True if fraud detected.
    """
    score, signals = calculate_fraud_score(
        ip_address=click_log.ip_address or "",
        user_agent=click_log.user_agent or "",
        device_fingerprint=click_log.device_fingerprint or "",
        user=click_log.user,
        network=click_log.network,
    )

    if score >= FRAUD_SCORE_THRESHOLD_FLAG:
        fraud_type = _dominant_fraud_type(signals)
        fraud_log = FraudAttemptLog.objects.create(
            tenant=click_log.tenant,
            click_log=click_log,
            network=click_log.network,
            user=click_log.user,
            fraud_type=fraud_type,
            fraud_score=score,
            is_auto_blocked=(score >= FRAUD_SCORE_THRESHOLD_BLOCK),
            source_ip=click_log.ip_address,
            user_agent=click_log.user_agent,
            country=click_log.country,
            signals=[s.to_dict() for s in signals],
        )
        click_log.mark_fraud(fraud_type=fraud_type, score=score)
        fraud_detected.send(sender=FraudAttemptLog, fraud_log=fraud_log, raw_log=None)

        if score >= FRAUD_SCORE_THRESHOLD_BLOCK:
            _auto_blacklist_ip(click_log.ip_address, fraud_log, click_log.tenant)

        return True
    return False


def scan_postback(raw_log: PostbackRawLog) -> Tuple[bool, float, List[FraudSignal]]:
    """
    Run fraud checks on an incoming postback.
    Returns (is_fraud, score, signals).
    """
    score, signals = calculate_fraud_score(
        ip_address=raw_log.source_ip or "",
        network=raw_log.network,
        raw_log=raw_log,
    )

    if score >= FRAUD_SCORE_THRESHOLD_FLAG:
        fraud_type = _dominant_fraud_type(signals)
        FraudAttemptLog.objects.create(
            tenant=raw_log.tenant,
            raw_log=raw_log,
            network=raw_log.network,
            fraud_type=fraud_type,
            fraud_score=score,
            is_auto_blocked=(score >= FRAUD_SCORE_THRESHOLD_BLOCK),
            source_ip=raw_log.source_ip,
            signals=[s.to_dict() for s in signals],
        )
        return True, score, signals
    return False, score, signals


def run_scheduled_scan() -> dict:
    """
    Periodic background fraud scan.
    Looks for patterns across recent clicks and postbacks.
    """
    flagged = 0
    blocked = 0

    # Check for high-velocity IPs in last hour
    from django.db.models import Count
    from ..models import PostbackRawLog

    cutoff = timezone.now() - timezone.timedelta(hours=1)
    velocity_ips = (
        PostbackRawLog.objects
        .filter(received_at__gte=cutoff)
        .values("source_ip")
        .annotate(cnt=Count("id"))
        .filter(cnt__gte=MAX_CONVERSIONS_SAME_IP_HOUR)
    )

    for row in velocity_ips:
        ip = row["source_ip"]
        if not ip:
            continue
        existing = IPBlacklist.objects.active().filter(value=ip).exists()
        if not existing:
            fraud_log = FraudAttemptLog.objects.create(
                fraud_type=FraudType.VELOCITY_ABUSE,
                fraud_score=75,
                is_auto_blocked=True,
                source_ip=ip,
                details={"velocity_count": row["cnt"], "window_hours": 1},
            )
            _auto_blacklist_ip(ip, fraud_log, tenant=None)
            blocked += 1
        flagged += 1

    return {"flagged": flagged, "auto_blocked": blocked}


def _auto_blacklist_ip(ip_address: str, fraud_log: FraudAttemptLog, tenant=None):
    """Add an IP to the blacklist automatically."""
    if not ip_address:
        return
    from ..enums import BlacklistType, BlacklistReason
    IPBlacklist.objects.get_or_create(
        blacklist_type=BlacklistType.IP,
        value=ip_address,
        tenant=tenant,
        defaults={
            "reason": BlacklistReason.FRAUD,
            "is_active": True,
            "added_by_system": True,
            "fraud_attempt": fraud_log,
            "notes": f"Auto-blocked: fraud_score={fraud_log.fraud_score}",
        },
    )
    fraud_auto_blocked.send(
        sender=IPBlacklist,
        ip=ip_address,
        reason=BlacklistReason.FRAUD,
    )
    logger.warning("Auto-blacklisted IP: %s", ip_address)


def _dominant_fraud_type(signals: List[FraudSignal]) -> str:
    """Return the fraud type from the highest-score signal."""
    if not signals:
        return FraudType.OTHER
    dominant = max(signals, key=lambda s: s.score)
    signal_to_fraud = {
        "known_bot_ua":     FraudType.BOT_TRAFFIC,
        "blacklisted_ip":   FraudType.KNOWN_BAD_IP,
        "ip_velocity":      FraudType.VELOCITY_ABUSE,
        "device_velocity":  FraudType.VELOCITY_ABUSE,
        "vpn_proxy":        FraudType.PROXY_VPN,
    }
    return signal_to_fraud.get(dominant.signal_type, FraudType.OTHER)
