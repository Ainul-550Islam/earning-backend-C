"""
AbuseIPDB Integration — Threat Intelligence Layer
===================================================
This module wraps the AbuseIPDB API specifically for the
threat_intelligence subsystem. It extends the base integration
with threat-feed-specific logic: auto-flagging IPs in the
MaliciousIPDatabase, tracking report trends, and providing
category-based threat classification.

The base HTTP integration lives in integrations/abuseipdb_integration.py.
This module adds threat-intelligence orchestration on top.
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# AbuseIPDB category codes → threat types
# https://www.abuseipdb.com/categories
CATEGORY_MAP = {
    1:  'DNS_COMPROMISE',
    2:  'DNS_POISONING',
    3:  'FRAUD_ORDERS',
    4:  'DDoS_ATTACK',
    5:  'FTP_BRUTE_FORCE',
    6:  'PING_OF_DEATH',
    7:  'PHISHING',
    8:  'FRAUD_VoIP',
    9:  'OPEN_PROXY',
    10: 'WEB_SPAM',
    11: 'EMAIL_SPAM',
    12: 'BLOG_SPAM',
    13: 'VPN_IP',
    14: 'PORT_SCAN',
    15: 'HACKING',
    16: 'SQL_INJECTION',
    17: 'SPOOFING',
    18: 'BRUTE_FORCE',
    19: 'BAD_WEB_BOT',
    20: 'EXPLOITED_HOST',
    21: 'WEB_APP_ATTACK',
    22: 'SSH_BRUTE_FORCE',
    23: 'IoT_TARGETED',
}

# Categories that map to our ThreatType enum
CATEGORY_TO_THREAT_TYPE = {
    7:  'phishing',
    9:  'proxy',
    10: 'spam',
    11: 'spam',
    12: 'spam',
    13: 'vpn',
    14: 'scanner',
    15: 'malware',
    18: 'brute_force',
    22: 'brute_force',
}


class AbuseIPDBThreatIntelligence:
    """
    Threat-intelligence-layer wrapper for AbuseIPDB.

    Key responsibilities:
    1. Query AbuseIPDB for IP reputation
    2. Auto-flag IPs in MaliciousIPDatabase when confidence is high
    3. Classify threat types from category codes
    4. Track historical report trends
    5. Provide bulk-check capability for threat feed sync
    """

    CONFIDENCE_AUTO_FLAG = 75    # Auto-flag in MaliciousIPDatabase above this
    CONFIDENCE_HIGH_RISK = 50    # Consider high-risk above this
    CONFIDENCE_SUSPICIOUS = 25   # Consider suspicious above this

    def __init__(self, tenant=None):
        self.tenant = tenant

    # ── Single IP Analysis ─────────────────────────────────────────────────

    def analyze(self, ip_address: str, max_age_days: int = 90) -> dict:
        """
        Full threat analysis of an IP via AbuseIPDB.
        Includes auto-flagging and threat type classification.

        Args:
            ip_address:    The IP to analyze.
            max_age_days:  Only count reports newer than this many days.

        Returns:
            Structured threat intelligence dict.
        """
        cache_key = f"pi:ti_abuse:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Call base integration
        try:
            from ..integrations.abuseipdb_integration import AbuseIPDBIntegration
            raw = AbuseIPDBIntegration().check(ip_address, max_age_days=max_age_days)
        except Exception as e:
            logger.warning(f"AbuseIPDB base call failed for {ip_address}: {e}")
            return self._empty(ip_address)

        if raw.get('error'):
            return self._empty(ip_address, error=raw['error'])

        confidence   = raw.get('abuse_confidence_score', 0)
        total_reports = raw.get('total_reports', 0)
        categories   = raw.get('usage_type', [])
        threat_types = self._classify_threat_types(raw.get('categories', []))

        result = {
            'ip_address':            ip_address,
            'source':                'abuseipdb',
            'confidence_score':      confidence,
            'total_reports':         total_reports,
            'distinct_users':        raw.get('num_distinct_users', 0),
            'last_reported':         raw.get('last_reported_at', ''),
            'country_code':          raw.get('country_code', ''),
            'isp':                   raw.get('isp', ''),
            'domain':                raw.get('domain', ''),
            'usage_type':            raw.get('usage_type', ''),
            'is_whitelisted':        raw.get('is_whitelisted', False),
            'threat_types':          threat_types,
            'is_malicious':          confidence >= self.CONFIDENCE_HIGH_RISK,
            'is_high_risk':          confidence >= self.CONFIDENCE_HIGH_RISK,
            'is_suspicious':         confidence >= self.CONFIDENCE_SUSPICIOUS,
            'risk_level':            self._risk_level(confidence),
            'recommended_action':    self._recommended_action(confidence),
            'auto_flagged':          False,
        }

        # Auto-flag in MaliciousIPDatabase if confidence is high
        if confidence >= self.CONFIDENCE_AUTO_FLAG and not raw.get('is_whitelisted'):
            result['auto_flagged'] = self._auto_flag(ip_address, confidence, threat_types)

        cache.set(cache_key, result, 3600)
        return result

    # ── Bulk Check ─────────────────────────────────────────────────────────

    def bulk_analyze(self, ip_list: list) -> dict:
        """
        Analyze multiple IPs and return a summary.
        Used during threat feed synchronization.

        Returns:
            {
                'results': {ip: analysis_dict},
                'malicious_count': int,
                'high_confidence': [ip, ...],
                'auto_flagged': [ip, ...],
            }
        """
        results = {}
        malicious_count = 0
        high_confidence = []
        auto_flagged    = []

        for ip in ip_list:
            try:
                result = self.analyze(ip)
                results[ip] = result
                if result.get('is_malicious'):
                    malicious_count += 1
                if result.get('confidence_score', 0) >= 85:
                    high_confidence.append(ip)
                if result.get('auto_flagged'):
                    auto_flagged.append(ip)
            except Exception as e:
                logger.warning(f"Bulk AbuseIPDB check failed for {ip}: {e}")
                results[ip] = self._empty(ip, error=str(e))

        return {
            'total_checked':  len(ip_list),
            'malicious_count': malicious_count,
            'clean_count':    len(ip_list) - malicious_count,
            'high_confidence': high_confidence,
            'auto_flagged':   auto_flagged,
            'results':        results,
        }

    # ── Report History ─────────────────────────────────────────────────────

    def get_report_trend(self, ip_address: str) -> dict:
        """
        Check if reports for this IP are increasing (emerging threat)
        or decreasing (recovering/cleaned).
        Uses our local MaliciousIPDatabase history.
        """
        try:
            from ..models import MaliciousIPDatabase
            from django.db.models import Count
            from django.db.models.functions import TruncDay
            from datetime import timedelta

            since = timezone.now() - timedelta(days=30)
            entries = (
                MaliciousIPDatabase.objects
                .filter(ip_address=ip_address, created_at__gte=since)
                .annotate(day=TruncDay('created_at'))
                .values('day')
                .annotate(count=Count('id'))
                .order_by('day')
            )
            trend_data = list(entries)

            if len(trend_data) >= 2:
                first_count = trend_data[0]['count']
                last_count  = trend_data[-1]['count']
                if last_count > first_count:
                    trend = 'increasing'
                elif last_count < first_count:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            elif len(trend_data) == 1:
                trend = 'stable'
            else:
                trend = 'no_data'

            return {
                'ip_address':  ip_address,
                'trend':       trend,
                'data_points': trend_data,
                'period_days': 30,
            }
        except Exception as e:
            logger.debug(f"Trend analysis failed for {ip_address}: {e}")
            return {'ip_address': ip_address, 'trend': 'unknown', 'error': str(e)}

    # ── Sync Interface ─────────────────────────────────────────────────────

    def sync_top_abusers(self, limit: int = 100) -> dict:
        """
        Pull the most recently reported IPs from our database
        and re-check them against AbuseIPDB to get fresh scores.
        Used during scheduled threat feed sync.
        """
        try:
            from ..models import MaliciousIPDatabase
            ips = list(
                MaliciousIPDatabase.objects
                .filter(is_active=True)
                .order_by('-last_reported')
                .values_list('ip_address', flat=True)
                .distinct()[:limit]
            )
            return self.bulk_analyze(ips)
        except Exception as e:
            logger.error(f"AbuseIPDB sync_top_abusers failed: {e}")
            return {'error': str(e)}

    # ── Private Helpers ────────────────────────────────────────────────────

    def _classify_threat_types(self, category_ids: list) -> list:
        """Map AbuseIPDB category codes to our internal threat type names."""
        types = set()
        for cat_id in (category_ids or []):
            threat = CATEGORY_TO_THREAT_TYPE.get(int(cat_id))
            if threat:
                types.add(threat)
        return sorted(types)

    def _auto_flag(self, ip_address: str, confidence: int,
                   threat_types: list) -> bool:
        """
        Automatically add this IP to MaliciousIPDatabase
        when confidence is high enough.
        """
        try:
            from ..models import ThreatFeedProvider, MaliciousIPDatabase

            provider, _ = ThreatFeedProvider.objects.get_or_create(
                name='abuseipdb',
                defaults={
                    'display_name': 'AbuseIPDB',
                    'is_active':    True,
                    'priority':     1,
                }
            )

            # Use the primary threat type or fallback to 'malware'
            primary_type = threat_types[0] if threat_types else 'malware'

            MaliciousIPDatabase.objects.update_or_create(
                ip_address=ip_address,
                threat_type=primary_type,
                threat_feed=provider,
                defaults={
                    'confidence_score': round(confidence / 100, 3),
                    'is_active':        True,
                    'last_reported':    timezone.now(),
                }
            )
            return True
        except Exception as e:
            logger.error(f"Auto-flag failed for {ip_address}: {e}")
            return False

    @staticmethod
    def _risk_level(confidence: int) -> str:
        if confidence >= 90: return 'critical'
        if confidence >= 70: return 'high'
        if confidence >= 40: return 'medium'
        if confidence >= 20: return 'low'
        return 'very_low'

    @staticmethod
    def _recommended_action(confidence: int) -> str:
        if confidence >= 85: return 'block'
        if confidence >= 60: return 'challenge'
        if confidence >= 30: return 'flag'
        return 'allow'

    @staticmethod
    def _empty(ip_address: str, error: str = '') -> dict:
        return {
            'ip_address':         ip_address,
            'source':             'abuseipdb',
            'confidence_score':   0,
            'total_reports':      0,
            'is_malicious':       False,
            'is_high_risk':       False,
            'threat_types':       [],
            'risk_level':         'very_low',
            'recommended_action': 'allow',
            'auto_flagged':       False,
            'error':              error,
        }
