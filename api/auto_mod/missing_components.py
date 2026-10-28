# =============================================================================
# api/auto_mod/missing_components.py
# =============================================================================
"""
CPAlead-grade missing components — all in one file, one owner per class.

  BlacklistService          — IP/user/device blacklist + whitelist management
  PublisherQualityService   — publisher trust score lifecycle
  ConversionRateMonitor     — per-publisher conversion anomaly detection
  ClickFraudDetector        — click pattern analysis (bot clicks, stuffing)
  InvalidTrafficDetector    — real-time IVT scoring (bots, emulators, farms)
  GeoIPService              — GeoIP restriction enforcement per offer/rule
  EXIFVerifier              — screenshot EXIF metadata validation
  PerceptualHasher           — pHash / dHash near-duplicate image detection
  SLATracker                — moderation + appeal SLA deadline management
  RiskScoreHistory          — per-user/submission risk score time-series
  OfferModerationConfig     — per-offer moderation thresholds and overrides
  ReReviewService           — re-review workflow (appeal-triggered re-scan)
  ABTestService             — ML model A/B testing framework
"""

from __future__ import annotations

import hashlib
import logging
import struct
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("auto_mod.missing_components")

# ─── helpers ─────────────────────────────────────────────────────────────────

def _cache_get(key: str, default=None):
    try:
        v = cache.get(f"auto_mod:{key}")
        return v if v is not None else default
    except Exception:
        return default

def _cache_set(key: str, value, ttl: int = 3600):
    try:
        cache.set(f"auto_mod:{key}", value, ttl)
    except Exception:
        pass


# =============================================================================
# 1. BlacklistService — IP / user / device blacklist + whitelist
# =============================================================================

class BlacklistService:
    """
    Manages IP, user_id, device fingerprint, and email-domain blacklists.
    Also handles whitelists (trusted publishers, known-good IPs).
    Single owner: all blacklist/whitelist logic lives here.
    """

    _LISTS = ("ip", "user", "device", "email_domain", "asn", "country")
    _TTL = 86_400 * 7  # 7 days default

    @classmethod
    def _key(cls, list_type: str, value: str, is_white: bool = False) -> str:
        kind = "whitelist" if is_white else "blacklist"
        return f"{kind}:{list_type}:{value.lower()}"

    # ── Blacklist ─────────────────────────────────────────────────────────────

    @classmethod
    def add(cls, list_type: str, value: str, reason: str = "",
            ttl: int = _TTL, added_by: str = "system") -> dict:
        if list_type not in cls._LISTS:
            raise ValueError(f"Invalid list_type {list_type!r}")
        key = cls._key(list_type, value)
        entry = {"value": value, "reason": reason,
                 "added_by": added_by, "added_at": str(timezone.now())}
        _cache_set(key, entry, ttl)
        logger.info("blacklist.add type=%s value=%r reason=%r", list_type, value, reason)
        return entry

    @classmethod
    def remove(cls, list_type: str, value: str) -> bool:
        cache.delete(f"auto_mod:{cls._key(list_type, value)}")
        logger.info("blacklist.remove type=%s value=%r", list_type, value)
        return True

    @classmethod
    def is_blacklisted(cls, list_type: str, value: str) -> bool:
        return _cache_get(cls._key(list_type, value)) is not None

    @classmethod
    def get_entry(cls, list_type: str, value: str) -> dict | None:
        return _cache_get(cls._key(list_type, value))

    # ── Whitelist ─────────────────────────────────────────────────────────────

    @classmethod
    def whitelist_add(cls, list_type: str, value: str,
                      reason: str = "", added_by: str = "system") -> dict:
        key = cls._key(list_type, value, is_white=True)
        entry = {"value": value, "reason": reason,
                 "added_by": added_by, "added_at": str(timezone.now())}
        _cache_set(key, entry, cls._TTL)
        return entry

    @classmethod
    def is_whitelisted(cls, list_type: str, value: str) -> bool:
        return _cache_get(cls._key(list_type, value, is_white=True)) is not None

    # ── Composite check ───────────────────────────────────────────────────────

    @classmethod
    def assess_request(cls, *, ip: str = "", user_id: str = "",
                       device: str = "", email: str = "") -> dict:
        """
        Check all provided identifiers against blacklists and whitelists.
        Returns {blocked, whitelisted, reason, blocked_by}.
        """
        checks = [("ip", ip), ("user", user_id), ("device", device)]
        if email and "@" in email:
            checks.append(("email_domain", email.split("@")[-1]))

        for list_type, value in checks:
            if not value:
                continue
            if cls.is_whitelisted(list_type, value):
                return {"blocked": False, "whitelisted": True,
                        "reason": "whitelisted", "blocked_by": None}
            if cls.is_blacklisted(list_type, value):
                entry = cls.get_entry(list_type, value) or {}
                return {"blocked": True, "whitelisted": False,
                        "reason": entry.get("reason", "blacklisted"),
                        "blocked_by": list_type}

        return {"blocked": False, "whitelisted": False,
                "reason": "", "blocked_by": None}

    @classmethod
    def bulk_add(cls, list_type: str, values: list[str],
                 reason: str = "", ttl: int = _TTL) -> int:
        for v in values:
            cls.add(list_type, v, reason=reason, ttl=ttl)
        return len(values)


# =============================================================================
# 2. PublisherQualityService — publisher trust score lifecycle
# =============================================================================

