"""
utils/fraud_detector.py – Postback-internal geo/device fraud detection.

Design principles:
  • 100% self-contained inside postback app — no external app imports.
  • Uses Django cache for sliding-window counters (same pattern as rate_limiter).
  • Four independent checks, each returns a FraudSignal.
  • Never raises — returns a FraudResult with is_fraudulent bool + reasons list.
  • Caller (services.py) decides whether to reject or just flag.

Checks performed:
  1. Geo anomaly      — same user_id firing from >N countries in 1 hour
  2. IP velocity      — single IP firing >N postbacks in 1 minute
  3. Device mismatch  — adapted payload device/os fields sanity check
  4. Known bad subnet — configurable CIDR blocklist via NetworkPostbackConfig.metadata
"""
import hashlib
import ipaddress
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

_PREFIX = "postback:fraud"

# ── Thresholds (can be overridden per-network via NetworkPostbackConfig.metadata) ─
_DEFAULT_GEO_COUNTRIES_PER_HOUR = 3      # >3 different countries in 1h = anomaly
_DEFAULT_IP_VELOCITY_PER_MINUTE = 30     # >30 postbacks from same IP/min = suspicious
_DEFAULT_IP_VELOCITY_WINDOW = 60         # seconds
_DEFAULT_GEO_WINDOW = 3600              # seconds (1 hour)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class FraudSignal:
    check: str          # check name
    triggered: bool
    reason: str = ""
    score: int = 0      # 0–100 severity


@dataclass
class FraudResult:
    is_fraudulent: bool
    total_score: int
    signals: List[FraudSignal] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    @classmethod
    def clean(cls) -> "FraudResult":
        return cls(is_fraudulent=False, total_score=0)


# ── Main entry point ──────────────────────────────────────────────────────────

def check_fraud(
    *,
    adapted_payload: dict,
    source_ip: Optional[str],
    network_config,
    fraud_threshold: int = 60,
) -> FraudResult:
    """
    Run all fraud checks against the adapted payload.

    Args:
        adapted_payload:  The normalised payload dict from the adapter.
        source_ip:        Source IP string (IPv4 or IPv6).
        network_config:   NetworkPostbackConfig instance.
        fraud_threshold:  Total score >= this → is_fraudulent=True.

    Returns:
        FraudResult — never raises.
    """
    try:
        return _run_checks(adapted_payload, source_ip, network_config, fraud_threshold)
    except Exception as exc:
        logger.error("FraudDetector unexpected error (failing open): %s", exc)
        return FraudResult.clean()


def _run_checks(adapted_payload, source_ip, network_config, threshold) -> FraudResult:
    meta = getattr(network_config, "metadata", {}) or {}
    network_key = getattr(network_config, "network_key", "?")
    user_id = str(adapted_payload.get("user_id", "") or "")
    country = str(adapted_payload.get("country", "") or "").upper()
    device = str(adapted_payload.get("device", "") or "").lower()
    os_name = str(adapted_payload.get("os", "") or "").lower()

    signals: List[FraudSignal] = []

    # ── Check 1: IP velocity ──────────────────────────────────────────────────
    signals.append(_check_ip_velocity(
        source_ip=source_ip,
        network_key=network_key,
        limit=meta.get("fraud_ip_velocity_limit", _DEFAULT_IP_VELOCITY_PER_MINUTE),
        window=_DEFAULT_IP_VELOCITY_WINDOW,
    ))

    # ── Check 2: Geo anomaly (per user) ──────────────────────────────────────
    if user_id and country:
        signals.append(_check_geo_anomaly(
            user_id=user_id,
            country=country,
            network_key=network_key,
            max_countries=meta.get("fraud_max_countries_per_hour", _DEFAULT_GEO_COUNTRIES_PER_HOUR),
            window=_DEFAULT_GEO_WINDOW,
        ))

    # ── Check 3: Device/OS sanity ─────────────────────────────────────────────
    if device or os_name:
        signals.append(_check_device_sanity(device=device, os_name=os_name))

    # ── Check 4: Known bad subnet (from network metadata) ────────────────────
    bad_subnets = meta.get("fraud_blocked_subnets", [])
    if source_ip and bad_subnets:
        signals.append(_check_blocked_subnet(source_ip=source_ip, bad_subnets=bad_subnets))

    # ── Aggregate ─────────────────────────────────────────────────────────────
    total_score = sum(s.score for s in signals if s.triggered)
    reasons = [s.reason for s in signals if s.triggered and s.reason]
    is_fraudulent = total_score >= threshold

    if is_fraudulent:
        logger.warning(
            "FraudDetector: network=%s ip=%s score=%d reasons=%s",
            network_key, source_ip, total_score, reasons,
        )

    return FraudResult(
        is_fraudulent=is_fraudulent,
        total_score=total_score,
        signals=signals,
        reasons=reasons,
    )


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_ip_velocity(
    source_ip: Optional[str],
    network_key: str,
    limit: int,
    window: int,
) -> FraudSignal:
    """Check how many postbacks came from this IP in the window."""
    if not source_ip:
        return FraudSignal(check="ip_velocity", triggered=False)

    import time
    bucket = int(time.time()) // window
    ip_hash = hashlib.md5(source_ip.encode()).hexdigest()[:12]
    key = f"{_PREFIX}:ipvel:{network_key}:{ip_hash}:{bucket}"

    try:
        added = cache.add(key, 1, timeout=window + 5)
        count = 1 if added else cache.incr(key)
    except Exception:
        return FraudSignal(check="ip_velocity", triggered=False)

    if count > limit:
        return FraudSignal(
            check="ip_velocity",
            triggered=True,
            reason=f"IP velocity: {count} postbacks in {window}s (limit={limit})",
            score=50,
        )
    return FraudSignal(check="ip_velocity", triggered=False)


