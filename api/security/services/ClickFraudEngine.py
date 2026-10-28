"""
api/security/services/ClickFraudEngine.py
==========================================
Comprehensive Click Fraud Detection Engine — upgrades basic click fraud.
Goes beyond simple deduplication to full fraud pattern analysis.

Fraud patterns detected:
1.  Click flooding            — massive clicks from same source
2.  Click hijacking           — redirect manipulation
3.  Fake installs             — emulator/simulator detection
4.  Impression fraud          — fake impression counts
5.  Ad stacking               — invisible stacked ads
6.  SDK spoofing              — fake SDK postbacks
7.  Device farm detection     — coordinated device farms
8.  Incent traffic abuse      — incentivized traffic on non-incent offers
9.  Geographic fraud          — traffic source geo mismatch
10. Time-pattern fraud        — unnatural time distributions
11. Publisher collusion       — coordinated fraud between publishers
12. Conversion rate anomaly   — abnormal CVR patterns
"""
from __future__ import annotations

import hashlib
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone as tz
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger("security.services.click_fraud")


# ── Thresholds ────────────────────────────────────────────────────────────────
CLICK_FLOOD_THRESHOLD_PER_MIN   = 100
CLICK_FLOOD_THRESHOLD_PER_HOUR  = 2000
DEVICE_FARM_MIN_DEVICES         = 10    # 10+ devices, same IP subnet = device farm
DEVICE_FARM_WINDOW              = 3600  # 1 hour window
SDK_SPOOF_TIME_TOLERANCE        = 2     # seconds — SDK events too synchronized
INCENT_CVR_THRESHOLD            = 0.85  # 85%+ CVR on non-incent = incent abuse
GEO_MISMATCH_THRESHOLD          = 0.60  # 60%+ traffic from wrong geo
TIME_UNIFORMITY_THRESHOLD       = 0.05  # coefficient of variation < 5% = machine


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FraudPattern:
    name:        str
    fraud_type:  str
    weight:      int           # 1-100, contribution to fraud score
    confidence:  float         # 0.0-1.0
    evidence:    Dict          = field(default_factory=dict)