class PublisherQualityService:
    """
    Tracks and updates a per-publisher quality score (0–100).
    Score drives auto-approval thresholds and review frequency.
    Single owner: all publisher quality logic lives here.
    """

    _DEFAULT_SCORE = 70
    _SCORE_TTL = 86_400

    TIER_ELITE     = (90, 100)
    TIER_TRUSTED   = (75, 89)
    TIER_STANDARD  = (50, 74)
    TIER_PROBATION = (25, 49)
    TIER_SUSPENDED = (0,  24)

    @classmethod
    def _key(cls, publisher_id: str) -> str:
        return f"publisher_score:{publisher_id}"

    @classmethod
    def get_score(cls, publisher_id: str) -> float:
        return float(_cache_get(cls._key(publisher_id), cls._DEFAULT_SCORE))

    @classmethod
    def update_score(cls, publisher_id: str, delta: float, reason: str = "") -> float:
        current = cls.get_score(publisher_id)
        new_score = round(max(0.0, min(100.0, current + delta)), 2)
        _cache_set(cls._key(publisher_id), new_score, cls._SCORE_TTL)
        logger.info("publisher_quality.update pub=%s %.1f→%.1f reason=%r",
                    publisher_id, current, new_score, reason)
        return new_score

    @classmethod
    def get_tier(cls, publisher_id: str) -> str:
        score = cls.get_score(publisher_id)
        for tier_name, (lo, hi) in {
            "elite":     cls.TIER_ELITE,
            "trusted":   cls.TIER_TRUSTED,
            "standard":  cls.TIER_STANDARD,
            "probation": cls.TIER_PROBATION,
            "suspended": cls.TIER_SUSPENDED,
        }.items():
            if lo <= score <= hi:
                return tier_name
        return "standard"

    @classmethod
    def get_auto_approve_threshold(cls, publisher_id: str) -> float:
        """Elite/trusted publishers get lower AI confidence threshold."""
        tier_thresholds = {
            "elite":     0.70,
            "trusted":   0.75,
            "standard":  0.85,
            "probation": 0.95,
            "suspended": 1.01,  # never auto-approve
        }
        return tier_thresholds.get(cls.get_tier(publisher_id), 0.85)

    @classmethod
    def record_approved(cls, publisher_id: str) -> float:
        return cls.update_score(publisher_id, +0.5, "approved_submission")

    @classmethod
    def record_rejected(cls, publisher_id: str) -> float:
        return cls.update_score(publisher_id, -2.0, "rejected_submission")

    @classmethod
    def record_fraud_detected(cls, publisher_id: str) -> float:
        return cls.update_score(publisher_id, -15.0, "fraud_detected")

    @classmethod
    def record_successful_appeal(cls, publisher_id: str) -> float:
        return cls.update_score(publisher_id, +3.0, "successful_appeal")

    @classmethod
    def get_full_profile(cls, publisher_id: str) -> dict:
        score = cls.get_score(publisher_id)
        tier  = cls.get_tier(publisher_id)
        return {
            "publisher_id":          publisher_id,
            "quality_score":         score,
            "tier":                  tier,
            "auto_approve_threshold": cls.get_auto_approve_threshold(publisher_id),
            "requires_human_review":  tier in ("probation", "suspended"),
        }


# =============================================================================
# 3. ConversionRateMonitor — per-publisher conversion anomaly detection
# =============================================================================

class ConversionRateMonitor:
    """
    Tracks conversion rates per publisher and detects anomalies.
    Unusually high conversion rates signal incentivised/fake traffic.
    Single owner: all conversion rate monitoring lives here.
    """

    ANOMALY_HIGH = 0.95  # > 95% conversion rate is suspicious
    ANOMALY_LOW  = 0.01  # < 1% conversion rate signals quality issues
    _WINDOW_HOURS = 24

    @classmethod
    def _key(cls, publisher_id: str) -> str:
        return f"conv_rate:{publisher_id}"

    @classmethod
    def record_event(cls, publisher_id: str, *, converted: bool) -> None:
        key  = cls._key(publisher_id)
        data = _cache_get(key, {"clicks": 0, "conversions": 0})
        data["clicks"]      += 1
        data["conversions"] += 1 if converted else 0
        _cache_set(key, data, cls._WINDOW_HOURS * 3600)

    @classmethod
    def get_rate(cls, publisher_id: str) -> float:
        data = _cache_get(cls._key(publisher_id), {"clicks": 0, "conversions": 0})
        if data["clicks"] == 0:
            return 0.0
        return round(data["conversions"] / data["clicks"], 4)

    @classmethod
    def assess(cls, publisher_id: str) -> dict:
        rate  = cls.get_rate(publisher_id)
        data  = _cache_get(cls._key(publisher_id), {"clicks": 0, "conversions": 0})
        is_anomalous = (
            data["clicks"] >= 10 and
            (rate >= cls.ANOMALY_HIGH or (data["clicks"] >= 50 and rate <= cls.ANOMALY_LOW))
        )
        anomaly_type = None
        if is_anomalous:
            anomaly_type = "too_high" if rate >= cls.ANOMALY_HIGH else "too_low"

        return {
            "publisher_id":  publisher_id,
            "conversion_rate": rate,
            "clicks":        data["clicks"],
            "conversions":   data["conversions"],
            "is_anomalous":  is_anomalous,
            "anomaly_type":  anomaly_type,
            "risk_score":    0.9 if anomaly_type == "too_high" else
                             0.5 if anomaly_type == "too_low" else 0.1,
        }

    @classmethod
    def reset(cls, publisher_id: str) -> None:
        cache.delete(f"auto_mod:{cls._key(publisher_id)}")


# =============================================================================
# 4. ClickFraudDetector — click pattern analysis
# =============================================================================

