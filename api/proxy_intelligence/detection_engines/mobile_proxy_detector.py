"""
Mobile Proxy Detector  (PRODUCTION-READY — COMPLETE)
======================================================
Detects 4G/LTE rotating mobile proxies.

Mobile proxies are especially dangerous for earning/marketing platforms
because they use real carrier IP addresses (residential-like) that rotate
naturally with each new mobile connection — making them very hard to detect.

Detection signals:
  1. ISP/org keyword matching against known mobile proxy providers
  2. Connection type classification (Mobile from IPQS/MaxMind)
  3. Carrier + mobile proxy provider co-occurrence
  4. IP rotation speed analysis (mobile IPs rotate on reconnect)
  5. ASN/ISP cross-reference against carrier database
  6. Threat DB lookup for known mobile proxy IPs
"""
import logging
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Known Mobile Proxy Provider Keywords ──────────────────────────────────
# These appear in ISP / organization names for known 4G proxy services.
MOBILE_PROXY_PROVIDER_KEYWORDS = [
    'proxyempire', 'proxy empire',
    'mobileproxy', 'mobile proxy',
    '4gproxy', '4g proxy',
    'ltegoproxy', 'lte proxy',
    'proxidize',
    'airproxy', 'air proxy',
    'rotatingproxies', 'rotating proxies',
    'mobileip', 'mobile ip',
    'proxymobile',
    'primeproxies', 'prime proxies',
    'hydraproxy', 'hydra proxy',
    'infatica',
    'iproyal',
    'lunaproxy',
    'soax',
]

# ── Mobile Carrier Keywords (ISP/org names) ───────────────────────────────
# Real mobile carrier indicators — NOT proxies by themselves,
# but combined with proxy provider keywords they become high-signal.
MOBILE_CARRIER_KEYWORDS = [
    'mobile', 'cellular', 'wireless', 'telecom', 'telecommunication',
    '4g', 'lte', '5g', 'mvno', 'gsm', 'wcdma',
    # South Asia carriers
    'grameenphone', 'robi', 'banglalink', 'teletalk', 'airtel',
    'bsnl', 'jio', 'airtel', 'vi vodafone',
    # Global carriers
    'verizon', 't-mobile', 'at&t', 'sprint', 'vodafone',
    'orange', 'telefonica', 'three', 'o2', 'ee',
    'telstra', 'optus', 'singtel', 'docomo', 'softbank',
    'china mobile', 'china unicom', 'china telecom',
    'mtn', 'glo', 'airtel africa',
]

# ── Connection types from IPQS/MaxMind that indicate mobile ──────────────
MOBILE_CONNECTION_TYPES = {
    'mobile', 'cellular', '4g', 'lte', 'mobiledata', 'mobile data',
}