def _check_geo_anomaly(
    user_id: str,
    country: str,
    network_key: str,
    max_countries: int,
    window: int,
) -> FraudSignal:
    """
    Track which countries a user_id fires from within the window.
    Flag if they appear from more than max_countries distinct countries.
    """
    import time
    uid_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
    bucket = int(time.time()) // window
    key = f"{_PREFIX}:geo:{network_key}:{uid_hash}:{bucket}"

    try:
        raw = cache.get(key)
        countries: set = set(raw.split(",")) if raw else set()
        countries.add(country[:2])  # Keep ISO-2 only
        cache.set(key, ",".join(countries), timeout=window + 5)
        count = len(countries)
    except Exception:
        return FraudSignal(check="geo_anomaly", triggered=False)

    if count > max_countries:
        return FraudSignal(
            check="geo_anomaly",
            triggered=True,
            reason=f"Geo anomaly: user seen from {count} countries in {window}s (limit={max_countries})",
            score=40,
        )
    return FraudSignal(check="geo_anomaly", triggered=False)


def _check_device_sanity(device: str, os_name: str) -> FraudSignal:
    """
    Basic sanity check: known impossible device/OS combinations.
    E.g. 'ios' device with 'windows' os is suspicious.
    """
    impossible_combos = [
        ("ios", "windows"),
        ("ios", "android"),
        ("android", "ios"),
        ("android", "macos"),
    ]
    for dev_kw, os_kw in impossible_combos:
        if dev_kw in device and os_kw in os_name:
            return FraudSignal(
                check="device_sanity",
                triggered=True,
                reason=f"Impossible device/OS combo: device={device!r} os={os_name!r}",
                score=30,
            )
    return FraudSignal(check="device_sanity", triggered=False)


def _check_blocked_subnet(source_ip: str, bad_subnets: list) -> FraudSignal:
    """
    Check if source_ip falls within any of the blocked CIDR ranges.
    bad_subnets is read from NetworkPostbackConfig.metadata['fraud_blocked_subnets'].
    """
    try:
        ip_obj = ipaddress.ip_address(source_ip)
    except ValueError:
        return FraudSignal(check="blocked_subnet", triggered=False)

    for cidr in bad_subnets:
        try:
            if ip_obj in ipaddress.ip_network(cidr, strict=False):
                return FraudSignal(
                    check="blocked_subnet",
                    triggered=True,
                    reason=f"IP {source_ip} is in blocked subnet {cidr}",
                    score=80,
                )
        except ValueError:
            continue  # Skip malformed CIDR entries

    return FraudSignal(check="blocked_subnet", triggered=False)


# ══════════════════════════════════════════════════════════════════════════════
# ENHANCED ANTI-CHEAT CHECKS
# ══════════════════════════════════════════════════════════════════════════════

import ipaddress as _ipaddress

# Known VPN/datacenter ASN prefixes and CIDR ranges (partial — extend as needed)
_DATACENTER_CIDR = [
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",  # RFC1918
    "100.64.0.0/10",  # CGNAT
]


def _is_datacenter_ip(ip: str) -> bool:
    """Return True if IP belongs to a datacenter/VPN/private range."""
    try:
        addr = _ipaddress.ip_address(ip)
        for cidr in _DATACENTER_CIDR:
            if addr in _ipaddress.ip_network(cidr, strict=False):
                return True
    except ValueError:
        pass
    return False


def check_vpn_or_proxy(source_ip: str) -> "FraudSignal":
    """
    Flag requests from private/datacenter IP ranges.
    Production should replace this with a paid GeoIP / proxy-detection API
    (e.g. ip-api.com, MaxMind, IPQualityScore).
    """
    if _is_datacenter_ip(source_ip):
        return FraudSignal(
            check="vpn_proxy_check",
            triggered=True,
            score=50,
            detail=f"IP {source_ip} is in a datacenter/private range — possible VPN/proxy.",
        )
    return FraudSignal(check="vpn_proxy_check", triggered=False, score=0, detail="")