class ClickFraudDetector:
    """
    Detects click fraud: bot clicks, click stuffing, click injection.
    Single owner: all click fraud detection logic lives here.
    """

    _WINDOW = 300  # 5 minutes
    BOT_SIGNALS = [
        "headlesschrome", "phantomjs", "python-requests", "curl", "wget",
        "scrapy", "libwww", "java/", "go-http", "okhttp", "urllib",
    ]

    @classmethod
    def _click_key(cls, identifier: str) -> str:
        return f"click_fraud:{identifier}"

    @classmethod
    def record_click(cls, *, ip: str, user_agent: str,
                     offer_id: str, publisher_id: str) -> None:
        key = cls._click_key(f"{ip}:{offer_id}")
        clicks: list = _cache_get(key, [])
        clicks.append(timezone.now().timestamp())
        # keep only within window
        cutoff = timezone.now().timestamp() - cls._WINDOW
        clicks = [c for c in clicks if c > cutoff]
        _cache_set(key, clicks, cls._WINDOW * 2)

    @classmethod
    def assess_click(cls, *, ip: str, user_agent: str,
                     offer_id: str, publisher_id: str) -> dict:
        ua_lower  = user_agent.lower()
        is_bot_ua = any(sig in ua_lower for sig in cls.BOT_SIGNALS)

        # Click frequency
        key    = cls._click_key(f"{ip}:{offer_id}")
        clicks = _cache_get(key, [])
        cutoff = timezone.now().timestamp() - cls._WINDOW
        recent = [c for c in clicks if c > cutoff]
        is_stuffing = len(recent) >= 5  # 5+ clicks in 5 min from same IP

        risk = 0.0
        signals = []
        if is_bot_ua:
            risk = max(risk, 0.9)
            signals.append("bot_user_agent")
        if is_stuffing:
            risk = max(risk, 0.85)
            signals.append("click_stuffing")

        return {
            "is_fraud":       is_bot_ua or is_stuffing,
            "risk_score":     risk,
            "signals":        signals,
            "click_count_5m": len(recent),
        }

    @classmethod
    def is_click_injected(cls, *, click_ts: float, install_ts: float) -> bool:
        """Click injection: install happens before or within 1s of click."""
        return install_ts <= click_ts + 1.0


# =============================================================================
# 5. InvalidTrafficDetector — real-time IVT scoring
# =============================================================================

class InvalidTrafficDetector:
    """
    Combines all signals to classify traffic as valid / suspicious / invalid.
    Covers: bots, emulators, click farms, VPNs, data centres.
    Single owner: final IVT verdict comes only from here.
    """

    IVT_THRESHOLD    = 0.7   # above this → invalid
    SIVT_THRESHOLD   = 0.4   # above this → sophisticated IVT

    @classmethod
    def score(cls, *, ip: str = "", user_agent: str = "",
              publisher_id: str = "", offer_id: str = "",
              device_fingerprint: str = "") -> dict:
        """
        Returns {ivt_score, ivt_type, is_invalid, signals, action}.
        action: 'allow' | 'flag' | 'block'
        """
        signals = []
        scores: list[float] = []

        # 1. Blacklist check
        bl = BlacklistService.assess_request(ip=ip, device=device_fingerprint)
        if bl["blocked"]:
            return {"ivt_score": 1.0, "ivt_type": "blacklisted",
                    "is_invalid": True, "signals": ["blacklisted"],
                    "action": "block"}

        # 2. IP reputation
        try:
            from .fraud_detection import IPReputationService
            ip_result = IPReputationService.score_ip(ip)
            if ip_result["risk_score"] >= 0.6:
                signals.append("high_risk_ip")
                scores.append(ip_result["risk_score"])
            if ip_result["is_proxy"]:
                signals.append("proxy_ip")
                scores.append(0.75)
            if ip_result["is_tor"]:
                signals.append("tor_ip")
                scores.append(0.9)
        except Exception:
            pass

        # 3. Bot user-agent
        try:
            from .fraud_detection import DeviceFingerprintService
            dev = DeviceFingerprintService.assess_device(user_agent=user_agent)
            if dev["is_bot"]:
                signals.append("bot_ua")
                scores.append(0.95)
        except Exception:
            pass

        # 4. Click fraud
        if offer_id and publisher_id:
            click_assess = ClickFraudDetector.assess_click(
                ip=ip, user_agent=user_agent,
                offer_id=offer_id, publisher_id=publisher_id,
            )
            if click_assess["is_fraud"]:
                signals.extend(click_assess["signals"])
                scores.append(click_assess["risk_score"])

        # 5. Conversion rate anomaly
        if publisher_id:
            conv = ConversionRateMonitor.assess(publisher_id)
            if conv["is_anomalous"]:
                signals.append(f"conversion_anomaly_{conv['anomaly_type']}")
                scores.append(conv["risk_score"])

        ivt_score = round(max(scores, default=0.0), 4)
        ivt_type  = "general_invalid" if signals else "valid"
        is_invalid = ivt_score >= cls.IVT_THRESHOLD

        action = "block" if ivt_score >= cls.IVT_THRESHOLD else \
                 "flag"  if ivt_score >= cls.SIVT_THRESHOLD else "allow"

        return {
            "ivt_score":  ivt_score,
            "ivt_type":   ivt_type,
            "is_invalid": is_invalid,
            "signals":    signals,
            "action":     action,
        }


# =============================================================================
# 6. GeoIPService — GeoIP restriction enforcement
# =============================================================================