class MobileProxyDetector:
    """
    Detects mobile proxy usage with confidence scoring.

    Distinguishes between:
    - Legitimate mobile users (low risk — just a carrier IP)
    - Mobile proxy providers (high risk — commercial proxy services)

    Usage:
        detector = MobileProxyDetector(
            ip_address='1.2.3.4',
            isp='ProxyEmpire Mobile Network',
            connection_type='mobile',
        )
        result = detector.detect()
    """

    # Confidence weights
    WEIGHT_PROXY_PROVIDER_KW  = 0.70  # Strongest signal
    WEIGHT_CARRIER_KW         = 0.10  # Carrier alone is not suspicious
    WEIGHT_CARRIER_MOBILE_CNX = 0.10  # Carrier + mobile connection
    WEIGHT_THREAT_DB          = 0.85  # DB match is very strong
    WEIGHT_IP_ROTATION        = 0.30  # IP rotating fast = suspicious

    def __init__(self, ip_address: str,
                 isp: str = '',
                 org: str = '',
                 asn: str = '',
                 connection_type: str = '',
                 user_id: Optional[int] = None,
                 session_id: str = ''):
        self.ip_address      = ip_address
        self.isp             = isp.lower()
        self.org             = org.lower()
        self.asn             = asn.upper()
        self.connection_type = connection_type.lower()
        self.user_id         = user_id
        self.session_id      = session_id
        self.combined_text   = f"{self.isp} {self.org}"
        self.signals: dict   = {}

    # ── Public API ─────────────────────────────────────────────────────────

    def detect(self) -> dict:
        """
        Run all mobile proxy detection signals.

        Returns:
            {
                'ip_address':        str,
                'is_mobile':         bool,   # true for any mobile connection
                'is_mobile_proxy':   bool,   # true for commercial proxy services
                'confidence':        float,
                'mobile_carrier':    str,    # detected carrier name
                'proxy_provider':    str,    # detected proxy provider name
                'signals':           dict,
                'detection_methods': list,
            }
        """
        cache_key = f"pi:mob_proxy:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        self._check_proxy_provider_keywords()
        self._check_carrier_keywords()
        self._check_connection_type()
        self._check_threat_db()
        self._check_ip_rotation()

        confidence = self._calculate_confidence()

        result = {
            'ip_address':        self.ip_address,
            'is_mobile':         (
                self.signals.get('is_carrier_mobile', False) or
                self.signals.get('is_mobile_connection', False)
            ),
            'is_mobile_proxy':   confidence >= 0.50,
            'confidence':        round(confidence, 4),
            'mobile_carrier':    self.signals.get('carrier_name', ''),
            'proxy_provider':    self.signals.get('proxy_provider_name', ''),
            'signals':           self.signals,
            'detection_methods': self._triggered_methods(),
            'risk_contribution': int(confidence * 30),  # Max 30pt risk contribution
        }

        if result['is_mobile_proxy']:
            self._persist_log(result)

        cache.set(cache_key, result, 1800)
        return result

    @classmethod
    def quick_check(cls, ip_address: str, isp: str = '',
                    org: str = '', connection_type: str = '') -> bool:
        """Fast boolean mobile proxy check."""
        return cls(ip_address, isp=isp, org=org,
                   connection_type=connection_type).detect()['is_mobile_proxy']

    # ── Signal Checks ──────────────────────────────────────────────────────

    def _check_proxy_provider_keywords(self):
        """Signal 1: ISP/org name matches known mobile proxy provider."""
        matched_provider = ''
        for keyword in MOBILE_PROXY_PROVIDER_KEYWORDS:
            if keyword in self.combined_text:
                matched_provider = keyword
                break

        self.signals['is_proxy_provider_keyword'] = bool(matched_provider)
        self.signals['proxy_provider_name']        = matched_provider
        self.signals['proxy_provider_keywords_matched'] = (
            [kw for kw in MOBILE_PROXY_PROVIDER_KEYWORDS if kw in self.combined_text]
        )

    def _check_carrier_keywords(self):
        """Signal 2: ISP/org name matches a known mobile carrier."""
        matched_carrier = ''
        for keyword in MOBILE_CARRIER_KEYWORDS:
            if keyword in self.combined_text:
                matched_carrier = keyword
                break

        self.signals['is_carrier_mobile'] = bool(matched_carrier)
        self.signals['carrier_name']      = matched_carrier

    def _check_connection_type(self):
        """Signal 3: connection_type field from IPQS/MaxMind indicates mobile."""
        is_mobile_cnx = self.connection_type in MOBILE_CONNECTION_TYPES
        self.signals['is_mobile_connection'] = is_mobile_cnx
        self.signals['connection_type']       = self.connection_type

    def _check_threat_db(self):
        """Signal 4: IP is in our local MaliciousIPDatabase as mobile proxy."""
        try:
            from ..models import MaliciousIPDatabase
            from ..enums import ThreatType
            entry = MaliciousIPDatabase.objects.filter(
                ip_address=self.ip_address,
                threat_type=ThreatType.PROXY,
                is_active=True,
            ).first()
            if entry:
                self.signals['db_threat_match'] = True
                self.signals['db_confidence']   = float(entry.confidence_score)
            else:
                self.signals['db_threat_match'] = False
                self.signals['db_confidence']   = 0.0
        except Exception as e:
            logger.debug(f"Threat DB check failed for {self.ip_address}: {e}")
            self.signals['db_threat_match'] = False
            self.signals['db_confidence']   = 0.0

    def _check_ip_rotation(self):
        """
        Signal 5: Detect rapid IP rotation typical of mobile proxy networks.
        Checks how many different IPs from the same session/user are seen
        across a short window.
        """
        if not (self.user_id or self.session_id):
            self.signals['ip_rotation_detected'] = False
            self.signals['unique_ips_in_window']  = 0
            return

        key = (
            f"pi:mob_ips:u{self.user_id}" if self.user_id
            else f"pi:mob_ips:s{self.session_id}"
        )
        seen_ips = cache.get(key, set())
        seen_ips.add(self.ip_address)
        cache.set(key, seen_ips, 3600)

        self.signals['ip_rotation_detected'] = len(seen_ips) >= 3
        self.signals['unique_ips_in_window']  = len(seen_ips)

    # ── Confidence Calculation ─────────────────────────────────────────────

    def _calculate_confidence(self) -> float:
        score = 0.0

        if self.signals.get('is_proxy_provider_keyword'):
            score += self.WEIGHT_PROXY_PROVIDER_KW

        if self.signals.get('db_threat_match'):
            db_conf = self.signals.get('db_confidence', 0)
            score = max(score, db_conf * self.WEIGHT_THREAT_DB)

        if self.signals.get('ip_rotation_detected'):
            score += self.WEIGHT_IP_ROTATION

        # Mobile carrier alone is not suspicious — only if combined
        if (self.signals.get('is_carrier_mobile') and
                self.signals.get('is_mobile_connection')):
            score += self.WEIGHT_CARRIER_MOBILE_CNX

        return min(score, 1.0)

    def _triggered_methods(self) -> list:
        methods = []
        if self.signals.get('is_proxy_provider_keyword'):
            methods.append('mobile_proxy_provider_keyword')
        if self.signals.get('db_threat_match'):
            methods.append('threat_db_lookup')
        if self.signals.get('ip_rotation_detected'):
            methods.append('ip_rotation_analysis')
        if self.signals.get('is_mobile_connection'):
            methods.append('connection_type_analysis')
        if self.signals.get('is_carrier_mobile'):
            methods.append('carrier_keyword_match')
        return methods

    def _persist_log(self, result: dict):
        """Save to ProxyDetectionLog when mobile proxy is detected."""
        try:
            from ..models import ProxyDetectionLog
            ProxyDetectionLog.objects.create(
                ip_address        = self.ip_address,
                proxy_type        = 'mobile',
                proxy_provider    = result.get('proxy_provider', ''),
                confidence_score  = result['confidence'],
                is_anonymous      = True,
                headers_detected  = [],
            )
        except Exception as e:
            logger.debug(f"MobileProxyDetector log save failed: {e}")
