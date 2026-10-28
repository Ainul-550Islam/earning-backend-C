"""
api/security/services/SubIDTrackingSecurity.py
===============================================
Sub-ID Tracking Security — Publisher fraud detection through sub-ID analysis.

Sub-IDs (also called sub-sources, publisher sub-accounts) are used by affiliates
to track traffic sources. Fraudsters manipulate sub-IDs to:
- Launder traffic from banned sources (sub-ID stuffing)
- Fake legitimate traffic origins (sub-ID spoofing)
- Re-use high-performing sub-IDs from other publishers (sub-ID theft)
- Inflate conversion counts per sub-ID (sub-ID pumping)

This service provides:
1. Sub-ID format validation (enforce platform rules)
2. Sub-ID fraud pattern detection
3. Sub-ID velocity tracking (clicks + conversions per window)
4. Sub-ID reputation scoring (historical performance)
5. Cross-publisher sub-ID theft detection
6. Sub-ID blacklist management
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger("security.services.subid_security")

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_SUBID_LENGTH         = 64
SUBID_ALLOWED_PATTERN    = re.compile(r'^[a-zA-Z0-9_\-\.]{1,64}$')

# Known fraud/test sub-ID values
BLACKLISTED_SUBID_VALUES = frozenset([
    "test", "testing", "demo", "fake", "fraud", "bot", "automated",
    "null", "none", "undefined", "unknown", "n/a", "na", "0", "00",
    "000", "0000", "1", "11", "111", "1111", "admin", "default",
    "click", "traffic", "source", "sub", "subid", "publisher",
])

# Velocity thresholds
SUBID_MAX_CLICKS_PER_HOUR      = 5000
SUBID_MAX_CONVERSIONS_PER_HOUR = 500
SUBID_MAX_CVR_THRESHOLD        = 0.85    # 85%+ CVR is suspicious
SUBID_MIN_CVR_THRESHOLD        = 0.0001  # extremely low CVR = bot traffic

# Reputation windows
REPUTATION_WINDOW_DAYS = 30


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SubIDValidationResult:
    is_valid:       bool
    sub_id:         str
    publisher_id:   Optional[int]    = None
    risk_score:     int              = 0     # 0-100
    signals:        List[str]        = field(default_factory=list)
    action:         str              = "allow"  # allow | flag | block | reject
    reputation:     Optional[dict]   = None
    details:        Dict             = field(default_factory=dict)

    @property
    def is_high_risk(self) -> bool:
        return self.risk_score >= 60

    def to_dict(self) -> dict:
        return {
            "is_valid":     self.is_valid,
            "sub_id":       self.sub_id,
            "risk_score":   self.risk_score,
            "signals":      self.signals,
            "action":       self.action,
            "reputation":   self.reputation,
        }


@dataclass
class SubIDReputation:
    sub_id:          str
    publisher_id:    int
    total_clicks:    int   = 0
    total_convs:     int   = 0
    avg_cvr:         float = 0.0
    fraud_flags:     int   = 0
    is_blacklisted:  bool  = False
    first_seen:      Optional[float] = None
    last_seen:       Optional[float] = None
    risk_score:      int   = 0

    def to_dict(self) -> dict:
        return {
            "sub_id":         self.sub_id,
            "publisher_id":   self.publisher_id,
            "total_clicks":   self.total_clicks,
            "total_convs":    self.total_convs,
            "avg_cvr":        round(self.avg_cvr, 4),
            "fraud_flags":    self.fraud_flags,
            "is_blacklisted": self.is_blacklisted,
            "risk_score":     self.risk_score,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class SubIDTrackingSecurity:
    """
    Sub-ID fraud detection and tracking security.

    Usage — validate on click:
        engine  = SubIDTrackingSecurity()
        result  = engine.validate(
            sub_id       = request.GET.get("sub_id", ""),
            publisher_id = publisher.id,
            offer_id     = offer.id,
            ip           = get_client_ip(request),
        )
        if result.action == "block":
            return 403

    Usage — record a conversion:
        engine.record_conversion(sub_id="source_abc", publisher_id=42, payout=1.50)

    Usage — get reputation:
        rep = engine.get_reputation(sub_id="source_abc", publisher_id=42)
    """

    # ── Validate ──────────────────────────────────────────────────────────────

    def validate(
        self,
        sub_id:       str,
        publisher_id: int,
        offer_id:     str             = "",
        ip:           str             = "",
        extra_context: Optional[dict] = None,
    ) -> SubIDValidationResult:
        """
        Full sub-ID validation pipeline.
        Call this on every click with a sub-ID parameter.
        """
        signals    = []
        risk_score = 0
        details    = {}

        # 1. Format validation
        format_ok, format_signal = self._validate_format(sub_id)
        if not format_ok:
            signals.append(format_signal)
            risk_score += 30
            details["format_issue"] = format_signal

        # 2. Blacklist check
        if self._is_blacklisted(sub_id, publisher_id):
            return SubIDValidationResult(
                is_valid     = False,
                sub_id       = sub_id,
                publisher_id = publisher_id,
                risk_score   = 100,
                signals      = ["subid_blacklisted"],
                action       = "reject",
                details      = {"reason": "Sub-ID is blacklisted"},
            )

        # 3. Known fraud value check
        sub_lower = sub_id.lower().strip()
        if sub_lower in BLACKLISTED_SUBID_VALUES:
            signals.append("known_fraud_subid_value")
            risk_score += 60
            details["matched_value"] = sub_lower

        # 4. Velocity check (clicks per hour)
        vel_result = self._check_velocity(sub_id, publisher_id, offer_id)
        if vel_result["clicks_exceeded"]:
            signals.append("subid_click_velocity_exceeded")
            risk_score += 50
            details["clicks_per_hour"] = vel_result["clicks"]
        if vel_result["convs_exceeded"]:
            signals.append("subid_conversion_velocity_exceeded")
            risk_score += 40
            details["convs_per_hour"] = vel_result["convs"]

        # 5. CVR anomaly (from reputation)
        rep = self._load_reputation(sub_id, publisher_id)
        if rep and rep.total_clicks > 50:
            if rep.avg_cvr > SUBID_MAX_CVR_THRESHOLD:
                signals.append("abnormally_high_cvr")
                risk_score += 45
                details["cvr"] = rep.avg_cvr
            elif rep.avg_cvr < SUBID_MIN_CVR_THRESHOLD and rep.total_clicks > 1000:
                signals.append("abnormally_low_cvr_high_volume")
                risk_score += 30
                details["cvr"] = rep.avg_cvr
            if rep.fraud_flags >= 3:
                signals.append("repeated_fraud_flags")
                risk_score += rep.fraud_flags * 10

        # 6. Cross-publisher theft detection
        theft_detected, theft_detail = self._detect_cross_publisher_theft(
            sub_id, publisher_id
        )
        if theft_detected:
            signals.append("cross_publisher_subid_theft")
            risk_score += 70
            details.update(theft_detail)

        # 7. IP-SubID consistency (same sub_id from wildly different IPs)
        ip_ok = self._check_ip_subid_consistency(sub_id, publisher_id, ip)
        if not ip_ok:
            signals.append("subid_ip_inconsistency")
            risk_score += 25

        # 8. Record this click in reputation system
        self._record_click(sub_id, publisher_id, ip)

        # Determine action
        risk_score  = min(risk_score, 100)
        action      = self._determine_action(risk_score, signals)
        is_valid    = action in ("allow", "flag")

        if signals:
            logger.warning(
                "SubID fraud signals: pub=%d sub_id=%s score=%d signals=%s",
                publisher_id, sub_id[:20], risk_score, signals,
            )

        return SubIDValidationResult(
            is_valid     = is_valid,
            sub_id       = sub_id,
            publisher_id = publisher_id,
            risk_score   = risk_score,
            signals      = signals,
            action       = action,
            reputation   = rep.to_dict() if rep else None,
            details      = details,
        )

    # ── Record conversion ─────────────────────────────────────────────────────

    def record_conversion(
        self,
        sub_id:       str,
        publisher_id: int,
        payout:       float   = 0.0,
        offer_id:     str     = "",
    ) -> None:
        """Record a conversion for this sub-ID (update reputation)."""
        rep_key  = self._rep_key(sub_id, publisher_id)
        rep_data = cache.get(rep_key) or self._default_rep_data(sub_id, publisher_id)

        rep_data["total_convs"]  = rep_data.get("total_convs", 0) + 1
        rep_data["last_seen"]    = time.time()
        clicks                   = max(rep_data.get("total_clicks", 1), 1)
        rep_data["avg_cvr"]      = rep_data["total_convs"] / clicks

        cache.set(rep_key, rep_data, REPUTATION_WINDOW_DAYS * 86400)

        # Hourly conversion velocity
        vel_key = f"sec:subid:vel:conv:{self._hash(sub_id + str(publisher_id))}"
        count   = cache.get(vel_key) or 0
        if count == 0:
            cache.set(vel_key, 1, 3600)
        else:
            cache.incr(vel_key)

        logger.debug("SubID conversion recorded: pub=%d sub=%s", publisher_id, sub_id[:20])

    # ── Blacklist management ──────────────────────────────────────────────────

    def blacklist(
        self,
        sub_id:       str,
        publisher_id: int,
        reason:       str = "",
        duration_days: int = 30,
    ) -> None:
        """Blacklist a sub-ID for a publisher."""
        key = f"sec:subid:bl:{self._hash(sub_id + str(publisher_id))}"
        cache.set(key, {"reason": reason, "ts": time.time()}, duration_days * 86400)
        logger.info(
            "SubID blacklisted: pub=%d sub=%s reason=%s",
            publisher_id, sub_id[:20], reason,
        )

        # Update reputation
        rep_key  = self._rep_key(sub_id, publisher_id)
        rep_data = cache.get(rep_key) or self._default_rep_data(sub_id, publisher_id)
        rep_data["is_blacklisted"] = True
        rep_data["fraud_flags"]    = rep_data.get("fraud_flags", 0) + 1
        cache.set(rep_key, rep_data, REPUTATION_WINDOW_DAYS * 86400)

    def unblacklist(self, sub_id: str, publisher_id: int) -> None:
        """Remove a sub-ID from the blacklist."""
        key = f"sec:subid:bl:{self._hash(sub_id + str(publisher_id))}"
        cache.delete(key)

    # ── Reputation ────────────────────────────────────────────────────────────

    def get_reputation(self, sub_id: str, publisher_id: int) -> SubIDReputation:
        """Get full reputation data for a sub-ID."""
        rep = self._load_reputation(sub_id, publisher_id)
        if rep:
            return rep
        return SubIDReputation(sub_id=sub_id, publisher_id=publisher_id)

    def get_top_fraud_subids(self, publisher_id: int, limit: int = 20) -> List[dict]:
        """Return top fraud sub-IDs for a publisher (from tracking data)."""
        prefix = f"sec:subid:rep:{publisher_id}:"
        try:
            keys = cache.keys(prefix + "*") if hasattr(cache, "keys") else []
            results = []
            for key in keys[:100]:
                data = cache.get(key)
                if data and data.get("risk_score", 0) >= 50:
                    results.append(data)
            results.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
            return results[:limit]
        except Exception:
            return []

    # ── Private helpers ───────────────────────────────────────────────────────

    def _validate_format(self, sub_id: str) -> Tuple[bool, str]:
        if not sub_id:
            return False, "empty_subid"
        if len(sub_id) > MAX_SUBID_LENGTH:
            return False, "subid_too_long"
        if not SUBID_ALLOWED_PATTERN.match(sub_id):
            return False, "subid_invalid_characters"
        return True, ""

    def _is_blacklisted(self, sub_id: str, publisher_id: int) -> bool:
        key = f"sec:subid:bl:{self._hash(sub_id + str(publisher_id))}"
        return bool(cache.get(key))

    def _check_velocity(
        self,
        sub_id: str,
        publisher_id: int,
        offer_id: str,
    ) -> dict:
        h        = self._hash(sub_id + str(publisher_id))
        clk_key  = f"sec:subid:vel:clk:{h}"
        conv_key = f"sec:subid:vel:conv:{h}"

        clicks = (cache.get(clk_key) or 0) + 1
        if clicks == 1:
            cache.set(clk_key, 1, 3600)
        else:
            cache.incr(clk_key)
        convs  = cache.get(conv_key) or 0

        return {
            "clicks":          clicks,
            "convs":           convs,
            "clicks_exceeded": clicks > SUBID_MAX_CLICKS_PER_HOUR,
            "convs_exceeded":  convs > SUBID_MAX_CONVERSIONS_PER_HOUR,
        }

    def _detect_cross_publisher_theft(
        self,
        sub_id:       str,
        publisher_id: int,
    ) -> Tuple[bool, dict]:
        """Detect if this sub-ID is also being used by another publisher."""
        global_key  = f"sec:subid:global:{self._hash(sub_id)}"
        known_pubs  = cache.get(global_key) or []
        pub_str     = str(publisher_id)

        if pub_str not in known_pubs:
            if len(known_pubs) >= 3:
                # Sub-ID used by 3+ publishers = likely theft or shared fraud source
                return True, {
                    "other_publishers_count": len(known_pubs),
                    "sub_id":                 sub_id[:20],
                }
            known_pubs.append(pub_str)
            cache.set(global_key, known_pubs[-10:], REPUTATION_WINDOW_DAYS * 86400)

        return False, {}

    def _check_ip_subid_consistency(
        self,
        sub_id:       str,
        publisher_id: int,
        ip:           str,
    ) -> bool:
        """Check if sub-ID is used from wildly different IPs (bot rotation)."""
        if not ip:
            return True
        ip_set_key = f"sec:subid:ips:{self._hash(sub_id + str(publisher_id))}"
        known_ips  = cache.get(ip_set_key) or set()
        if isinstance(known_ips, list):
            known_ips = set(known_ips)

        known_ips.add(ip.split(".")[:2].__str__())  # compare /16 subnet
        cache.set(ip_set_key, list(known_ips)[-100:], 86400)

        # More than 50 different /16 subnets for same sub-ID = bot/VPN rotation
        return len(known_ips) <= 50

    def _record_click(self, sub_id: str, publisher_id: int, ip: str) -> None:
        rep_key  = self._rep_key(sub_id, publisher_id)
        rep_data = cache.get(rep_key) or self._default_rep_data(sub_id, publisher_id)
        rep_data["total_clicks"] = rep_data.get("total_clicks", 0) + 1
        rep_data["last_seen"]    = time.time()
        if not rep_data.get("first_seen"):
            rep_data["first_seen"] = time.time()
        cache.set(rep_key, rep_data, REPUTATION_WINDOW_DAYS * 86400)

    def _load_reputation(
        self,
        sub_id:       str,
        publisher_id: int,
    ) -> Optional[SubIDReputation]:
        data = cache.get(self._rep_key(sub_id, publisher_id))
        if not data:
            return None
        return SubIDReputation(
            sub_id         = sub_id,
            publisher_id   = publisher_id,
            total_clicks   = data.get("total_clicks", 0),
            total_convs    = data.get("total_convs", 0),
            avg_cvr        = data.get("avg_cvr", 0.0),
            fraud_flags    = data.get("fraud_flags", 0),
            is_blacklisted = data.get("is_blacklisted", False),
            first_seen     = data.get("first_seen"),
            last_seen      = data.get("last_seen"),
            risk_score     = data.get("risk_score", 0),
        )

    def _default_rep_data(self, sub_id: str, publisher_id: int) -> dict:
        return {
            "sub_id":         sub_id,
            "publisher_id":   publisher_id,
            "total_clicks":   0,
            "total_convs":    0,
            "avg_cvr":        0.0,
            "fraud_flags":    0,
            "is_blacklisted": False,
            "first_seen":     time.time(),
            "last_seen":      time.time(),
            "risk_score":     0,
        }

    def _determine_action(self, risk_score: int, signals: List[str]) -> str:
        if "subid_blacklisted" in signals:              return "reject"
        if "cross_publisher_subid_theft" in signals:    return "block"
        if "known_fraud_subid_value" in signals:        return "block"
        if "subid_click_velocity_exceeded" in signals:  return "block"
        if risk_score >= 80:  return "block"
        if risk_score >= 60:  return "reject"
        if risk_score >= 40:  return "flag"
        return "allow"

    def _rep_key(self, sub_id: str, publisher_id: int) -> str:
        return f"sec:subid:rep:{publisher_id}:{self._hash(sub_id)}"

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:24]


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

subid_security = SubIDTrackingSecurity()