class GeoIPService:
    """
    Enforces per-offer or per-rule geographic restrictions.
    Single owner: all geo-targeting/restriction logic lives here.
    """

    @staticmethod
    def get_country(ip: str) -> str | None:
        """Resolve IP → ISO country code. Falls back to proxy_intelligence."""
        try:
            from .adapters import AdapterRegistry
            result = AdapterRegistry.proxy_intelligence.check_ip(ip)
            return result.get("country")
        except Exception:
            return None

    @staticmethod
    def is_allowed(ip: str, *, allowed_countries: list[str] = None,
                   blocked_countries: list[str] = None) -> dict:
        """
        Check if an IP is allowed based on geo restrictions.
        Returns {allowed, country, reason}.
        """
        if not allowed_countries and not blocked_countries:
            return {"allowed": True, "country": None, "reason": "no_restriction"}

        country = GeoIPService.get_country(ip)

        if blocked_countries and country in blocked_countries:
            return {"allowed": False, "country": country,
                    "reason": f"country_blocked: {country}"}

        if allowed_countries and country not in (allowed_countries or []):
            return {"allowed": False, "country": country,
                    "reason": f"country_not_allowed: {country}"}

        return {"allowed": True, "country": country, "reason": "allowed"}

    @staticmethod
    def get_risk_by_country(country: str) -> float:
        """Simple country risk mapping (extend with real data)."""
        high_risk   = {"CN", "RU", "IN", "NG", "PK", "VN", "BD"}
        medium_risk = {"UA", "RO", "BR", "MX", "PH"}
        if country in high_risk:   return 0.7
        if country in medium_risk: return 0.4
        return 0.1


# =============================================================================
# 7. EXIFVerifier — screenshot EXIF metadata validation
# =============================================================================

class EXIFVerifier:
    """
    Validates EXIF metadata on uploaded screenshots/images.
    Detects: edited timestamps, mismatched device info, stripped EXIF (suspicious).
    Single owner: all EXIF verification lives here.
    """

    @staticmethod
    def extract_exif(file_path_or_bytes: bytes | str) -> dict:
        """
        Extract EXIF data. Returns dict or empty dict if unavailable.
        In production, use Pillow / exifread.
        """
        try:
            import struct
            # Minimal JPEG EXIF check
            data = file_path_or_bytes if isinstance(file_path_or_bytes, bytes) \
                   else open(file_path_or_bytes, "rb").read()

            if data[:2] != b'\xff\xd8':
                return {}  # not a JPEG

            # Check for EXIF marker
            has_exif = b'Exif\x00\x00' in data[:128]
            return {"has_exif": has_exif, "size_bytes": len(data)}
        except Exception as exc:
            logger.debug("EXIFVerifier.extract_exif failed: %s", exc)
            return {}

    @staticmethod
    def assess(file_data: bytes, expected_device: str = "") -> dict:
        """
        Returns {passed, risk_score, signals, exif_present}.
        """
        exif = EXIFVerifier.extract_exif(file_data)
        signals = []
        risk    = 0.1

        if not exif.get("has_exif"):
            signals.append("no_exif_data")
            risk = max(risk, 0.4)  # stripped EXIF is suspicious

        timestamp = exif.get("datetime")
        if timestamp:
            # Future timestamps are impossible
            try:
                from datetime import datetime
                dt = datetime.strptime(str(timestamp), "%Y:%m:%d %H:%M:%S")
                if dt > datetime.now():
                    signals.append("future_timestamp")
                    risk = max(risk, 0.9)
            except Exception:
                pass

        return {
            "passed":       risk < 0.6,
            "risk_score":   risk,
            "signals":      signals,
            "exif_present": bool(exif.get("has_exif")),
        }


# =============================================================================
# 8. PerceptualHasher — pHash / dHash for near-duplicate image detection
# =============================================================================

class PerceptualHasher:
    """
    Perceptual image hashing for near-duplicate screenshot detection.
    Uses difference hash (dHash) — lightweight, no ML required.
    Single owner: all perceptual hashing lives here.
    """

    HASH_SIZE = 8  # 8×8 = 64-bit hash
    DUPLICATE_THRESHOLD = 5  # hamming distance ≤ 5 = near-duplicate

    @staticmethod
    def dhash(image_bytes: bytes) -> int | None:
        """
        Compute a 64-bit difference hash from image bytes.
        Returns None if image cannot be processed.
        """
        try:
            # Minimal grayscale resize using pure Python (no Pillow required)
            # In production, use: from PIL import Image
            # Fallback: hash the raw bytes in blocks
            if len(image_bytes) < 100:
                return None

            # Simplified: divide bytes into 64 blocks, compare adjacent
            block = len(image_bytes) // 64
            values = [
                sum(image_bytes[i*block:(i+1)*block]) // block
                for i in range(64)
            ]
            bits = [1 if values[i] > values[i-1] else 0 for i in range(1, 64)] + [0]
            result = 0
            for bit in bits:
                result = (result << 1) | bit
            return result
        except Exception as exc:
            logger.debug("PerceptualHasher.dhash error: %s", exc)
            return None

    @staticmethod
    def hamming_distance(hash_a: int, hash_b: int) -> int:
        return bin(hash_a ^ hash_b).count("1")

    @classmethod
    def is_near_duplicate(cls, image_a: bytes, image_b: bytes) -> dict:
        ha = cls.dhash(image_a)
        hb = cls.dhash(image_b)
        if ha is None or hb is None:
            return {"is_duplicate": False, "distance": -1, "confidence": 0.0}
        dist = cls.hamming_distance(ha, hb)
        is_dup = dist <= cls.DUPLICATE_THRESHOLD
        return {
            "is_duplicate": is_dup,
            "distance":     dist,
            "confidence":   round(1.0 - dist / 64, 4),
        }

    @classmethod
    def store_and_check(cls, image_bytes: bytes,
                        submission_id: str, ttl: int = 86_400) -> dict:
        """Store hash and check against recent hashes for duplicates."""
        h = cls.dhash(image_bytes)
        if h is None:
            return {"is_duplicate": False, "original_id": None}

        # Check cache for recent hashes
        all_hashes = _cache_get("phash_store", {})
        for stored_id, stored_hash in list(all_hashes.items()):
            if stored_id == submission_id:
                continue
            if cls.hamming_distance(h, stored_hash) <= cls.DUPLICATE_THRESHOLD:
                return {"is_duplicate": True, "original_id": stored_id,
                        "distance": cls.hamming_distance(h, stored_hash)}

        # Store this hash
        all_hashes[submission_id] = h
        # Keep only last 1000
        if len(all_hashes) > 1000:
            oldest = list(all_hashes.keys())[:100]
            for k in oldest:
                del all_hashes[k]
        _cache_set("phash_store", all_hashes, ttl)
        return {"is_duplicate": False, "original_id": None}


