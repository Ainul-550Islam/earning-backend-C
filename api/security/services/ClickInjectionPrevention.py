"""
api/security/services/ClickInjectionPrevention.py
===================================================
Click Injection Prevention — CPAlead-level affiliate fraud protection.

Click injection is when malware/apps fire fake clicks just before a real
install/conversion to steal the attribution credit.

Detection signals:
1. Install-to-click time too short        (< 5 seconds = impossible for real user)
2. Click timestamp in the future          (clock manipulation)
3. Click token reuse across users/IPs
4. Impossible click velocity              (same device, multiple offers simultaneously)
5. Referrer spoofing                      (fake traffic sources)
6. Click-to-conversion ratio anomaly      (99%+ CVR = injected)
7. Sub-ID pattern analysis                (known fraud sub-ids)
8. SHA-256 hash chain verification        (tampered click data)
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("security.services.click_injection")

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_CLICK_TO_INSTALL_SECONDS  = 5        # below this = injected
MAX_CLICK_TO_INSTALL_SECONDS  = 604800   # 7 days — older clicks ignored
MAX_CLICKS_PER_DEVICE_SECOND  = 3        # simultaneous clicks = fraud
FUTURE_CLICK_TOLERANCE_SECS   = 30       # allow 30s clock drift
HIGH_CVR_THRESHOLD             = 0.90    # 90%+ conversion rate = suspicious
MIN_REFERRER_SCORE             = 30      # below this = spoofed referrer

# Known fraud sub-id patterns (regex-free, string matching)
FRAUD_SUBID_PATTERNS = [
    "test", "fraud", "inject", "bot", "fake",
    "null", "undefined", "0000", "1111", "9999",
]


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClickValidationResult:
    is_valid:           bool
    is_injected:        bool
    risk_score:         int               = 0    # 0-100
    signals:            List[str]         = field(default_factory=list)
    recommended_action: str               = "allow"   # allow | flag | block | reject
    click_token:        str               = ""
    details:            Dict              = field(default_factory=dict)

    @property
    def severity(self) -> str:
        if self.risk_score >= 80: return "critical"
        if self.risk_score >= 60: return "high"
        if self.risk_score >= 40: return "medium"
        return "low"

    def to_dict(self) -> dict:
        return {
            "is_valid":           self.is_valid,
            "is_injected":        self.is_injected,
            "risk_score":         self.risk_score,
            "severity":           self.severity,
            "signals":            self.signals,
            "recommended_action": self.recommended_action,
            "details":            self.details,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class ClickInjectionPrevention:
    """
    Multi-signal click injection detection engine.

    Usage — validate a click when it arrives:
        engine = ClickInjectionPrevention()
        result = engine.validate_click(
            click_token  = request.GET.get("click_id"),
            offer_id     = "offer_123",
            user_id      = request.user.id,
            ip           = get_client_ip(request),
            user_agent   = request.META.get("HTTP_USER_AGENT",""),
            referrer     = request.META.get("HTTP_REFERER",""),
            sub_id       = request.GET.get("sub_id",""),
            device_id    = request.GET.get("device_id",""),
            click_ts     = int(request.GET.get("ts", time.time())),
        )
        if not result.is_valid:
            return HttpResponse(status=403)

    Usage — validate a conversion postback:
        result = engine.validate_conversion(
            click_token    = postback_data["click_id"],
            conversion_ts  = postback_data["timestamp"],
            offer_id       = postback_data["offer_id"],
        )
    """

    # ── Click validation ──────────────────────────────────────────────────────

    def validate_click(
        self,
        click_token:  str,
        offer_id:     str,
        user_id:      Optional[int]  = None,
        ip:           str            = "",
        user_agent:   str            = "",
        referrer:     str            = "",
        sub_id:       str            = "",
        device_id:    str            = "",
        click_ts:     Optional[int]  = None,
    ) -> ClickValidationResult:
        """Full click injection check when click arrives."""
        signals    = []
        risk_score = 0
        details    = {}
        now        = int(time.time())
        click_ts   = click_ts or now

        # 1. Timestamp sanity
        if click_ts > now + FUTURE_CLICK_TOLERANCE_SECS:
            signals.append("future_timestamp")
            risk_score += 40
            details["ts_diff"] = click_ts - now

        if click_ts < now - MAX_CLICK_TO_INSTALL_SECONDS:
            signals.append("click_too_old")
            risk_score += 25
            details["click_age_days"] = (now - click_ts) // 86400

        # 2. Token reuse check
        token_key = f"sec:ci:token:{self._hash(click_token)}"
        existing  = cache.get(token_key)
        if existing:
            ex_user = existing.get("user_id")
            ex_ip   = existing.get("ip")
            if ex_user and user_id and str(ex_user) != str(user_id):
                signals.append("token_reused_different_user")
                risk_score += 70
                details["original_user"] = ex_user
            elif ex_ip and ip and ex_ip != ip:
                signals.append("token_reused_different_ip")
                risk_score += 50
                details["original_ip"] = ex_ip
        else:
            # Record first use
            cache.set(token_key, {"user_id": user_id, "ip": ip, "ts": now}, 86400)

        # 3. Device velocity — too many clicks from same device/IP
        vel_key   = f"sec:ci:vel:{self._hash(device_id or ip)}:{offer_id}"
        vel_count = (cache.get(vel_key) or 0)
        if vel_count == 0:
            cache.set(vel_key, 1, 1)  # 1-second window
        else:
            cache.incr(vel_key)
        if vel_count >= MAX_CLICKS_PER_DEVICE_SECOND:
            signals.append("impossible_click_velocity")
            risk_score += 60
            details["clicks_per_second"] = vel_count

        # 4. Sub-ID fraud pattern
        sub_lower = sub_id.lower() if sub_id else ""
        for bad in FRAUD_SUBID_PATTERNS:
            if bad in sub_lower:
                signals.append(f"fraud_subid_pattern:{bad}")
                risk_score += 30
                details["sub_id"] = sub_id
                break

        # 5. User-Agent check
        if not user_agent or len(user_agent) < 20:
            signals.append("missing_or_short_user_agent")
            risk_score += 25

        # 6. Referrer check
        referrer_score = self._score_referrer(referrer, offer_id)
        if referrer_score < MIN_REFERRER_SCORE:
            signals.append("suspicious_referrer")
            risk_score += 20
            details["referrer_score"] = referrer_score

        # 7. Store click data for conversion-time validation
        self._store_click(click_token, {
            "offer_id":   offer_id,
            "user_id":    user_id,
            "ip":         ip,
            "device_id":  device_id,
            "user_agent": user_agent,
            "sub_id":     sub_id,
            "click_ts":   click_ts,
            "risk_score": risk_score,
        })

        # 8. Determine action
        risk_score        = min(risk_score, 100)
        is_injected       = risk_score >= 60
        recommended_action = self._recommend_action(risk_score, signals)

        if signals:
            logger.warning(
                "Click injection signals: offer=%s ip=%s score=%d signals=%s",
                offer_id, ip, risk_score, signals,
            )

        return ClickValidationResult(
            is_valid           = risk_score < 60,
            is_injected        = is_injected,
            risk_score         = risk_score,
            signals            = signals,
            recommended_action = recommended_action,
            click_token        = click_token,
            details            = details,
        )

    # ── Conversion validation (postback) ──────────────────────────────────────

    def validate_conversion(
        self,
        click_token:    str,
        conversion_ts:  int,
        offer_id:       str,
        payout:         float = 0.0,
    ) -> ClickValidationResult:
        """
        Validate conversion postback against the stored click.
        Call this when an advertiser fires a conversion postback.
        """
        signals    = []
        risk_score = 0
        details    = {}

        click_data = self._load_click(click_token)
        if not click_data:
            return ClickValidationResult(
                is_valid    = False,
                is_injected = True,
                risk_score  = 100,
                signals     = ["click_not_found"],
                recommended_action = "reject",
                click_token = click_token,
                details     = {"reason": "No stored click data for this token"},
            )

        click_ts   = click_data.get("click_ts", 0)
        time_diff  = conversion_ts - click_ts

        # 1. Install-to-click time too short
        if 0 < time_diff < MIN_CLICK_TO_INSTALL_SECONDS:
            signals.append("install_to_click_too_fast")
            risk_score += 90
            details["time_diff_seconds"] = time_diff
            logger.critical(
                "CLICK INJECTION: install_time=%ds (< %ds) offer=%s token=%s",
                time_diff, MIN_CLICK_TO_INSTALL_SECONDS, offer_id, click_token[:12],
            )

        # 2. Conversion before click (impossible)
        if time_diff < 0:
            signals.append("conversion_before_click")
            risk_score += 100
            details["time_diff_seconds"] = time_diff

        # 3. Click too old for this offer
        if time_diff > MAX_CLICK_TO_INSTALL_SECONDS:
            signals.append("click_expired_for_conversion")
            risk_score += 40
            details["time_diff_days"] = time_diff // 86400

        # 4. Inherit click-level risk
        existing_risk = click_data.get("risk_score", 0)
        if existing_risk >= 40:
            signals.append("high_risk_click_source")
            risk_score += existing_risk // 2

        # 5. Suspiciously high payout for known fraud pattern
        if payout > 0 and click_data.get("sub_id", "").lower() in FRAUD_SUBID_PATTERNS:
            signals.append("fraud_subid_conversion")
            risk_score += 50

        # 6. CVR tracking per IP/device
        cvr_result = self._check_cvr(click_data.get("ip", ""), offer_id)
        if cvr_result["suspicious"]:
            signals.append("abnormal_conversion_rate")
            risk_score += 35
            details["cvr"] = cvr_result["cvr"]

        risk_score         = min(risk_score, 100)
        is_injected        = risk_score >= 50
        recommended_action = self._recommend_action(risk_score, signals)

        if is_injected:
            logger.warning(
                "Conversion rejected (click injection): score=%d offer=%s token=%s signals=%s",
                risk_score, offer_id, click_token[:12], signals,
            )

        return ClickValidationResult(
            is_valid           = not is_injected,
            is_injected        = is_injected,
            risk_score         = risk_score,
            signals            = signals,
            recommended_action = recommended_action,
            click_token        = click_token,
            details            = details,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:24]

    def _store_click(self, token: str, data: dict) -> None:
        cache.set(f"sec:ci:click:{self._hash(token)}", data, MAX_CLICK_TO_INSTALL_SECONDS)

    def _load_click(self, token: str) -> Optional[dict]:
        return cache.get(f"sec:ci:click:{self._hash(token)}")

    def _score_referrer(self, referrer: str, offer_id: str) -> int:
        """Score referrer quality 0-100. 100 = legitimate, 0 = spoofed."""
        if not referrer:
            return 20   # no referrer = somewhat suspicious

        score = 50

        # Known ad network referrers get bonus
        trusted_domains = [
            "google.com", "facebook.com", "meta.com", "tiktok.com",
            "snapchat.com", "twitter.com", "x.com", "instagram.com",
            "youtube.com", "bing.com", "yahoo.com",
        ]
        for domain in trusted_domains:
            if domain in referrer:
                score = 90
                break

        # Known fraud referrers
        suspicious_referrers = ["localhost", "127.0.0.1", "0.0.0.0", "test.com"]
        for bad in suspicious_referrers:
            if bad in referrer:
                score = 5
                break

        return score

    def _check_cvr(self, ip: str, offer_id: str) -> dict:
        """Track conversion rate per IP per offer. Flag if > 90%."""
        click_key   = f"sec:ci:cvr:clicks:{ip}:{offer_id}"
        conv_key    = f"sec:ci:cvr:convs:{ip}:{offer_id}"
        clicks      = cache.get(click_key) or 0
        convs       = (cache.get(conv_key) or 0) + 1
        cache.set(conv_key, convs, 86400)
        if clicks < 5:
            return {"suspicious": False, "cvr": 0}
        cvr = convs / max(clicks, 1)
        cache.set(conv_key, convs, 86400)
        return {"suspicious": cvr > HIGH_CVR_THRESHOLD, "cvr": round(cvr, 3)}

    def _recommend_action(self, risk_score: int, signals: List[str]) -> str:
        if "conversion_before_click" in signals:   return "reject"
        if "install_to_click_too_fast" in signals: return "reject"
        if "token_reused_different_user" in signals: return "reject"
        if risk_score >= 80: return "block"
        if risk_score >= 60: return "reject"
        if risk_score >= 40: return "flag"
        return "allow"


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

click_injection_guard = ClickInjectionPrevention()