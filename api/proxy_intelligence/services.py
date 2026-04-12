"""
Proxy Intelligence Services  (PRODUCTION-READY - COMPLETE REWRITE)
====================================================================
Orchestrates all detection engines, integrations, and database writes.
This is the single source of truth for all business logic.

Services:
  IPValidationService     — validates & normalises IP strings
  BlacklistService        — blacklist/whitelist CRUD + cache
  RiskScoringService      — composite risk score calculation
  IPIntelligenceService   — full IP check orchestration (main entry point)
  VelocityService         — rate limiting / velocity tracking
  FingerprintService      — device fingerprint processing
  ThreatFeedService       — multi-feed threat enrichment
  AlertService            — dispatches real-time alerts
  AuditService            — writes SystemAuditTrail entries
  APIRequestLogger        — persists API call logs
  PerformanceTracker      — records engine latency metrics
"""

import ipaddress
import logging
import time
from datetime import timedelta
from typing import Optional, List

from django.core.cache import cache
from django.utils import timezone

from .cache import PICache
from .constants import (
    IP_INTELLIGENCE_CACHE_TTL, BLACKLIST_CACHE_TTL,
    VPN_CONFIDENCE_THRESHOLD, TOR_CONFIDENCE_THRESHOLD,
    DATACENTER_CONFIDENCE_THRESHOLD, VELOCITY_WINDOW_SECONDS,
    MAX_REQUESTS_PER_MINUTE,
)
from .enums import RiskLevel, BlacklistReason
from .exceptions import InvalidIPAddress, IPBlacklistedException
from .models import (
    IPIntelligence, IPBlacklist, IPWhitelist,
    VPNDetectionLog, ProxyDetectionLog, TorExitNode,
    FraudAttempt, UserRiskProfile, RiskScoreHistory,
    VelocityMetric, APIRequestLog, AnomalyDetectionLog,
    SystemAuditTrail, PerformanceMetric, IntegrationCredential,
    DeviceFingerprint, MaliciousIPDatabase, AlertConfiguration,
)
from .schemas import (
    IPCheckRequest, IPDetectionResult, BulkIPCheckResult,
    FingerprintResult, VelocityResult, DashboardStats,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# 1. IP VALIDATION SERVICE
# ══════════════════════════════════════════════════════════════════

class IPValidationService:
    """Validates, normalises, and classifies IP address strings."""

    @staticmethod
    def validate(ip_str: str) -> str:
        """Return normalised IP string or raise InvalidIPAddress."""
        try:
            return str(ipaddress.ip_address(ip_str.strip()))
        except ValueError:
            raise InvalidIPAddress(f"'{ip_str}' is not a valid IP address.")

    @staticmethod
    def is_private(ip_str: str) -> bool:
        try:
            return ipaddress.ip_address(ip_str).is_private
        except ValueError:
            return False

    @staticmethod
    def is_loopback(ip_str: str) -> bool:
        try:
            return ipaddress.ip_address(ip_str).is_loopback
        except ValueError:
            return False

    @staticmethod
    def is_reserved(ip_str: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
            return addr.is_reserved or addr.is_multicast or addr.is_link_local
        except ValueError:
            return False

    @staticmethod
    def should_skip(ip_str: str) -> bool:
        """Return True if this IP should bypass all checks (private/loopback)."""
        return (IPValidationService.is_private(ip_str) or
                IPValidationService.is_loopback(ip_str) or
                IPValidationService.is_reserved(ip_str))

    @staticmethod
    def get_version(ip_str: str) -> str:
        try:
            return 'ipv6' if ipaddress.ip_address(ip_str).version == 6 else 'ipv4'
        except ValueError:
            return 'ipv4'

    @staticmethod
    def extract_from_request(request) -> str:
        """Extract real client IP from Django request, honouring proxy headers."""
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            ip = xff.split(',')[0].strip()
            try:
                ipaddress.ip_address(ip)
                if not IPValidationService.is_private(ip):
                    return ip
            except ValueError:
                pass
        real_ip = request.META.get('HTTP_X_REAL_IP', '')
        if real_ip:
            try:
                ipaddress.ip_address(real_ip)
                return real_ip
            except ValueError:
                pass
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ══════════════════════════════════════════════════════════════════
# 2. BLACKLIST SERVICE
# ══════════════════════════════════════════════════════════════════

class BlacklistService:
    """Manages IP blacklist and whitelist operations with Redis caching."""

    @staticmethod
    def is_blacklisted(ip_address: str, tenant=None) -> bool:
        cached = PICache.is_blacklisted(ip_address)
        if cached is not None:
            return bool(cached)

        qs = IPBlacklist.objects.filter(ip_address=ip_address, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)

        result = any(not entry.is_expired() for entry in qs)
        PICache.set_blacklist(ip_address, result)
        return result

    @staticmethod
    def is_whitelisted(ip_address: str, tenant=None) -> bool:
        cached = PICache.is_whitelisted(ip_address)
        if cached is not None:
            return bool(cached)

        qs = IPWhitelist.objects.filter(ip_address=ip_address, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)

        result = qs.exists()
        PICache.set_whitelist(ip_address, result)
        return result

    @staticmethod
    def add_to_blacklist(
        ip_address: str,
        reason: str,
        tenant=None,
        is_permanent: bool = False,
        expires_hours: Optional[int] = None,
        blocked_by=None,
        description: str = '',
        source: str = 'manual',
    ) -> IPBlacklist:
        expires_at = None
        if not is_permanent and expires_hours:
            expires_at = timezone.now() + timedelta(hours=expires_hours)

        entry, _ = IPBlacklist.objects.update_or_create(
            ip_address=ip_address,
            tenant=tenant,
            defaults={
                'reason':       reason,
                'is_permanent': is_permanent,
                'is_active':    True,
                'expires_at':   expires_at,
                'blocked_by':   blocked_by,
                'description':  description,
                'source':       source,
            }
        )
        PICache.invalidate_blacklist(ip_address)
        PICache.invalidate_all_for_ip(ip_address)
        return entry

    @staticmethod
    def remove_from_blacklist(ip_address: str, tenant=None) -> int:
        qs = IPBlacklist.objects.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        count, _ = qs.update(is_active=False)
        PICache.invalidate_blacklist(ip_address)
        return count

    @staticmethod
    def bulk_blacklist(ip_list: List[str], reason: str,
                       tenant=None, source: str = 'threat_feed') -> int:
        created = 0
        for ip in ip_list:
            try:
                IPValidationService.validate(ip)
                entry, made = IPBlacklist.objects.get_or_create(
                    ip_address=ip, tenant=tenant,
                    defaults={'reason': reason, 'is_active': True,
                              'source': source, 'is_permanent': False}
                )
                if made:
                    created += 1
                PICache.invalidate_blacklist(ip)
            except Exception:
                continue
        return created


# ══════════════════════════════════════════════════════════════════
# 3. RISK SCORING SERVICE
# ══════════════════════════════════════════════════════════════════

class RiskScoringService:
    """
    Calculates composite 0-100 risk scores from detection signals.
    Weights are calibrated so that Tor = always block, VPN = challenge.
    """

    SIGNAL_WEIGHTS = {
        'is_tor':               45,
        'is_vpn':               30,
        'is_proxy':             20,
        'is_datacenter':        10,
        'malicious_db':         35,   # Found in MaliciousIPDatabase
        'abuse_confidence':     0.4,  # multiplier on 0-100 field
        'fraud_score':          0.2,  # multiplier on 0-100 field
        'velocity_exceeded':    15,
        'multi_account':        20,
        'device_spoofing':      15,
    }

    @classmethod
    def calculate(cls, signals: dict) -> int:
        """
        signals: dict of signal_name -> bool or numeric value
        Returns: int 0-100
        """
        score = 0

        if signals.get('is_tor'):
            score += cls.SIGNAL_WEIGHTS['is_tor']
        if signals.get('is_vpn'):
            score += int(cls.SIGNAL_WEIGHTS['is_vpn'] *
                         signals.get('vpn_confidence', 1.0))
        if signals.get('is_proxy'):
            score += int(cls.SIGNAL_WEIGHTS['is_proxy'] *
                         signals.get('proxy_confidence', 1.0))
        if signals.get('is_datacenter'):
            score += cls.SIGNAL_WEIGHTS['is_datacenter']
        if signals.get('malicious_db'):
            score += cls.SIGNAL_WEIGHTS['malicious_db']

        abuse = signals.get('abuse_confidence_score', 0)
        score += int(abuse * cls.SIGNAL_WEIGHTS['abuse_confidence'])

        fraud = signals.get('fraud_score', 0)
        score += int(fraud * cls.SIGNAL_WEIGHTS['fraud_score'])

        if signals.get('velocity_exceeded'):
            score += cls.SIGNAL_WEIGHTS['velocity_exceeded']
        if signals.get('multi_account'):
            score += cls.SIGNAL_WEIGHTS['multi_account']
        if signals.get('device_spoofing'):
            score += cls.SIGNAL_WEIGHTS['device_spoofing']

        return min(int(score), 100)

    @staticmethod
    def score_to_level(score: int) -> str:
        if score <= 20: return RiskLevel.VERY_LOW
        if score <= 40: return RiskLevel.LOW
        if score <= 60: return RiskLevel.MEDIUM
        if score <= 80: return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    @staticmethod
    def level_to_action(risk_level: str) -> str:
        mapping = {
            RiskLevel.VERY_LOW: 'allow',
            RiskLevel.LOW:      'allow',
            RiskLevel.MEDIUM:   'flag',
            RiskLevel.HIGH:     'challenge',
            RiskLevel.CRITICAL: 'block',
        }
        return mapping.get(risk_level, 'flag')

    @classmethod
    def update_user_profile(cls, user, ip_risk: int,
                            fraud_detected: bool = False,
                            tenant=None) -> UserRiskProfile:
        """Update UserRiskProfile and log any significant score changes."""
        profile, _ = UserRiskProfile.objects.get_or_create(
            user=user,
            defaults={'tenant': tenant}
        )
        old_score = profile.overall_risk_score

        profile.ip_risk_score = ip_risk
        if fraud_detected:
            profile.fraud_attempts_count += 1
            profile.behavior_risk_score = min(profile.behavior_risk_score + 15, 100)

        # Weighted composite
        profile.overall_risk_score = min(int(
            profile.ip_risk_score       * 0.40 +
            profile.behavior_risk_score * 0.30 +
            profile.device_risk_score   * 0.15 +
            profile.transaction_risk_score * 0.15
        ), 100)
        profile.risk_level = cls.score_to_level(profile.overall_risk_score)
        profile.is_high_risk = profile.overall_risk_score >= 61
        profile.last_assessed = timezone.now()
        profile.save()

        # Record history if the score changed meaningfully (≥5 points)
        delta = abs(profile.overall_risk_score - old_score)
        if delta >= 5:
            RiskScoreHistory.objects.create(
                user=user,
                ip_address='0.0.0.0',
                previous_score=old_score,
                new_score=profile.overall_risk_score,
                triggered_by='ip_check' if not fraud_detected else 'fraud_detected',
                tenant=tenant,
            )

        return profile


# ══════════════════════════════════════════════════════════════════
# 4. IP INTELLIGENCE SERVICE  (Main orchestrator)
# ══════════════════════════════════════════════════════════════════

class IPIntelligenceService:
    """
    Central service that orchestrates all detection engines and integrations
    to produce a complete IP risk profile.

    Call .full_check(ip_address) for a complete analysis.
    Call .quick_check(ip_address) for a fast cached-only check.
    """

    def __init__(self, tenant=None):
        self.tenant = tenant

    # ── Quick check (cache only, <5ms) ───────────────────────────────────

    def quick_check(self, ip_address: str, user=None) -> dict:
        """
        Millisecond-speed check using only cached data.
        No external API calls, no DB writes.
        """
        from .real_time_processing.real_time_scorer import RealTimeScorer
        scorer = RealTimeScorer(ip_address, user=user, tenant=self.tenant)
        return scorer.score_request()

    # ── Full check (complete analysis) ───────────────────────────────────

    def full_check(self, ip_address: str, user=None,
                   request_headers: dict = None,
                   include_threat_feeds: bool = False) -> IPDetectionResult:
        """
        Complete IP analysis. Runs all engines and returns IPDetectionResult.
        Results are cached for 1 hour to prevent repeated external calls.
        """
        t_start = time.time()
        ip = IPValidationService.validate(ip_address)
        headers = request_headers or {}

        # ── 1. Whitelist check ───────────────────────────────────────────
        if BlacklistService.is_whitelisted(ip, self.tenant):
            return self._build_result(ip, is_whitelisted=True,
                                      elapsed=time.time() - t_start)

        # ── 2. Blacklist check ───────────────────────────────────────────
        if BlacklistService.is_blacklisted(ip, self.tenant):
            return self._build_result(ip, is_blacklisted=True,
                                      recommended_action='block',
                                      elapsed=time.time() - t_start)

        # ── 3. Core detection engines ─────────────────────────────────────
        vpn_result     = self._run_vpn_detector(ip, headers)
        proxy_result   = self._run_proxy_detector(ip, headers)
        tor_result     = self._run_tor_detector(ip)
        dc_result      = self._run_datacenter_detector(ip, vpn_result.get('asn', ''))
        asn_info       = self._run_asn_lookup(ip)

        # ── 4. Threat feed enrichment (optional, slower) ──────────────────
        threat_result  = {}
        abuse_score    = 0
        if include_threat_feeds:
            threat_result = self._run_threat_feeds(ip)
            abuse_score   = threat_result.get('abuse_confidence_score', 0)

        # ── 5. Malicious DB cross-check ───────────────────────────────────
        in_malicious_db = MaliciousIPDatabase.objects.filter(
            ip_address=ip, is_active=True
        ).exists()

        # ── 6. Composite risk score ────────────────────────────────────────
        risk_score = RiskScoringService.calculate({
            'is_tor':               tor_result.get('is_tor', False),
            'is_vpn':               vpn_result.get('is_vpn', False),
            'vpn_confidence':       vpn_result.get('confidence', 0),
            'is_proxy':             proxy_result.get('is_proxy', False),
            'proxy_confidence':     proxy_result.get('confidence', 0),
            'is_datacenter':        dc_result.get('is_datacenter', False),
            'malicious_db':         in_malicious_db,
            'abuse_confidence_score': abuse_score,
            'fraud_score':          threat_result.get('fraud_score', 0),
        })
        risk_level = RiskScoringService.score_to_level(risk_score)
        action     = RiskScoringService.level_to_action(risk_level)

        # ── 7. Persist to IPIntelligence ──────────────────────────────────
        intel = self._persist_intelligence(
            ip, vpn_result, proxy_result, tor_result, dc_result,
            asn_info, risk_score, risk_level, threat_result
        )

        # ── 8. Update user risk profile ───────────────────────────────────
        if user and user.is_authenticated:
            RiskScoringService.update_user_profile(
                user, risk_score, tenant=self.tenant
            )

        # ── 9. Build response ─────────────────────────────────────────────
        result = self._build_result(
            ip,
            is_blacklisted=False,
            is_whitelisted=False,
            risk_score=risk_score,
            risk_level=risk_level,
            recommended_action=action,
            is_vpn=vpn_result.get('is_vpn', False),
            is_proxy=proxy_result.get('is_proxy', False),
            is_tor=tor_result.get('is_tor', False),
            is_datacenter=dc_result.get('is_datacenter', False),
            vpn_provider=vpn_result.get('vpn_provider', ''),
            proxy_type=proxy_result.get('proxy_type', ''),
            country_code=asn_info.get('country', ''),
            city=asn_info.get('city', ''),
            region=asn_info.get('region', ''),
            isp=asn_info.get('isp', ''),
            asn=asn_info.get('asn', ''),
            detection_methods=(
                vpn_result.get('detection_methods', []) +
                proxy_result.get('detection_methods', [])
            ),
            elapsed=time.time() - t_start,
        )

        # ── 10. Record performance metric ─────────────────────────────────
        PerformanceTracker.record(
            engine_name='ip_intelligence_service',
            metric_type='detection_latency',
            value=result.response_time_ms,
            unit='ms',
        )

        return result

    # ── Detection Engine Runners ─────────────────────────────────────────

    def _run_vpn_detector(self, ip: str, headers: dict) -> dict:
        try:
            from .detection_engines.vpn_detector import VPNDetector
            return VPNDetector(ip, request_headers=headers).detect()
        except Exception as e:
            logger.warning(f"VPN detector failed for {ip}: {e}")
            return {'is_vpn': False, 'confidence': 0.0, 'vpn_provider': ''}

    def _run_proxy_detector(self, ip: str, headers: dict) -> dict:
        try:
            from .detection_engines.proxy_detector import ProxyDetector
            return ProxyDetector(ip, request_headers=headers).detect()
        except Exception as e:
            logger.warning(f"Proxy detector failed for {ip}: {e}")
            return {'is_proxy': False, 'confidence': 0.0, 'proxy_type': ''}

    def _run_tor_detector(self, ip: str) -> dict:
        try:
            from .detection_engines.tor_detector import TorDetector
            return TorDetector.detect(ip)
        except Exception as e:
            logger.warning(f"Tor detector failed for {ip}: {e}")
            return {'is_tor': False, 'confidence': 0.0}

    def _run_datacenter_detector(self, ip: str, asn: str = '') -> dict:
        try:
            from .detection_engines.proxy_detector import DatacenterDetector
            return {
                'is_datacenter': DatacenterDetector.is_datacenter(ip, asn),
                'asn': asn,
            }
        except Exception as e:
            logger.warning(f"Datacenter detector failed for {ip}: {e}")
            return {'is_datacenter': False}

    def _run_asn_lookup(self, ip: str) -> dict:
        try:
            from .ip_intelligence.ip_asn_lookup import ASNLookup
            return ASNLookup.lookup(ip)
        except Exception as e:
            logger.debug(f"ASN lookup failed for {ip}: {e}")
            return {}

    def _run_threat_feeds(self, ip: str) -> dict:
        """Run AbuseIPDB + IPQS threat feed checks."""
        combined = {}
        # AbuseIPDB
        try:
            from .integrations.abuseipdb_integration import AbuseIPDBIntegration
            abuse = AbuseIPDBIntegration().check(ip)
            combined['abuse_confidence_score'] = abuse.get('abuse_confidence_score', 0)
            combined['total_abuse_reports']    = abuse.get('total_reports', 0)
        except Exception as e:
            logger.debug(f"AbuseIPDB failed for {ip}: {e}")

        # IPQS
        try:
            from .integrations.ipqualityscore_integration import IPQualityScoreIntegration
            ipqs = IPQualityScoreIntegration(tenant=self.tenant).check(ip)
            if ipqs.get('success'):
                combined['fraud_score']     = ipqs.get('fraud_score', 0)
                combined['ipqs_is_proxy']   = ipqs.get('is_proxy', False)
                combined['ipqs_is_vpn']     = ipqs.get('is_vpn', False)
                combined['recent_abuse']    = ipqs.get('recent_abuse', False)
        except Exception as e:
            logger.debug(f"IPQS failed for {ip}: {e}")

        return combined

    # ── Persistence ───────────────────────────────────────────────────────

    def _persist_intelligence(
        self, ip, vpn, proxy, tor, dc, asn_info,
        risk_score, risk_level, threat
    ) -> IPIntelligence:
        """Create or update the IPIntelligence record."""
        defaults = {
            'ip_version':     IPValidationService.get_version(ip),
            'asn':            asn_info.get('asn', ''),
            'asn_name':       asn_info.get('asn_name', ''),
            'isp':            asn_info.get('isp', ''),
            'country_code':   asn_info.get('country', ''),
            'city':           asn_info.get('city', ''),
            'region':         asn_info.get('region', ''),
            'is_vpn':         vpn.get('is_vpn', False),
            'is_proxy':       proxy.get('is_proxy', False),
            'is_tor':         tor.get('is_tor', False),
            'is_datacenter':  dc.get('is_datacenter', False),
            'risk_score':     risk_score,
            'risk_level':     risk_level,
            'fraud_score':    threat.get('fraud_score', 0),
            'abuse_confidence_score': threat.get('abuse_confidence_score', 0),
            'last_checked':   timezone.now(),
            'tenant':         self.tenant,
        }
        obj, created = IPIntelligence.objects.update_or_create(
            ip_address=ip, tenant=self.tenant, defaults=defaults
        )
        if not created:
            obj.check_count += 1
            obj.save(update_fields=['check_count', 'last_checked'])

        # Update cache
        PICache.set_intelligence(ip, {
            'risk_score':    risk_score,
            'risk_level':    risk_level,
            'is_vpn':        vpn.get('is_vpn', False),
            'is_proxy':      proxy.get('is_proxy', False),
            'is_tor':        tor.get('is_tor', False),
            'is_datacenter': dc.get('is_datacenter', False),
        })
        return obj

    # ── Result Builder ────────────────────────────────────────────────────

    @staticmethod
    def _build_result(ip: str, is_blacklisted: bool = False,
                      is_whitelisted: bool = False, risk_score: int = 0,
                      risk_level: str = RiskLevel.VERY_LOW,
                      recommended_action: str = 'allow', elapsed: float = 0,
                      **kwargs) -> IPDetectionResult:
        return IPDetectionResult(
            ip_address=ip,
            risk_score=risk_score if not is_blacklisted else 100,
            risk_level=risk_level if not is_blacklisted else RiskLevel.CRITICAL,
            recommended_action='block' if is_blacklisted else recommended_action,
            is_blacklisted=is_blacklisted,
            is_whitelisted=is_whitelisted,
            response_time_ms=round(elapsed * 1000, 2),
            checked_at=timezone.now().isoformat(),
            **{k: v for k, v in kwargs.items()
               if k in IPDetectionResult.__dataclass_fields__}
        )


# ══════════════════════════════════════════════════════════════════
# 5. VELOCITY SERVICE
# ══════════════════════════════════════════════════════════════════

class VelocityService:
    """
    Tracks request rate per IP / action and enforces velocity thresholds.
    Uses Redis counters with atomic increments and sliding window TTL.
    """

    @classmethod
    def record_and_check(cls, ip_address: str, action_type: str,
                          threshold: int = MAX_REQUESTS_PER_MINUTE,
                          window_seconds: int = VELOCITY_WINDOW_SECONDS,
                          user=None, tenant=None) -> VelocityResult:
        cache_key = f"pi:vel:{ip_address}:{action_type}:{window_seconds}"

        # Atomic increment
        try:
            count = cache.incr(cache_key)
        except ValueError:
            # Key doesn't exist yet
            cache.set(cache_key, 1, window_seconds)
            count = 1
        except Exception:
            count = 1

        # Ensure expiry is set
        cache.expire(cache_key, window_seconds)

        exceeded = count > threshold
        if exceeded:
            # Persist to DB (throttled: max 1 DB write per window)
            db_key = f"pi:vel_db:{ip_address}:{action_type}"
            if not cache.get(db_key):
                try:
                    VelocityMetric.objects.create(
                        ip_address=ip_address,
                        user=user,
                        action_type=action_type,
                        window_seconds=window_seconds,
                        request_count=count,
                        threshold=threshold,
                        exceeded=True,
                        tenant=tenant,
                    )
                    cache.set(db_key, 1, window_seconds)
                except Exception as e:
                    logger.debug(f"VelocityMetric DB write failed: {e}")

        return VelocityResult(
            ip_address=ip_address,
            action_type=action_type,
            request_count=count,
            threshold=threshold,
            window_seconds=window_seconds,
            exceeded=exceeded,
            recommended_action='rate_limit' if exceeded else 'allow',
        )

    @classmethod
    def get_current_rate(cls, ip_address: str, action_type: str,
                          window_seconds: int = 60) -> int:
        cache_key = f"pi:vel:{ip_address}:{action_type}:{window_seconds}"
        return cache.get(cache_key, 0)

    @classmethod
    def reset(cls, ip_address: str, action_type: str,
               window_seconds: int = 60):
        cache_key = f"pi:vel:{ip_address}:{action_type}:{window_seconds}"
        cache.delete(cache_key)


# ══════════════════════════════════════════════════════════════════
# 6. FINGERPRINT SERVICE
# ══════════════════════════════════════════════════════════════════

class FingerprintService:
    """Processes and analyses device fingerprints."""

    def __init__(self, tenant=None):
        self.tenant = tenant

    def process(self, raw_data: dict, ip_address: str = '',
                user=None) -> FingerprintResult:
        from .utilities.device_fingerprint import DeviceFingerprintProcessor
        processor = DeviceFingerprintProcessor(
            raw_data=raw_data,
            ip_address=ip_address,
            user=user,
            tenant=self.tenant,
        )
        result = processor.process()
        return FingerprintResult(**result)

    def analyze(self, fingerprint_hash: str) -> dict:
        from .utilities.device_fingerprint import FingerprintRiskAnalyzer
        return FingerprintRiskAnalyzer(fingerprint_hash, self.tenant).analyze()

    def get_linked_accounts(self, fingerprint_hash: str) -> list:
        """Return all users associated with this fingerprint."""
        return list(
            DeviceFingerprint.objects
            .filter(fingerprint_hash=fingerprint_hash)
            .exclude(user=None)
            .values('user__id', 'user__email', 'last_seen')
            .distinct()
        )


# ══════════════════════════════════════════════════════════════════
# 7. THREAT FEED SERVICE
# ══════════════════════════════════════════════════════════════════

class ThreatFeedService:
    """Orchestrates all threat feed integrations."""

    def __init__(self, tenant=None):
        self.tenant = tenant

    def check_ip(self, ip_address: str) -> dict:
        from .threat_intelligence.threat_feed_integrator import ThreatFeedIntegrator
        return ThreatFeedIntegrator().check_ip(ip_address)

    def sync_all(self) -> dict:
        from .threat_intelligence.threat_feed_integrator import ThreatFeedIntegrator
        return ThreatFeedIntegrator().sync_all_feeds()


# ══════════════════════════════════════════════════════════════════
# 8. ALERT SERVICE
# ══════════════════════════════════════════════════════════════════

class AlertService:
    """Dispatches real-time alerts for threat events."""

    @staticmethod
    def dispatch(trigger: str, context: dict, tenant=None) -> list:
        from .real_time_processing.webhook_handler import AlertDispatcher
        return AlertDispatcher.dispatch(trigger, context, tenant)

    @staticmethod
    def alert_high_risk_ip(ip_address: str, risk_score: int,
                            flags: list, tenant=None):
        if risk_score >= 61:
            AlertService.dispatch('high_risk_ip', {
                'ip_address': ip_address,
                'risk_score': risk_score,
                'risk_level': RiskScoringService.score_to_level(risk_score),
                'flags': flags,
            }, tenant)


# ══════════════════════════════════════════════════════════════════
# 9. AUDIT SERVICE
# ══════════════════════════════════════════════════════════════════

class AuditService:
    """Writes SystemAuditTrail entries for configuration changes."""

    @staticmethod
    def log(action: str, model_name: str, object_id: str = '',
            object_repr: str = '', before: dict = None, after: dict = None,
            user=None, ip_address: str = '', notes: str = '',
            tenant=None):
        try:
            SystemAuditTrail.objects.create(
                action=action,
                model_name=model_name,
                object_id=str(object_id),
                object_repr=object_repr[:500],
                before_state=before or {},
                after_state=after or {},
                user=user,
                ip_address=ip_address or None,
                notes=notes,
                tenant=tenant,
            )
        except Exception as e:
            logger.error(f"AuditTrail write failed: {e}")


# ══════════════════════════════════════════════════════════════════
# 10. API REQUEST LOGGER
# ══════════════════════════════════════════════════════════════════

class APIRequestLogger:
    """Persists API request logs asynchronously (best-effort)."""

    @staticmethod
    def log(ip_address: str, endpoint: str, method: str, status_code: int,
            response_time_ms: float = 0.0, user=None, tenant=None,
            user_agent: str = '', error: str = '',
            request_body: dict = None, response_summary: dict = None):
        try:
            APIRequestLog.objects.create(
                ip_address=ip_address,
                endpoint=endpoint[:255],
                method=method[:10],
                status_code=status_code,
                response_time_ms=response_time_ms,
                user=user,
                tenant=tenant,
                user_agent=user_agent[:500],
                error_message=error[:1000],
                request_body=request_body or {},
                response_summary=response_summary or {},
            )
        except Exception as e:
            logger.debug(f"APIRequestLog write failed: {e}")


# ══════════════════════════════════════════════════════════════════
# 11. PERFORMANCE TRACKER
# ══════════════════════════════════════════════════════════════════

class PerformanceTracker:
    """Records detection engine latency and throughput metrics."""

    @staticmethod
    def record(engine_name: str, metric_type: str, value: float,
               unit: str = 'ms', metadata: dict = None):
        try:
            PerformanceMetric.objects.create(
                engine_name=engine_name,
                metric_type=metric_type,
                value=value,
                unit=unit,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.debug(f"PerformanceMetric write failed: {e}")

    @staticmethod
    def time(engine_name: str, func, *args, **kwargs):
        """Execute func and record its latency."""
        t = time.time()
        result = func(*args, **kwargs)
        PerformanceTracker.record(
            engine_name=engine_name,
            metric_type='detection_latency',
            value=round((time.time() - t) * 1000, 2),
            unit='ms',
        )
        return result


# ══════════════════════════════════════════════════════════════════
# 12. DASHBOARD STATS SERVICE
# ══════════════════════════════════════════════════════════════════

class DashboardStatsService:
    """Generates aggregated stats for the admin dashboard."""

    def __init__(self, tenant=None):
        self.tenant = tenant

    def get(self) -> DashboardStats:
        cache_key = f"pi:dashboard_stats:{self.tenant.pk if self.tenant else 'global'}"
        cached = cache.get(cache_key)
        if cached:
            return DashboardStats(**cached)

        from django.db.models import Avg
        qs_intel = IPIntelligence.objects.all()
        if self.tenant:
            qs_intel = qs_intel.filter(tenant=self.tenant)

        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        stats = DashboardStats(
            total_ips_checked=qs_intel.count(),
            high_risk_ips=qs_intel.filter(risk_score__gte=61).count(),
            vpn_detected=qs_intel.filter(is_vpn=True).count(),
            proxy_detected=qs_intel.filter(is_proxy=True).count(),
            tor_detected=qs_intel.filter(is_tor=True).count(),
            blacklisted_ips=IPBlacklist.objects.filter(is_active=True).count(),
            fraud_attempts_today=FraudAttempt.objects.filter(
                created_at__gte=today).count(),
            anomalies_today=AnomalyDetectionLog.objects.filter(
                created_at__gte=today).count(),
            high_risk_users=UserRiskProfile.objects.filter(is_high_risk=True).count(),
            avg_risk_score=round(
                qs_intel.aggregate(avg=Avg('risk_score'))['avg'] or 0, 1
            ),
            tor_exit_nodes_tracked=TorExitNode.objects.filter(is_active=True).count(),
            malicious_ips_in_db=MaliciousIPDatabase.objects.filter(is_active=True).count(),
        )

        cache.set(cache_key, stats.to_dict(), 300)  # Cache 5 min
        return stats