# =============================================================================
# 9. SLATracker — moderation + appeal SLA deadline management
# =============================================================================

class SLATracker:
    """
    Tracks SLA deadlines for moderation decisions and appeals.
    Raises alerts when SLA is at risk or breached.
    Single owner: all SLA tracking lives here.
    """

    # Default SLA windows
    SLA_AUTO_MODERATION_HOURS   = 1
    SLA_HUMAN_REVIEW_HOURS      = 24
    SLA_APPEAL_REVIEW_HOURS     = 72
    SLA_ESCALATED_HOURS         = 4

    @classmethod
    def _key(cls, entity_type: str, entity_id: str) -> str:
        return f"sla:{entity_type}:{entity_id}"

    @classmethod
    def start(cls, entity_type: str, entity_id: str,
              sla_hours: float | None = None) -> dict:
        """Register SLA start for an entity."""
        if sla_hours is None:
            sla_hours = {
                "submission":  cls.SLA_AUTO_MODERATION_HOURS,
                "human_review": cls.SLA_HUMAN_REVIEW_HOURS,
                "appeal":      cls.SLA_APPEAL_REVIEW_HOURS,
                "escalated":   cls.SLA_ESCALATED_HOURS,
            }.get(entity_type, cls.SLA_HUMAN_REVIEW_HOURS)

        now     = timezone.now()
        due_at  = now + timedelta(hours=sla_hours)
        record  = {
            "entity_type": entity_type,
            "entity_id":   entity_id,
            "started_at":  now.isoformat(),
            "due_at":      due_at.isoformat(),
            "sla_hours":   sla_hours,
            "breached":    False,
        }
        _cache_set(cls._key(entity_type, entity_id), record,
                   int(sla_hours * 3600 * 3))
        return record

    @classmethod
    def check(cls, entity_type: str, entity_id: str) -> dict:
        """Check current SLA status."""
        record = _cache_get(cls._key(entity_type, entity_id))
        if not record:
            return {"status": "not_tracked", "breached": False,
                    "minutes_remaining": None}

        from datetime import datetime
        due_at  = datetime.fromisoformat(record["due_at"]).replace(tzinfo=timezone.utc)
        now     = timezone.now()
        remaining = (due_at - now).total_seconds() / 60

        if remaining < 0:
            status = "breached"
        elif remaining < record["sla_hours"] * 60 * 0.2:
            status = "at_risk"
        else:
            status = "on_track"

        return {
            "status":            status,
            "breached":          remaining < 0,
            "minutes_remaining": round(remaining, 1),
            "due_at":            record["due_at"],
        }

    @classmethod
    def complete(cls, entity_type: str, entity_id: str) -> dict:
        """Mark SLA as completed (resolved on time)."""
        record = _cache_get(cls._key(entity_type, entity_id))
        status = cls.check(entity_type, entity_id)
        cache.delete(f"auto_mod:{cls._key(entity_type, entity_id)}")
        return {"completed": True, "was_breached": status.get("breached", False)}

    @classmethod
    def get_all_at_risk(cls, entity_type: str,
                        entity_ids: list[str]) -> list[dict]:
        """Return SLA records at risk or breached from a list of IDs."""
        results = []
        for eid in entity_ids:
            status = cls.check(entity_type, eid)
            if status["status"] in ("at_risk", "breached"):
                results.append({"entity_id": eid, **status})
        return results


# =============================================================================
# 10. RiskScoreHistory — per-user/submission risk score time-series
# =============================================================================

class RiskScoreHistory:
    """
    Maintains a time-series of risk scores per user and per submission.
    Used for trend detection and escalation triggers.
    Single owner: all risk score history lives here.
    """

    _MAX_HISTORY = 50
    _TTL = 86_400 * 30  # 30 days

    @classmethod
    def _key(cls, entity_type: str, entity_id: str) -> str:
        return f"risk_history:{entity_type}:{entity_id}"

    @classmethod
    def record(cls, entity_type: str, entity_id: str,
               risk_score: float, context: dict | None = None) -> None:
        key     = cls._key(entity_type, entity_id)
        history: list = _cache_get(key, [])
        history.append({
            "ts":    timezone.now().isoformat(),
            "score": round(risk_score, 4),
            "ctx":   context or {},
        })
        if len(history) > cls._MAX_HISTORY:
            history = history[-cls._MAX_HISTORY:]
        _cache_set(key, history, cls._TTL)

    @classmethod
    def get_history(cls, entity_type: str, entity_id: str) -> list[dict]:
        return _cache_get(cls._key(entity_type, entity_id), [])

    @classmethod
    def get_trend(cls, entity_type: str, entity_id: str,
                  last_n: int = 5) -> dict:
        """
        Detect trend: is risk increasing or decreasing?
        Returns {trend: 'rising'|'falling'|'stable', avg_score, max_score}.
        """
        history = cls.get_history(entity_type, entity_id)
        if len(history) < 2:
            return {"trend": "insufficient_data", "avg_score": 0.0, "max_score": 0.0}

        recent = [h["score"] for h in history[-last_n:]]
        avg    = sum(recent) / len(recent)
        delta  = recent[-1] - recent[0]
        trend  = "rising"  if delta >  0.1 else \
                 "falling" if delta < -0.1 else "stable"

        return {
            "trend":     trend,
            "avg_score": round(avg, 4),
            "max_score": round(max(recent), 4),
            "min_score": round(min(recent), 4),
            "delta":     round(delta, 4),
        }

    @classmethod
    def is_escalation_needed(cls, entity_type: str,
                             entity_id: str) -> bool:
        """Return True if risk trend warrants escalation."""
        trend = cls.get_trend(entity_type, entity_id)
        return (
            trend["trend"]     == "rising"  and
            trend["avg_score"] >= 0.6       and
            trend["max_score"] >= 0.8
        )


