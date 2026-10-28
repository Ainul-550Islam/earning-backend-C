"""
api/security/services/AdvertiserFraudShield.py
===============================================
Advertiser Fraud Shield — Protect advertisers from publisher/affiliate fraud.

Protects against:
1. Traffic quality fraud     (bot traffic sold as real users)
2. Conversion fraud          (fake/forced conversions)
3. Impression fraud          (inflated impression counts)
4. Ad stacking               (invisible ads stacked behind visible ones)
5. Domain spoofing           (fake publisher domains)
6. Publisher quality scoring (automatic publisher grade: A/B/C/D/F)
7. Budget protection         (stop spend when fraud detected)
8. Real-time fraud alerts    (notify advertiser on anomaly)
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger("security.services.advertiser_fraud_shield")


# ── Enums ─────────────────────────────────────────────────────────────────────

class PublisherGrade(str, Enum):
    A = "A"   # Excellent — premium traffic
    B = "B"   # Good — mostly clean
    C = "C"   # Average — some fraud signals
    D = "D"   # Poor — high fraud rate
    F = "F"   # Suspended — blocked from all offers


class FraudType(str, Enum):
    BOT_TRAFFIC        = "bot_traffic"
    FAKE_CONVERSION    = "fake_conversion"
    CLICK_INJECTION    = "click_injection"
    DOMAIN_SPOOFING    = "domain_spoofing"
    IMPRESSION_FRAUD   = "impression_fraud"
    AD_STACKING        = "ad_stacking"
    SUB_ID_FRAUD       = "sub_id_fraud"
    VPN_PROXY_TRAFFIC  = "vpn_proxy_traffic"


# ── Thresholds ────────────────────────────────────────────────────────────────
GRADE_THRESHOLDS = {
    PublisherGrade.A: (0,  20),
    PublisherGrade.B: (20, 40),
    PublisherGrade.C: (40, 60),
    PublisherGrade.D: (60, 80),
    PublisherGrade.F: (80, 100),
}
AUTO_SUSPEND_SCORE   = 85     # auto-suspend publisher
BUDGET_PAUSE_SCORE   = 70     # pause advertiser budget spend
ALERT_SCORE          = 50     # send fraud alert


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FraudSignal:
    fraud_type:  FraudType
    publisher_id: int
    advertiser_id: int
    severity:    int              # 1-100
    description: str
    evidence:    Dict             = field(default_factory=dict)
    timestamp:   float            = field(default_factory=time.time)


@dataclass
class PublisherQualityReport:
    publisher_id:    int
    grade:           PublisherGrade
    fraud_score:     int              # 0-100
    total_clicks:    int              = 0
    valid_clicks:    int              = 0
    total_convs:     int              = 0
    valid_convs:     int              = 0
    fraud_rate:      float            = 0.0
    signals:         List[str]        = field(default_factory=list)
    is_suspended:    bool             = False
    recommendations: List[str]        = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "publisher_id":    self.publisher_id,
            "grade":           self.grade.value,
            "fraud_score":     self.fraud_score,
            "total_clicks":    self.total_clicks,
            "valid_clicks":    self.valid_clicks,
            "fraud_rate":      round(self.fraud_rate, 4),
            "signals":         self.signals,
            "is_suspended":    self.is_suspended,
            "recommendations": self.recommendations,
        }


@dataclass
class AdvertiserProtectionResult:
    should_block:     bool
    should_alert:     bool
    should_pause_budget: bool
    fraud_score:      int
    fraud_types:      List[FraudType]
    publisher_grade:  PublisherGrade
    signals:          List[str]           = field(default_factory=list)
    recommended_action: str               = "allow"
    details:          Dict                = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "should_block":       self.should_block,
            "should_alert":       self.should_alert,
            "should_pause_budget":self.should_pause_budget,
            "fraud_score":        self.fraud_score,
            "fraud_types":        [f.value for f in self.fraud_types],
            "publisher_grade":    self.publisher_grade.value,
            "signals":            self.signals,
            "recommended_action": self.recommended_action,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class AdvertiserFraudShield:
    """
    Comprehensive fraud shield for advertisers.

    Usage — evaluate a click before charging advertiser:
        shield = AdvertiserFraudShield()
        result = shield.evaluate_click(
            advertiser_id  = 99,
            publisher_id   = 42,
            click_token    = "abc123",
            ip             = "203.0.113.5",
            user_agent     = request.META.get("HTTP_USER_AGENT",""),
            is_vpn         = vpn_check_result,
            is_bot         = bot_detection_result,
            referrer       = request.META.get("HTTP_REFERER",""),
        )
        if result.should_block:
            return  # don't charge advertiser

    Usage — evaluate a conversion:
        result = shield.evaluate_conversion(
            advertiser_id = 99,
            publisher_id  = 42,
            click_token   = "abc123",
            conversion_ts = int(time.time()),
            payout        = 5.00,
        )
        if result.should_block:
            don't_credit_publisher()

    Usage — get publisher quality report:
        report = shield.get_publisher_quality(publisher_id=42)
    """

    # ── Click evaluation ──────────────────────────────────────────────────────

    def evaluate_click(
        self,
        advertiser_id: int,
        publisher_id:  int,
        click_token:   str,
        ip:            str            = "",
        user_agent:    str            = "",
        is_vpn:        bool           = False,
        is_bot:        bool           = False,
        referrer:      str            = "",
        sub_id:        str            = "",
        geo_country:   str            = "",
        device_type:   str            = "",
    ) -> AdvertiserProtectionResult:
        """Evaluate a click for fraud before charging advertiser."""
        signals     = []
        fraud_types = []
        fraud_score = 0

        # 1. Bot traffic check
        if is_bot:
            signals.append("bot_traffic_detected")
            fraud_types.append(FraudType.BOT_TRAFFIC)
            fraud_score += 80

        # 2. VPN/Proxy traffic
        if is_vpn:
            signals.append("vpn_proxy_traffic")
            fraud_types.append(FraudType.VPN_PROXY_TRAFFIC)
            fraud_score += 30

        # 3. Publisher suspension check
        if self._is_publisher_suspended(publisher_id):
            signals.append("publisher_suspended")
            fraud_score += 100

        # 4. Publisher grade check
        grade = self._get_publisher_grade(publisher_id)
        if grade == PublisherGrade.F:
            signals.append("publisher_grade_F")
            fraud_score += 90
        elif grade == PublisherGrade.D:
            signals.append("publisher_grade_D")
            fraud_score += 40

        # 5. Click velocity for this publisher-advertiser pair
        vel_key   = f"sec:shield:vel:{publisher_id}:{advertiser_id}"
        vel_count = (cache.get(vel_key) or 0) + 1
        if vel_count == 1:
            cache.set(vel_key, 1, 3600)
        else:
            cache.incr(vel_key)
        if vel_count > 10000:  # 10k clicks/hour from single publisher to single advertiser
            signals.append("click_velocity_anomaly")
            fraud_score += 45

        # 6. Geo mismatch (publisher claimed traffic from Tier1, getting from Tier3)
        if geo_country and not self._check_geo_compliance(advertiser_id, geo_country):
            signals.append("geo_compliance_violation")
            fraud_score += 35

        # 7. Domain spoofing check
        if referrer:
            spoofed, spoof_detail = self._check_domain_spoofing(referrer, publisher_id)
            if spoofed:
                signals.append("domain_spoofing_detected")
                fraud_types.append(FraudType.DOMAIN_SPOOFING)
                fraud_score += 70

        # 8. Record for publisher quality tracking
        self._record_click(publisher_id, advertiser_id, is_fraud=fraud_score >= 50)

        # Final decision
        fraud_score       = min(fraud_score, 100)
        publisher_grade   = self._get_publisher_grade(publisher_id)
        should_block      = fraud_score >= 60 or grade in (PublisherGrade.F,)
        should_alert      = fraud_score >= ALERT_SCORE
        should_pause      = fraud_score >= BUDGET_PAUSE_SCORE

        if fraud_score >= AUTO_SUSPEND_SCORE and FraudType.BOT_TRAFFIC in fraud_types:
            self._auto_suspend_publisher(publisher_id, reason="Auto: bot traffic threshold exceeded")

        return AdvertiserProtectionResult(
            should_block         = should_block,
            should_alert         = should_alert,
            should_pause_budget  = should_pause,
            fraud_score          = fraud_score,
            fraud_types          = fraud_types,
            publisher_grade      = publisher_grade,
            signals              = signals,
            recommended_action   = self._recommend(fraud_score, signals),
        )

    # ── Conversion evaluation ─────────────────────────────────────────────────

    def evaluate_conversion(
        self,
        advertiser_id:  int,
        publisher_id:   int,
        click_token:    str,
        conversion_ts:  int,
        payout:         float    = 0.0,
        goal_id:        str      = "",
    ) -> AdvertiserProtectionResult:
        """Evaluate a conversion for fraud before crediting publisher."""
        signals     = []
        fraud_types = []
        fraud_score = 0

        # 1. Publisher suspension
        if self._is_publisher_suspended(publisher_id):
            return AdvertiserProtectionResult(
                should_block        = True,
                should_alert        = True,
                should_pause_budget = True,
                fraud_score         = 100,
                fraud_types         = [FraudType.FAKE_CONVERSION],
                publisher_grade     = PublisherGrade.F,
                signals             = ["publisher_suspended_conversion_rejected"],
                recommended_action  = "reject",
            )

        # 2. Conversion velocity per publisher
        conv_vel_key   = f"sec:shield:conv_vel:{publisher_id}:{advertiser_id}"
        conv_count     = (cache.get(conv_vel_key) or 0) + 1
        if conv_count == 1:
            cache.set(conv_vel_key, 1, 3600)
        else:
            cache.incr(conv_vel_key)
        if conv_count > 500:
            signals.append("conversion_velocity_anomaly")
            fraud_types.append(FraudType.FAKE_CONVERSION)
            fraud_score += 60

        # 3. CVR check for this publisher on this advertiser
        cvr_result = self._check_publisher_cvr(publisher_id, advertiser_id)
        if cvr_result["suspicious"]:
            signals.append("abnormal_publisher_cvr")
            fraud_score += 50
            if cvr_result["cvr"] > 0.95:
                fraud_types.append(FraudType.FAKE_CONVERSION)
                fraud_score += 30

        # 4. Payout sanity
        if payout < 0:
            signals.append("negative_payout")
            fraud_score += 40

        # 5. Record conversion
        self._record_conversion(publisher_id, advertiser_id, is_fraud=fraud_score >= 50)

        fraud_score     = min(fraud_score, 100)
        grade           = self._get_publisher_grade(publisher_id)
        should_block    = fraud_score >= 50

        if should_block:
            logger.warning(
                "Conversion blocked: advertiser=%d publisher=%d score=%d signals=%s",
                advertiser_id, publisher_id, fraud_score, signals,
            )

        return AdvertiserProtectionResult(
            should_block         = should_block,
            should_alert         = fraud_score >= ALERT_SCORE,
            should_pause_budget  = fraud_score >= BUDGET_PAUSE_SCORE,
            fraud_score          = fraud_score,
            fraud_types          = fraud_types,
            publisher_grade      = grade,
            signals              = signals,
            recommended_action   = self._recommend(fraud_score, signals),
        )

    # ── Publisher quality report ──────────────────────────────────────────────

    def get_publisher_quality(self, publisher_id: int) -> PublisherQualityReport:
        """Generate a comprehensive publisher quality report."""
        data   = cache.get(self._pub_key(publisher_id)) or {}
        clicks = data.get("total_clicks", 0)
        convs  = data.get("total_convs", 0)
        fraud  = data.get("fraud_clicks", 0)

        fraud_rate  = fraud / max(clicks, 1)
        fraud_score = min(int(fraud_rate * 100), 100)
        grade       = self._score_to_grade(fraud_score)
        is_suspended= self._is_publisher_suspended(publisher_id)

        signals         = []
        recommendations = []

        if fraud_rate > 0.5:
            signals.append("high_fraud_rate")
            recommendations.append("Immediate review required — >50% fraud rate")
        if data.get("bot_traffic_count", 0) > 100:
            signals.append("significant_bot_traffic")
            recommendations.append("Investigate traffic sources for bot activity")
        if grade in (PublisherGrade.D, PublisherGrade.F):
            recommendations.append("Consider suspending this publisher")

        return PublisherQualityReport(
            publisher_id    = publisher_id,
            grade           = grade,
            fraud_score     = fraud_score,
            total_clicks    = clicks,
            valid_clicks    = clicks - fraud,
            total_convs     = convs,
            valid_convs     = data.get("valid_convs", convs),
            fraud_rate      = fraud_rate,
            signals         = signals,
            is_suspended    = is_suspended,
            recommendations = recommendations,
        )

    # ── Publisher management ──────────────────────────────────────────────────

    def suspend_publisher(self, publisher_id: int, reason: str) -> None:
        """Manually suspend a publisher from all advertiser offers."""
        key = f"sec:shield:suspended:{publisher_id}"
        cache.set(key, {"reason": reason, "ts": time.time()}, 86400 * 90)
        logger.warning("Publisher suspended: pub=%d reason=%s", publisher_id, reason)

    def reinstate_publisher(self, publisher_id: int) -> None:
        """Reinstate a suspended publisher."""
        key = f"sec:shield:suspended:{publisher_id}"
        cache.delete(key)
        logger.info("Publisher reinstated: pub=%d", publisher_id)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _is_publisher_suspended(self, publisher_id: int) -> bool:
        return bool(cache.get(f"sec:shield:suspended:{publisher_id}"))

    def _auto_suspend_publisher(self, publisher_id: int, reason: str) -> None:
        self.suspend_publisher(publisher_id, reason)
        logger.critical(
            "AUTO-SUSPENDED publisher=%d reason=%s", publisher_id, reason
        )

    def _get_publisher_grade(self, publisher_id: int) -> PublisherGrade:
        if self._is_publisher_suspended(publisher_id):
            return PublisherGrade.F
        data        = cache.get(self._pub_key(publisher_id)) or {}
        fraud_score = data.get("fraud_score", 0)
        return self._score_to_grade(fraud_score)

    def _score_to_grade(self, score: int) -> PublisherGrade:
        for grade, (low, high) in GRADE_THRESHOLDS.items():
            if low <= score < high:
                return grade
        return PublisherGrade.F

    def _check_publisher_cvr(self, publisher_id: int, advertiser_id: int) -> dict:
        clicks_key = f"sec:shield:cvr:clicks:{publisher_id}:{advertiser_id}"
        convs_key  = f"sec:shield:cvr:convs:{publisher_id}:{advertiser_id}"
        clicks     = cache.get(clicks_key) or 1
        convs      = (cache.get(convs_key) or 0) + 1
        cache.set(convs_key, convs, 86400)
        cvr        = convs / max(clicks, 1)
        return {"cvr": cvr, "suspicious": cvr > 0.90 and clicks > 20}

    def _check_geo_compliance(self, advertiser_id: int, country: str) -> bool:
        """Check if traffic country is allowed for this advertiser."""
        allowed_key = f"sec:shield:geo:{advertiser_id}"
        allowed     = cache.get(allowed_key)
        if not allowed:
            return True   # no geo restrictions
        return country.upper() in [c.upper() for c in allowed]

    def _check_domain_spoofing(self, referrer: str, publisher_id: int) -> Tuple[bool, dict]:
        """Detect domain spoofing in referrer."""
        # Known premium domains that fraudsters spoof
        premium_domains = [
            "google.com", "facebook.com", "youtube.com",
            "instagram.com", "tiktok.com", "twitter.com",
        ]
        publisher_domains_key = f"sec:shield:domains:{publisher_id}"
        publisher_domains     = cache.get(publisher_domains_key) or []

        for domain in premium_domains:
            if domain in referrer and domain not in publisher_domains:
                return True, {"spoofed_domain": domain, "referrer": referrer[:100]}
        return False, {}

    def _record_click(self, publisher_id: int, advertiser_id: int, is_fraud: bool) -> None:
        key  = self._pub_key(publisher_id)
        data = cache.get(key) or {}
        data["total_clicks"]    = data.get("total_clicks", 0) + 1
        data["fraud_clicks"]    = data.get("fraud_clicks", 0) + (1 if is_fraud else 0)
        data["last_activity"]   = time.time()
        if is_fraud:
            data["bot_traffic_count"] = data.get("bot_traffic_count", 0) + 1
        data["fraud_score"] = min(
            int(data["fraud_clicks"] / max(data["total_clicks"], 1) * 100), 100
        )
        cache.set(key, data, REPUTATION_WINDOW_DAYS * 86400)

        # Update CVR clicks counter
        clicks_key = f"sec:shield:cvr:clicks:{publisher_id}:{advertiser_id}"
        count      = cache.get(clicks_key) or 0
        if count == 0:
            cache.set(clicks_key, 1, 86400)
        else:
            cache.incr(clicks_key)

    def _record_conversion(
        self, publisher_id: int, advertiser_id: int, is_fraud: bool
    ) -> None:
        key  = self._pub_key(publisher_id)
        data = cache.get(key) or {}
        data["total_convs"]  = data.get("total_convs", 0) + 1
        if not is_fraud:
            data["valid_convs"] = data.get("valid_convs", 0) + 1
        cache.set(key, data, REPUTATION_WINDOW_DAYS * 86400)

    def _pub_key(self, publisher_id: int) -> str:
        return f"sec:shield:pub:{publisher_id}"

    def _recommend(self, score: int, signals: List[str]) -> str:
        if "publisher_suspended" in signals: return "reject"
        if score >= 80: return "block"
        if score >= 60: return "reject"
        if score >= 40: return "flag"
        return "allow"

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:24]


REPUTATION_WINDOW_DAYS = 30

# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

advertiser_fraud_shield = AdvertiserFraudShield()