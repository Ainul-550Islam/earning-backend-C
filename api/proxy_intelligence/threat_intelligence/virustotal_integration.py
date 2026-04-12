"""
VirusTotal Integration — Threat Intelligence Layer
====================================================
This module wraps the VirusTotal API specifically for the
threat_intelligence subsystem. It extends the base integration
with threat-feed-specific logic: malware URL detection,
file hash lookups (for compromised devices), IP reputation
aggregation from multiple AV engines, and auto-flagging
high-confidence malicious IPs.

The base HTTP integration lives in integrations/virustotal_integration.py.
This module adds threat-intelligence orchestration on top.
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

VT_API_URL_IP      = "https://www.virustotal.com/api/v3/ip_addresses/{ip}"
VT_API_URL_URL     = "https://www.virustotal.com/api/v3/urls"
VT_API_URL_DOMAIN  = "https://www.virustotal.com/api/v3/domains/{domain}"

# Minimum malicious engine votes before we auto-flag
AUTO_FLAG_THRESHOLD = 5


class VirusTotalThreatIntelligence:
    """
    Threat-intelligence-layer wrapper for VirusTotal.

    Key responsibilities:
    1. Query VirusTotal for IP reputation across 70+ AV engines
    2. Auto-flag IPs in MaliciousIPDatabase when enough engines flag it
    3. Domain reputation checks linked to IP addresses
    4. Malware category classification from VT tags
    5. Bulk-check for threat feed synchronization
    """

    def __init__(self, tenant=None):
        self.tenant = tenant
        self.api_key = self._resolve_api_key()

    # ── Credential Resolution ──────────────────────────────────────────────

    def _resolve_api_key(self) -> str:
        """Load API key from IntegrationCredential → settings → env."""
        try:
            from ..models import IntegrationCredential
            qs = IntegrationCredential.objects.filter(
                service='virustotal', is_active=True
            )
            if self.tenant:
                qs = qs.filter(tenant=self.tenant)
            cred = qs.first()
            if cred and cred.api_key:
                IntegrationCredential.objects.filter(pk=cred.pk).update(
                    used_today=cred.used_today + 1
                )
                return cred.api_key
        except Exception:
            pass

        import os
        from django.conf import settings
        return (
            getattr(settings, 'VIRUSTOTAL_API_KEY', None) or
            os.environ.get('VIRUSTOTAL_API_KEY', '')
        )

    # ── IP Reputation ──────────────────────────────────────────────────────

    def analyze_ip(self, ip_address: str) -> dict:
        """
        Full threat analysis of an IP via VirusTotal.
        Aggregates votes from 70+ antivirus / threat intelligence engines.

        Returns:
            Structured threat intelligence dict with engine breakdown.
        """
        cache_key = f"pi:ti_vt:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.api_key:
            return self._empty(ip_address, error='VIRUSTOTAL_API_KEY not configured')

        try:
            import requests
            resp = requests.get(
                VT_API_URL_IP.format(ip=ip_address),
                headers={'x-apikey': self.api_key},
                timeout=15,
            )

            if resp.status_code == 404:
                result = self._empty(ip_address, error='IP not found in VT database')
                cache.set(cache_key, result, 3600)
                return result

            if resp.status_code == 429:
                logger.warning("VirusTotal rate limit exceeded")
                return self._empty(ip_address, error='rate_limited')

            if resp.status_code == 401:
                logger.error("VirusTotal: Invalid API key")
                return self._empty(ip_address, error='invalid_api_key')

            resp.raise_for_status()
            data = resp.json().get('data', {}).get('attributes', {})

            result = self._parse_ip_response(ip_address, data)

            # Auto-flag if enough engines flagged it
            if result['malicious_votes'] >= AUTO_FLAG_THRESHOLD:
                result['auto_flagged'] = self._auto_flag_ip(
                    ip_address,
                    result['malicious_votes'],
                    result['confidence'],
                    result.get('threat_categories', []),
                )
            else:
                result['auto_flagged'] = False

            cache.set(cache_key, result, 3600 * 6)  # Cache 6 hours
            return result

        except Exception as e:
            logger.error(f"VirusTotal IP analysis failed for {ip_address}: {e}")
            return self._empty(ip_address, error=str(e))

    def _parse_ip_response(self, ip_address: str, data: dict) -> dict:
        """Parse VirusTotal IP attributes into our standard format."""
        last_analysis = data.get('last_analysis_stats', {})
        malicious     = int(last_analysis.get('malicious', 0))
        suspicious    = int(last_analysis.get('suspicious', 0))
        harmless      = int(last_analysis.get('harmless', 0))
        undetected    = int(last_analysis.get('undetected', 0))
        total_engines = malicious + suspicious + harmless + undetected

        # Weighted confidence score
        if total_engines > 0:
            confidence = (malicious + suspicious * 0.5) / total_engines
        else:
            confidence = 0.0

        # Extract engines that flagged this IP
        engine_results = data.get('last_analysis_results', {})
        flagging_engines = [
            {'engine': name, 'category': info.get('category', ''), 'result': info.get('result', '')}
            for name, info in engine_results.items()
            if info.get('category') in ('malicious', 'suspicious')
        ]

        # VirusTotal tags/categories
        tags       = data.get('tags', [])
        categories = data.get('categories', {})
        threat_categories = list(set(categories.values())) if categories else []

        return {
            'ip_address':         ip_address,
            'source':             'virustotal',
            'malicious_votes':    malicious,
            'suspicious_votes':   suspicious,
            'harmless_votes':     harmless,
            'undetected_votes':   undetected,
            'total_engines':      total_engines,
            'confidence':         round(confidence, 4),
            'reputation':         int(data.get('reputation', 0)),
            'country':            data.get('country', ''),
            'asn':                str(data.get('asn', '')),
            'as_owner':           data.get('as_owner', ''),
            'last_analysis_date': str(data.get('last_analysis_date', '')),
            'tags':               tags,
            'threat_categories':  threat_categories,
            'flagging_engines':   flagging_engines[:20],   # Top 20 flagging engines
            'is_malicious':       malicious >= AUTO_FLAG_THRESHOLD,
            'is_suspicious':      suspicious >= 3,
            'risk_level':         self._risk_level(malicious, total_engines),
            'recommended_action': self._recommended_action(malicious, total_engines),
        }

    # ── Domain Analysis ────────────────────────────────────────────────────

    def analyze_domain(self, domain: str) -> dict:
        """
        Check a domain's reputation on VirusTotal.
        Useful for identifying phishing/malware-hosting domains
        associated with suspicious IPs.
        """
        cache_key = f"pi:ti_vt_domain:{domain}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not self.api_key:
            return {'domain': domain, 'error': 'API key not configured', 'source': 'virustotal'}

        try:
            import requests
            resp = requests.get(
                VT_API_URL_DOMAIN.format(domain=domain),
                headers={'x-apikey': self.api_key},
                timeout=15,
            )

            if resp.status_code == 404:
                return {'domain': domain, 'not_found': True, 'source': 'virustotal'}

            if resp.status_code == 429:
                return {'domain': domain, 'error': 'rate_limited', 'source': 'virustotal'}

            resp.raise_for_status()
            data  = resp.json().get('data', {}).get('attributes', {})
            stats = data.get('last_analysis_stats', {})

            result = {
                'domain':          domain,
                'source':          'virustotal',
                'malicious_votes': int(stats.get('malicious', 0)),
                'suspicious_votes':int(stats.get('suspicious', 0)),
                'harmless_votes':  int(stats.get('harmless', 0)),
                'reputation':      int(data.get('reputation', 0)),
                'categories':      list(data.get('categories', {}).values()),
                'tags':            data.get('tags', []),
                'creation_date':   str(data.get('creation_date', '')),
                'registrar':       data.get('registrar', ''),
                'is_malicious':    int(stats.get('malicious', 0)) >= 3,
            }
            cache.set(cache_key, result, 3600 * 12)
            return result

        except Exception as e:
            logger.error(f"VirusTotal domain check failed for {domain}: {e}")
            return {'domain': domain, 'error': str(e), 'source': 'virustotal'}

    # ── Bulk Check ─────────────────────────────────────────────────────────

    def bulk_analyze(self, ip_list: list) -> dict:
        """
        Analyze multiple IPs. VirusTotal has strict rate limits
        (4 requests/minute on free tier, 1000/min on paid).
        Adds a small delay between requests on free tier.
        """
        import time

        results       = {}
        malicious     = []
        auto_flagged  = []
        errors        = []

        for i, ip in enumerate(ip_list):
            try:
                result = self.analyze_ip(ip)
                results[ip] = result
                if result.get('is_malicious'):
                    malicious.append(ip)
                if result.get('auto_flagged'):
                    auto_flagged.append(ip)
                if result.get('error'):
                    errors.append(ip)
                # Rate-limit safety: 200ms between requests
                if i % 4 == 3:
                    time.sleep(1.0)
                else:
                    time.sleep(0.2)
            except Exception as e:
                logger.warning(f"Bulk VT check failed for {ip}: {e}")
                results[ip] = self._empty(ip, error=str(e))
                errors.append(ip)

        return {
            'total_checked':   len(ip_list),
            'malicious_count': len(malicious),
            'clean_count':     len(ip_list) - len(malicious),
            'auto_flagged':    auto_flagged,
            'errors':          errors,
            'results':         results,
        }

    # ── Sync Interface ─────────────────────────────────────────────────────

    def sync_known_malicious(self, limit: int = 50) -> dict:
        """
        Re-check our top malicious IPs from MaliciousIPDatabase
        against VirusTotal to get fresh engine votes.
        Note: Respects rate limits — use small limit on free tier.
        """
        try:
            from ..models import MaliciousIPDatabase
            ips = list(
                MaliciousIPDatabase.objects
                .filter(is_active=True)
                .order_by('-confidence_score')
                .values_list('ip_address', flat=True)
                .distinct()[:limit]
            )
            return self.bulk_analyze(ips)
        except Exception as e:
            logger.error(f"VT sync_known_malicious failed: {e}")
            return {'error': str(e)}

    # ── Private Helpers ────────────────────────────────────────────────────

    def _auto_flag(self, ip_address: str, malicious_votes: int,
                   confidence: float, threat_categories: list) -> bool:
        """Add this IP to MaliciousIPDatabase with 'malware' threat type."""
        return self._auto_flag_ip(ip_address, malicious_votes, confidence, threat_categories)

    def _auto_flag_ip(self, ip_address: str, malicious_votes: int,
                      confidence: float, threat_categories: list) -> bool:
        try:
            from ..models import ThreatFeedProvider, MaliciousIPDatabase

            provider, _ = ThreatFeedProvider.objects.get_or_create(
                name='virustotal',
                defaults={
                    'display_name': 'VirusTotal',
                    'is_active':    True,
                    'priority':     2,
                }
            )

            # Determine threat type from VT categories
            threat_type = 'malware'
            for cat in (threat_categories or []):
                cat_lower = cat.lower()
                if 'phish' in cat_lower:
                    threat_type = 'phishing'; break
                if 'spam' in cat_lower:
                    threat_type = 'spam'; break
                if 'botnet' in cat_lower:
                    threat_type = 'botnet'; break
                if 'scan' in cat_lower:
                    threat_type = 'scanner'; break

            MaliciousIPDatabase.objects.update_or_create(
                ip_address=ip_address,
                threat_type=threat_type,
                threat_feed=provider,
                defaults={
                    'confidence_score': round(min(confidence, 1.0), 4),
                    'is_active':        True,
                    'last_reported':    timezone.now(),
                    'additional_data':  {
                        'malicious_votes': malicious_votes,
                        'threat_categories': threat_categories,
                    },
                }
            )
            logger.info(f"VT auto-flagged {ip_address} as {threat_type} "
                        f"(votes={malicious_votes}, conf={confidence:.2f})")
            return True

        except Exception as e:
            logger.error(f"VT auto-flag failed for {ip_address}: {e}")
            return False

    @staticmethod
    def _risk_level(malicious: int, total: int) -> str:
        if total == 0:
            return 'very_low'
        pct = malicious / total
        if pct >= 0.50: return 'critical'
        if pct >= 0.25: return 'high'
        if pct >= 0.10: return 'medium'
        if pct >= 0.03: return 'low'
        return 'very_low'

    @staticmethod
    def _recommended_action(malicious: int, total: int) -> str:
        if malicious >= 10:  return 'block'
        if malicious >= 5:   return 'challenge'
        if malicious >= 2:   return 'flag'
        return 'allow'

    @staticmethod
    def _empty(ip_address: str, error: str = '') -> dict:
        return {
            'ip_address':         ip_address,
            'source':             'virustotal',
            'malicious_votes':    0,
            'suspicious_votes':   0,
            'harmless_votes':     0,
            'total_engines':      0,
            'confidence':         0.0,
            'is_malicious':       False,
            'is_suspicious':      False,
            'risk_level':         'very_low',
            'recommended_action': 'allow',
            'auto_flagged':       False,
            'error':              error,
        }