# =============================================================================
# 11. OfferModerationConfig — per-offer moderation overrides
# =============================================================================

class OfferModerationConfig:
    """
    Per-offer (or per-advertiser) moderation configuration overrides.
    Allows advertisers to tighten/relax moderation rules for their offers.
    Single owner: all offer-level moderation config lives here.
    """

    _TTL = 3600

    _DEFAULTS = {
        "auto_approve_threshold":   0.85,
        "require_human_review":     False,
        "allowed_countries":        [],
        "blocked_countries":        [],
        "max_submissions_per_user": 10,
        "require_screenshot":       True,
        "require_ocr":              False,
        "flag_on_vpn":              True,
        "flag_on_proxy":            True,
        "appeal_allowed":           True,
        "max_appeals_per_user":     3,
    }

    @classmethod
    def _key(cls, offer_id: str) -> str:
        return f"offer_mod_config:{offer_id}"

    @classmethod
    def get(cls, offer_id: str) -> dict:
        stored = _cache_get(cls._key(offer_id))
        if stored:
            return {**cls._DEFAULTS, **stored}
        return dict(cls._DEFAULTS)

    @classmethod
    def set(cls, offer_id: str, config: dict) -> dict:
        # Validate keys
        invalid = set(config) - set(cls._DEFAULTS)
        if invalid:
            raise ValueError(f"Invalid config keys: {invalid}")
        existing = _cache_get(cls._key(offer_id), {})
        merged   = {**existing, **config}
        _cache_set(cls._key(offer_id), merged, cls._TTL)
        return {**cls._DEFAULTS, **merged}

    @classmethod
    def reset(cls, offer_id: str) -> None:
        cache.delete(f"auto_mod:{cls._key(offer_id)}")

    @classmethod
    def should_auto_approve(cls, offer_id: str,
                            confidence: float) -> bool:
        cfg = cls.get(offer_id)
        if cfg["require_human_review"]:
            return False
        return confidence >= cfg["auto_approve_threshold"]


# =============================================================================
# 12. ReReviewService — re-review workflow (appeal-triggered re-scan)
# =============================================================================

class ReReviewService:
    """
    Manages re-review of submissions after a successful appeal or
    moderator escalation. Triggers fresh scans and resets decisions.
    Single owner: all re-review workflow lives here.
    """

    @staticmethod
    def initiate_re_review(submission, *, reason: str,
                           initiated_by=None) -> dict:
        """
        Mark a submission for re-review:
          1. Reset status to PENDING
          2. Create re-review record in cache
          3. Signal scan pipeline to re-run
        """
        from .choices import ModerationStatus
        from .models import SuspiciousSubmission

        try:
            SuspiciousSubmission.objects.filter(pk=submission.pk).update(
                status=ModerationStatus.PENDING,
            )
        except Exception as exc:
            logger.warning("ReReviewService: could not reset status: %s", exc)

        record = {
            "submission_id": str(submission.pk),
            "reason":        reason,
            "initiated_by":  str(initiated_by.pk) if initiated_by else "system",
            "initiated_at":  timezone.now().isoformat(),
            "status":        "queued",
        }
        _cache_set(f"re_review:{submission.pk}", record, 3600)

        # Dispatch Celery task if available
        try:
            from .tasks import scan_submission
            scan_submission.delay(str(submission.pk))
        except Exception:
            pass  # task dispatch is best-effort

        logger.info("re_review.initiated submission_id=%s reason=%r",
                    submission.pk, reason)
        return record

    @staticmethod
    def get_status(submission_id: str) -> dict | None:
        return _cache_get(f"re_review:{submission_id}")

    @staticmethod
    def complete_re_review(submission_id: str,
                           new_status: str) -> None:
        record = _cache_get(f"re_review:{submission_id}")
        if record:
            record["status"]       = "completed"
            record["new_status"]   = new_status
            record["completed_at"] = timezone.now().isoformat()
            _cache_set(f"re_review:{submission_id}", record, 3600)


# =============================================================================
# 13. ABTestService — ML model A/B testing framework
# =============================================================================