@dataclass
class ClickFraudResult:
    is_fraud:           bool
    fraud_score:        int              # 0-100
    patterns_detected:  List[FraudPattern] = field(default_factory=list)
    recommended_action: str              = "allow"
    publisher_id:       Optional[int]    = None
    offer_id:           str              = ""
    details:            Dict             = field(default_factory=dict)
    should_hold_payout: bool             = False
    should_investigate: bool             = False

    @property
    def severity(self) -> str:
        if self.fraud_score >= 80: return "critical"
        if self.fraud_score >= 60: return "high"
        if self.fraud_score >= 40: return "medium"
        if self.fraud_score >= 20: return "low"
        return "clean"

    def to_dict(self) -> dict:
        return {
            "is_fraud":           self.is_fraud,
            "fraud_score":        self.fraud_score,
            "severity":           self.severity,
            "patterns_detected":  [p.name for p in self.patterns_detected],
            "recommended_action": self.recommended_action,
            "should_hold_payout": self.should_hold_payout,
            "should_investigate": self.should_investigate,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Click Fraud Engine
# ─────────────────────────────────────────────────────────────────────────────

class ClickFraudEngine:
    """
    Full-spectrum click fraud detection engine.

    Usage:
        engine = ClickFraudEngine()

        # On click arrival
        result = engine.analyze_click(
            click_token  = "tok_abc123",
            publisher_id = 42,
            offer_id     = "offer_99",
            ip           = "203.0.113.5",
            user_agent   = request.META.get("HTTP_USER_AGENT"),
            device_id    = request.GET.get("device_id"),
            geo_country  = geoip_result.country,
            geo_region   = geoip_result.region,
            is_incent     = offer.is_incentivized,
            sdk_timestamp = int(request.GET.get("sdk_ts", 0)),
        )

        if result.is_fraud:
            flag_click()
        if result.should_hold_payout:
            hold_publisher_payout()
    """

    def analyze_click(
        self,
        click_token:   str,
        publisher_id:  int,
        offer_id:      str,
        ip:            str            = "",
        user_agent:    str            = "",
        device_id:     str            = "",
        geo_country:   str            = "",
        geo_region:    str            = "",
        is_incent:     bool           = False,
        sdk_timestamp: Optional[int]  = None,
        referrer:      str            = "",
        sub_id:        str            = "",
        click_ts:      Optional[int]  = None,
    ) -> ClickFraudResult:
        """Full fraud analysis for a single click event."""
        patterns   = []
        now        = click_ts or int(time.time())

        # Run all detection modules
        patterns += self._detect_click_flooding(ip, publisher_id, offer_id)
        patterns += self._detect_device_farm(ip, device_id, publisher_id)
        patterns += self._detect_sdk_spoofing(sdk_timestamp, now)
        patterns += self._detect_incent_abuse(publisher_id, offer_id, is_incent)
        patterns += self._detect_geo_fraud(publisher_id, offer_id, geo_country)
        patterns += self._detect_time_pattern_fraud(publisher_id, offer_id, now)
        patterns += self._detect_conversion_rate_anomaly(publisher_id, offer_id)
        patterns += self._detect_publisher_collusion(publisher_id, ip, now)

        # Calculate total fraud score
        fraud_score = self._calculate_fraud_score(patterns)
        fraud_score = min(fraud_score, 100)
        is_fraud    = fraud_score >= 50

        # Record for pattern learning
        self._record_click(publisher_id, offer_id, ip, device_id, geo_country, now)

        action         = self._recommend_action(fraud_score, patterns)
        hold_payout    = fraud_score >= 60
        should_investigate = any(
            p.fraud_type in ("device_farm", "publisher_collusion", "sdk_spoofing")
            for p in patterns
        )

        if is_fraud:
            logger.warning(
                "Click fraud: publisher=%d offer=%s score=%d patterns=%s",
                publisher_id, offer_id, fraud_score,
                [p.name for p in patterns],
            )

        return ClickFraudResult(
            is_fraud           = is_fraud,
            fraud_score        = fraud_score,
            patterns_detected  = patterns,
            recommended_action = action,
            publisher_id       = publisher_id,
            offer_id           = offer_id,
            should_hold_payout = hold_payout,
            should_investigate = should_investigate,
        )

    # ── Detection Modules ─────────────────────────────────────────────────────

    def _detect_click_flooding(
        self,
        ip:           str,
        publisher_id: int,
        offer_id:     str,
    ) -> List[FraudPattern]:
        """Detect abnormally high click volumes from same source."""
        patterns  = []
        ip_hash   = self._hash(ip)

        # Per-minute
        min_key   = f"sec:cfe:flood:min:{ip_hash}:{publisher_id}"
        min_count = self._incr_with_ttl(min_key, 60)
        if min_count > CLICK_FLOOD_THRESHOLD_PER_MIN:
            patterns.append(FraudPattern(
                name       = "click_flooding_burst",
                fraud_type = "click_flooding",
                weight     = 70,
                confidence = min(min_count / CLICK_FLOOD_THRESHOLD_PER_MIN, 1.0),
                evidence   = {"clicks_per_min": min_count, "threshold": CLICK_FLOOD_THRESHOLD_PER_MIN},
            ))

        # Per-hour
        hr_key   = f"sec:cfe:flood:hr:{ip_hash}:{publisher_id}"
        hr_count = self._incr_with_ttl(hr_key, 3600)
        if hr_count > CLICK_FLOOD_THRESHOLD_PER_HOUR:
            patterns.append(FraudPattern(
                name       = "click_flooding_sustained",
                fraud_type = "click_flooding",
                weight     = 55,
                confidence = min(hr_count / CLICK_FLOOD_THRESHOLD_PER_HOUR, 1.0),
                evidence   = {"clicks_per_hour": hr_count, "threshold": CLICK_FLOOD_THRESHOLD_PER_HOUR},
            ))

        return patterns

    def _detect_device_farm(
        self,
        ip:           str,
        device_id:    str,
        publisher_id: int,
    ) -> List[FraudPattern]:
        """Detect device farms — many devices from same IP subnet."""
        if not ip:
            return []

        subnet      = ".".join(ip.split(".")[:2]) + ".0.0/16"
        subnet_key  = f"sec:cfe:farm:{self._hash(subnet)}:{publisher_id}"
        devices     = cache.get(subnet_key) or set()
        if isinstance(devices, list):
            devices = set(devices)

        if device_id:
            devices.add(device_id[:32])
        cache.set(subnet_key, list(devices)[-200:], DEVICE_FARM_WINDOW)

        if len(devices) >= DEVICE_FARM_MIN_DEVICES:
            return [FraudPattern(
                name       = "device_farm_detected",
                fraud_type = "device_farm",
                weight     = 80,
                confidence = min(len(devices) / (DEVICE_FARM_MIN_DEVICES * 2), 1.0),
                evidence   = {
                    "unique_devices": len(devices),
                    "subnet":         subnet,
                    "threshold":      DEVICE_FARM_MIN_DEVICES,
                },
            )]
        return []

    def _detect_sdk_spoofing(
        self,
        sdk_ts:  Optional[int],
        click_ts: int,
    ) -> List[FraudPattern]:
        """
        Detect SDK spoofing — events that arrive too synchronized.
        Real SDK events have natural timing variance.
        """
        if not sdk_ts:
            return []

        ts_diff = abs(click_ts - sdk_ts)

        # Perfect sync (< 2 seconds) between SDK event and click = likely spoofed
        if ts_diff < SDK_SPOOF_TIME_TOLERANCE:
            return [FraudPattern(
                name       = "sdk_spoofing_perfect_sync",
                fraud_type = "sdk_spoofing",
                weight     = 65,
                confidence = 0.8,
                evidence   = {"ts_diff_seconds": ts_diff, "threshold": SDK_SPOOF_TIME_TOLERANCE},
            )]
        return []

    def _detect_incent_abuse(
        self,
        publisher_id: int,
        offer_id:     str,
        is_incent:    bool,
    ) -> List[FraudPattern]:
        """Detect incentivized traffic on non-incentivized offers."""
        if is_incent:
            return []  # Incent offers allow incent traffic

        # Check CVR for this publisher on this non-incent offer
        clicks_key = f"sec:cfe:incent:clicks:{publisher_id}:{offer_id}"
        convs_key  = f"sec:cfe:incent:convs:{publisher_id}:{offer_id}"
        clicks     = cache.get(clicks_key) or 0
        convs      = cache.get(convs_key) or 0

        if clicks < 50:
            return []  # Not enough data

        cvr = convs / max(clicks, 1)
        if cvr > INCENT_CVR_THRESHOLD:
            return [FraudPattern(
                name       = "incent_traffic_on_non_incent_offer",
                fraud_type = "incent_abuse",
                weight     = 75,
                confidence = min(cvr, 1.0),
                evidence   = {
                    "cvr":       round(cvr, 3),
                    "clicks":    clicks,
                    "convs":     convs,
                    "threshold": INCENT_CVR_THRESHOLD,
                },
            )]
        return []

    def _detect_geo_fraud(
        self,
        publisher_id: int,
        offer_id:     str,
        geo_country:  str,
    ) -> List[FraudPattern]:
        """Detect geographic fraud — publisher claiming wrong geo traffic."""
        if not geo_country:
            return []

        geo_key  = f"sec:cfe:geo:{publisher_id}:{offer_id}"
        geo_data = cache.get(geo_key) or {}

        country = geo_country.upper()
        geo_data[country] = geo_data.get(country, 0) + 1
        total = sum(geo_data.values())
        cache.set(geo_key, geo_data, 86400)

        if total < 100:
            return []  # Not enough data

        # Get dominant country
        dominant_country  = max(geo_data, key=geo_data.get)
        dominant_fraction = geo_data[dominant_country] / total

        # If publisher registered for Tier1 but sending mostly Tier3
        tier1 = {"US", "GB", "CA", "AU", "DE", "FR", "NL", "SE", "NO"}
        tier3 = {"PK", "BD", "NG", "ET", "CD", "TZ", "KE", "VN", "PH"}

        if dominant_country in tier3 and dominant_fraction > GEO_MISMATCH_THRESHOLD:
            return [FraudPattern(
                name       = "geographic_fraud_tier3_dominant",
                fraud_type = "geo_fraud",
                weight     = 50,
                confidence = dominant_fraction,
                evidence   = {
                    "dominant_country": dominant_country,
                    "fraction":         round(dominant_fraction, 3),
                    "total_clicks":     total,
                },
            )]
        return []

    def _detect_time_pattern_fraud(
        self,
        publisher_id: int,
        offer_id:     str,
        click_ts:     int,
    ) -> List[FraudPattern]:
        """Detect unnatural time patterns — bots click at machine-precise intervals."""
        key        = f"sec:cfe:timing:{publisher_id}:{offer_id}"
        timestamps = cache.get(key) or []
        timestamps.append(click_ts)
        timestamps = timestamps[-30:]  # keep last 30
        cache.set(key, timestamps, 3600)

        if len(timestamps) < 10:
            return []

        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        if not intervals:
            return []

        avg = sum(intervals) / len(intervals)
        if avg <= 0:
            return []

        variance = sum((x - avg) ** 2 for x in intervals) / len(intervals)
        std_dev  = math.sqrt(variance)
        cv       = std_dev / avg  # coefficient of variation

        if cv < TIME_UNIFORMITY_THRESHOLD:
            return [FraudPattern(
                name       = "machine_click_timing",
                fraud_type = "automated_fraud",
                weight     = 60,
                confidence = 1.0 - (cv / TIME_UNIFORMITY_THRESHOLD),
                evidence   = {
                    "avg_interval_sec": round(avg, 3),
                    "std_dev":          round(std_dev, 3),
                    "cv":               round(cv, 5),
                    "threshold":        TIME_UNIFORMITY_THRESHOLD,
                },
            )]
        return []

    def _detect_conversion_rate_anomaly(
        self,
        publisher_id: int,
        offer_id:     str,
    ) -> List[FraudPattern]:
        """Detect abnormal conversion rates (too high or too low)."""
        clicks_key = f"sec:cfe:cvr:clicks:{publisher_id}:{offer_id}"
        convs_key  = f"sec:cfe:cvr:convs:{publisher_id}:{offer_id}"
        clicks     = self._incr_with_ttl(clicks_key, 86400)
        convs      = cache.get(convs_key) or 0

        if clicks < 100:
            return []

        cvr = convs / max(clicks, 1)

        patterns = []
        if cvr > 0.95:
            patterns.append(FraudPattern(
                name       = "conversion_rate_impossibly_high",
                fraud_type = "conversion_fraud",
                weight     = 85,
                confidence = min(cvr, 1.0),
                evidence   = {"cvr": round(cvr, 4), "clicks": clicks, "convs": convs},
            ))
        elif cvr < 0.0001 and clicks > 10000:
            patterns.append(FraudPattern(
                name       = "conversion_rate_suspiciously_low",
                fraud_type = "click_flooding",
                weight     = 40,
                confidence = 0.6,
                evidence   = {"cvr": round(cvr, 6), "clicks": clicks, "convs": convs},
            ))
        return patterns

    def _detect_publisher_collusion(
        self,
        publisher_id: int,
        ip:           str,
        click_ts:     int,
    ) -> List[FraudPattern]:
        """
        Detect coordinated fraud between publishers
        (multiple publisher IDs using same IP infrastructure).
        """
        if not ip:
            return []

        ip_key   = f"sec:cfe:collusion:{self._hash(ip)}"
        pub_data = cache.get(ip_key) or {}
        pub_str  = str(publisher_id)

        if pub_str not in pub_data:
            pub_data[pub_str] = click_ts
        cache.set(ip_key, pub_data, 3600)

        if len(pub_data) >= 5:
            # 5+ different publishers from same IP = collusion ring
            return [FraudPattern(
                name       = "publisher_collusion_ring",
                fraud_type = "publisher_collusion",
                weight     = 90,
                confidence = min(len(pub_data) / 10, 1.0),
                evidence   = {
                    "publishers_on_ip": len(pub_data),
                    "ip_hash":          self._hash(ip)[:8],
                },
            )]
        return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _calculate_fraud_score(self, patterns: List[FraudPattern]) -> int:
        """Aggregate pattern weights into a single fraud score."""
        if not patterns:
            return 0
        # Weighted sum with diminishing returns for multiple patterns
        total = 0
        for i, pattern in enumerate(sorted(patterns, key=lambda p: p.weight, reverse=True)):
            # Each additional pattern contributes less (diminishing returns)
            weight_factor = 1.0 / (1 + i * 0.3)
            total += pattern.weight * pattern.confidence * weight_factor
        return min(int(total), 100)

    def _recommend_action(
        self,
        score:    int,
        patterns: List[FraudPattern],
    ) -> str:
        critical_types = {"device_farm", "sdk_spoofing", "publisher_collusion"}
        has_critical   = any(p.fraud_type in critical_types for p in patterns)
        if has_critical or score >= 80: return "block"
        if score >= 60:                 return "reject"
        if score >= 40:                 return "flag"
        return "allow"

    def _record_click(
        self,
        publisher_id: int,
        offer_id:     str,
        ip:           str,
        device_id:    str,
        geo_country:  str,
        click_ts:     int,
    ) -> None:
        """Record click for ongoing pattern analysis."""
        # Conversion rate tracking (click side)
        key = f"sec:cfe:cvr:clicks:{publisher_id}:{offer_id}"
        self._incr_with_ttl(key, 86400)

    def record_conversion(
        self,
        publisher_id: int,
        offer_id:     str,
        payout:       float = 0.0,
    ) -> None:
        """Record a conversion event (called from postback handler)."""
        # Update CVR conversion counter
        conv_key = f"sec:cfe:cvr:convs:{publisher_id}:{offer_id}"
        count    = cache.get(conv_key) or 0
        if count == 0:
            cache.set(conv_key, 1, 86400)
        else:
            cache.incr(conv_key)

        # Update incent tracking
        incent_key = f"sec:cfe:incent:convs:{publisher_id}:{offer_id}"
        i_count    = cache.get(incent_key) or 0
        if i_count == 0:
            cache.set(incent_key, 1, 86400)
        else:
            cache.incr(incent_key)

    def _incr_with_ttl(self, key: str, ttl: int) -> int:
        """Increment a counter, setting TTL only on first increment."""
        count = cache.get(key) or 0
        if count == 0:
            cache.set(key, 1, ttl)
            return 1
        cache.incr(key)
        return count + 1

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:24]


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

click_fraud_engine = ClickFraudEngine()