def check_multi_account(user_id: str, source_ip: str, window_hours: int = 24) -> "FraudSignal":
    """
    Detect multiple distinct users completing offers from the same IP
    within `window_hours`. Strongly correlated with multi-accounting abuse.
    """
    from django.utils import timezone
    import datetime
    from django.contrib.auth import get_user_model
    from ..models import PostbackLog

    cutoff = timezone.now() - datetime.timedelta(hours=window_hours)
    distinct_users = (
        PostbackLog.objects
        .filter(source_ip=source_ip, received_at__gte=cutoff)
        .values("resolved_user_id")
        .distinct()
        .count()
    )
    if distinct_users >= 5:
        return FraudSignal(
            check="multi_account",
            triggered=True,
            score=70,
            detail=f"IP {source_ip} has {distinct_users} distinct users in last {window_hours}h.",
        )
    return FraudSignal(check="multi_account", triggered=False, score=0, detail="")


def check_device_fingerprint(
    current_fingerprint: str,
    user_id: str,
    window_hours: int = 48,
) -> "FraudSignal":
    """
    Detect a single device fingerprint (IDFA/GAID/click_id hash) being
    used by multiple user accounts — classic device-sharing fraud.
    """
    if not current_fingerprint:
        return FraudSignal(check="device_fingerprint", triggered=False, score=0, detail="")

    from django.utils import timezone
    import datetime
    from ..models import OfferClick

    cutoff = timezone.now() - datetime.timedelta(hours=window_hours)
    other_users = (
        OfferClick.objects
        .filter(
            idfa=current_fingerprint,
            clicked_at__gte=cutoff,
        )
        .exclude(user_id=user_id)
        .values("user_id")
        .distinct()
        .count()
    ) if current_fingerprint else 0

    if other_users >= 2:
        return FraudSignal(
            check="device_fingerprint",
            triggered=True,
            score=80,
            detail=f"Device fingerprint seen across {other_users + 1} accounts in {window_hours}h.",
        )
    return FraudSignal(check="device_fingerprint", triggered=False, score=0, detail="")


def check_withdrawal_fraud(user_id: str) -> "FraudSignal":
    """
    Pre-withdrawal fraud check: flag if account is too new, has reversed
    completions, or earning velocity is abnormally high.
    """
    from django.utils import timezone
    import datetime
    from django.contrib.auth import get_user_model
    from ..models import UserOfferCompletion

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return FraudSignal(check="withdrawal_fraud", triggered=True, score=90,
                           detail="User not found.")

    # Account age check
    account_age_hours = (timezone.now() - user.date_joined).total_seconds() / 3600
    if account_age_hours < 24:
        return FraudSignal(
            check="withdrawal_fraud",
            triggered=True,
            score=60,
            detail=f"Account only {account_age_hours:.1f}h old — minimum 24h required.",
        )

    # High reversal rate check
    total = UserOfferCompletion.objects.filter(user_id=user_id).count()
    reversed_count = UserOfferCompletion.objects.filter(user_id=user_id, is_reversed=True).count()
    if total > 0 and reversed_count / total > 0.3:
        return FraudSignal(
            check="withdrawal_fraud",
            triggered=True,
            score=75,
            detail=f"{reversed_count}/{total} completions reversed ({reversed_count/total:.0%}).",
        )

    # Velocity check: too many points in last 24h
    since = timezone.now() - datetime.timedelta(hours=24)
    from django.db.models import Sum
    recent_points = (
        UserOfferCompletion.objects
        .filter(user_id=user_id, completed_at__gte=since, is_reversed=False)
        .aggregate(total=Sum("points_awarded"))["total"] or 0
    )
    if recent_points > 10000:
        return FraudSignal(
            check="withdrawal_fraud",
            triggered=True,
            score=65,
            detail=f"Unusually high earnings in last 24h: {recent_points} pts.",
        )

    return FraudSignal(check="withdrawal_fraud", triggered=False, score=0, detail="")


def full_fraud_check_on_withdrawal(user_id: str, source_ip: str = "") -> dict:
    """
    Run all withdrawal fraud checks and return a combined result.
    Called from WithdrawalRequestViewSet.perform_create().
    """
    checks = [
        check_withdrawal_fraud(user_id),
    ]
    if source_ip:
        checks.append(check_vpn_or_proxy(source_ip))
        checks.append(check_multi_account(user_id, source_ip))

    triggered = [c for c in checks if c.triggered]
    total_score = sum(c.score for c in triggered)

    return {
        "passed": total_score < 60,
        "risk_score": total_score,
        "flags": [{"check": c.check, "score": c.score, "detail": c.detail} for c in triggered],
    }