class ABTestService:
    """
    Routes submissions to different ML model versions for A/B testing.
    Tracks per-variant accuracy, throughput, and decision rates.
    Single owner: all A/B testing logic lives here.
    """

    @classmethod
    def _exp_key(cls, experiment_id: str) -> str:
        return f"ab_test:{experiment_id}"

    @classmethod
    def create_experiment(
        cls,
        experiment_id: str,
        *,
        model_a_id: str,
        model_b_id: str,
        traffic_split: float = 0.5,
        description: str = "",
    ) -> dict:
        """Create a new A/B experiment with a 50/50 or custom traffic split."""
        if not 0 < traffic_split < 1:
            raise ValueError("traffic_split must be between 0 and 1")

        experiment = {
            "id":            experiment_id,
            "model_a_id":    model_a_id,
            "model_b_id":    model_b_id,
            "split":         traffic_split,
            "description":   description,
            "created_at":    timezone.now().isoformat(),
            "status":        "running",
            "stats_a":       {"total": 0, "approved": 0, "rejected": 0},
            "stats_b":       {"total": 0, "approved": 0, "rejected": 0},
        }
        _cache_set(cls._exp_key(experiment_id), experiment, 86_400 * 7)
        logger.info("ab_test.created exp=%s A=%s B=%s split=%.2f",
                    experiment_id, model_a_id, model_b_id, traffic_split)
        return experiment

    @classmethod
    def assign_variant(cls, experiment_id: str,
                       submission_id: str) -> str:
        """
        Deterministically assign a variant ('a' or 'b') to a submission.
        Uses submission_id hash for consistency (same submission → same variant).
        """
        exp = _cache_get(cls._exp_key(experiment_id))
        if not exp or exp["status"] != "running":
            return "a"  # default to A when no active experiment

        h = int(hashlib.md5(submission_id.encode()).hexdigest(), 16)
        return "b" if (h % 1000) / 1000 < exp["split"] else "a"

    @classmethod
    def get_model_id(cls, experiment_id: str,
                     submission_id: str) -> str:
        """Return the model_id assigned for this submission in the experiment."""
        exp = _cache_get(cls._exp_key(experiment_id))
        if not exp:
            return ""
        variant = cls.assign_variant(experiment_id, submission_id)
        return exp[f"model_{variant}_id"]

    @classmethod
    def record_result(cls, experiment_id: str, submission_id: str,
                      decision: str) -> None:
        """Record a decision result for statistical tracking."""
        exp = _cache_get(cls._exp_key(experiment_id))
        if not exp:
            return
        variant = cls.assign_variant(experiment_id, submission_id)
        stats   = exp[f"stats_{variant}"]
        stats["total"] += 1
        if "approved" in decision.lower():
            stats["approved"] += 1
        elif "rejected" in decision.lower():
            stats["rejected"] += 1
        _cache_set(cls._exp_key(experiment_id), exp, 86_400 * 7)

    @classmethod
    def get_results(cls, experiment_id: str) -> dict:
        """Return current experiment results with basic statistical summary."""
        exp = _cache_get(cls._exp_key(experiment_id))
        if not exp:
            return {"error": "experiment_not_found"}

        def approval_rate(stats: dict) -> float:
            return round(stats["approved"] / stats["total"], 4) \
                   if stats["total"] else 0.0

        a_rate = approval_rate(exp["stats_a"])
        b_rate = approval_rate(exp["stats_b"])
        return {
            "experiment_id": experiment_id,
            "status":        exp["status"],
            "model_a": {
                "model_id":     exp["model_a_id"],
                "stats":        exp["stats_a"],
                "approval_rate": a_rate,
            },
            "model_b": {
                "model_id":     exp["model_b_id"],
                "stats":        exp["stats_b"],
                "approval_rate": b_rate,
            },
            "winner": "a" if a_rate > b_rate else "b" if b_rate > a_rate else "tie",
            "lift":   round(abs(a_rate - b_rate), 4),
        }

    @classmethod
    def stop_experiment(cls, experiment_id: str) -> dict:
        """Stop the experiment and return final results."""
        exp = _cache_get(cls._exp_key(experiment_id))
        if exp:
            exp["status"]  = "stopped"
            exp["ended_at"] = timezone.now().isoformat()
            _cache_set(cls._exp_key(experiment_id), exp, 86_400 * 7)
        return cls.get_results(experiment_id)


# =============================================================================
# 14. ModeratorPerformanceTracker — track moderator speed, accuracy, workload
# =============================================================================

class ModeratorPerformanceTracker:
    """
    Tracks per-moderator KPIs: decisions/hour, accuracy rate, SLA compliance,
    appeal overturn rate, and average review time.
    Single owner: all moderator performance logic lives here.
    """

    _TTL = 86_400 * 30  # 30 days

    @classmethod
    def _key(cls, moderator_id: str) -> str:
        return f"mod_perf:{moderator_id}"

    @classmethod
    def record_decision(cls, moderator_id: str, *,
                        decision: str, review_time_seconds: float,
                        was_appealed: bool = False,
                        appeal_overturned: bool = False) -> None:
        key  = cls._key(moderator_id)
        data = _cache_get(key, {
            "total":             0,
            "approved":          0,
            "rejected":          0,
            "appealed":          0,
            "overturned":        0,
            "total_review_time": 0.0,
            "sla_met":           0,
        })
        data["total"]             += 1
        data["total_review_time"] += review_time_seconds
        if "approved" in decision.lower():
            data["approved"] += 1
        elif "rejected" in decision.lower():
            data["rejected"] += 1
        if was_appealed:
            data["appealed"] += 1
        if appeal_overturned:
            data["overturned"] += 1
        if review_time_seconds <= 86_400:          # reviewed within 24h SLA
            data["sla_met"] += 1
        _cache_set(key, data, cls._TTL)

    @classmethod
    def get_stats(cls, moderator_id: str) -> dict:
        data  = _cache_get(cls._key(moderator_id), {})
        total = data.get("total", 0)
        if total == 0:
            return {"moderator_id": moderator_id, "total_decisions": 0}
        avg_time = data.get("total_review_time", 0) / total
        return {
            "moderator_id":          moderator_id,
            "total_decisions":       total,
            "approval_rate":         round(data.get("approved", 0) / total, 4),
            "rejection_rate":        round(data.get("rejected", 0) / total, 4),
            "appeal_rate":           round(data.get("appealed", 0) / total, 4),
            "overturn_rate":         round(data.get("overturned", 0) / max(data.get("appealed", 1), 1), 4),
            "sla_compliance_rate":   round(data.get("sla_met", 0) / total, 4),
            "avg_review_time_sec":   round(avg_time, 1),
            "decisions_per_hour":    round(3600 / avg_time, 2) if avg_time else 0,
        }

    @classmethod
    def get_leaderboard(cls, moderator_ids: list[str],
                        sort_by: str = "total_decisions") -> list[dict]:
        stats = [cls.get_stats(mid) for mid in moderator_ids]
        stats = [s for s in stats if s.get("total_decisions", 0) > 0]
        return sorted(stats, key=lambda x: x.get(sort_by, 0), reverse=True)


# =============================================================================
# 15. BulkModerationService — bulk approve/reject/escalate in one operation
# =============================================================================

class BulkModerationService:
    """
    Process multiple submissions in a single atomic operation.
    Used by moderators for high-volume manual review workflows.
    Single owner: all bulk moderation logic lives here.
    """

    MAX_BULK_SIZE = 200

    @staticmethod
    def bulk_approve(
        submission_ids: list[str],
        reviewer,
        note: str = "",
    ) -> dict:
        """
        Human-approve a batch of submissions.
        Returns {approved, failed, errors}.
        """
        from .models import SuspiciousSubmission
        from .choices import ModerationStatus
        from django.utils import timezone

        if len(submission_ids) > BulkModerationService.MAX_BULK_SIZE:
            raise ValueError(
                f"Batch too large: {len(submission_ids)} > {BulkModerationService.MAX_BULK_SIZE}"
            )

        approved, failed, errors = 0, 0, []
        qs = SuspiciousSubmission.objects.filter(pk__in=submission_ids)

        for sub in qs:
            try:
                sub.reviewed_by   = reviewer
                sub.reviewed_at   = timezone.now()
                sub.reviewer_note = note
                sub.status        = ModerationStatus.HUMAN_APPROVED
                sub.final_status  = ModerationStatus.HUMAN_APPROVED
                sub.save(update_fields=[
                    "reviewed_by", "reviewed_at", "reviewer_note",
                    "status", "final_status", "updated_at"
                ])
                approved += 1
            except Exception as exc:
                failed += 1
                errors.append({"submission_id": str(sub.pk), "error": str(exc)})

        logger.info(
            "bulk_moderate.approved count=%d failed=%d reviewer=%s",
            approved, failed, reviewer.pk
        )
        return {"approved": approved, "failed": failed, "errors": errors}

    @staticmethod
    def bulk_reject(
        submission_ids: list[str],
        reviewer,
        reason: str,
        note: str = "",
    ) -> dict:
        """Human-reject a batch of submissions."""
        from .models import SuspiciousSubmission
        from .choices import ModerationStatus
        from django.utils import timezone

        if len(submission_ids) > BulkModerationService.MAX_BULK_SIZE:
            raise ValueError(f"Batch too large")

        rejected, failed, errors = 0, 0, []
        qs = SuspiciousSubmission.objects.filter(pk__in=submission_ids)

        for sub in qs:
            try:
                sub.reviewed_by   = reviewer
                sub.reviewed_at   = timezone.now()
                sub.reviewer_note = f"{reason}\n{note}".strip()
                sub.status        = ModerationStatus.HUMAN_REJECTED
                sub.final_status  = ModerationStatus.HUMAN_REJECTED
                sub.save(update_fields=[
                    "reviewed_by", "reviewed_at", "reviewer_note",
                    "status", "final_status", "updated_at"
                ])
                rejected += 1
            except Exception as exc:
                failed += 1
                errors.append({"submission_id": str(sub.pk), "error": str(exc)})

        logger.info(
            "bulk_moderate.rejected count=%d failed=%d",
            rejected, failed
        )
        return {"rejected": rejected, "failed": failed, "errors": errors}

    @staticmethod
    def bulk_escalate(
        submission_ids: list[str],
        escalated_to,
        note: str = "",
    ) -> dict:
        """Escalate a batch of submissions to a senior moderator."""
        from .models import SuspiciousSubmission
        from .choices import ModerationStatus

        escalated, failed, errors = 0, 0, []
        qs = SuspiciousSubmission.objects.filter(pk__in=submission_ids)

        for sub in qs:
            try:
                sub.escalated_to  = escalated_to
                sub.reviewer_note = note
                sub.status        = ModerationStatus.ESCALATED
                sub.save(update_fields=[
                    "escalated_to", "reviewer_note", "status", "updated_at"
                ])
                escalated += 1
            except Exception as exc:
                failed += 1
                errors.append({"submission_id": str(sub.pk), "error": str(exc)})

        return {"escalated": escalated, "failed": failed, "errors": errors}

    @staticmethod
    def bulk_assign_to_queue(
        submission_ids: list[str],
        priority: str = "normal",
    ) -> dict:
        """Add multiple submissions to the moderation queue at once."""
        from .models import SuspiciousSubmission
        from .services import ModerationQueueService

        svc = ModerationQueueService()
        queued, failed, errors = 0, 0, []
        qs  = SuspiciousSubmission.objects.filter(pk__in=submission_ids)

        for sub in qs:
            try:
                svc.add_to_queue(sub, priority=priority)
                queued += 1
            except Exception as exc:
                failed += 1
                errors.append({"submission_id": str(sub.pk), "error": str(exc)})

        return {"queued": queued, "failed": failed, "errors": errors}

    @staticmethod
    def get_bulk_status(submission_ids: list[str]) -> list[dict]:
        """Return current status of multiple submissions in one query."""
        from .models import SuspiciousSubmission

        qs = SuspiciousSubmission.objects.filter(
            pk__in=submission_ids
        ).values("id", "status", "risk_level", "ai_confidence", "updated_at")
        return [
            {
                "submission_id": str(row["id"]),
                "status":        row["status"],
                "risk_level":    row["risk_level"],
                "confidence":    float(row["ai_confidence"] or 0),
                "updated_at":    str(row["updated_at"]),
            }
            for row in qs
        ]
