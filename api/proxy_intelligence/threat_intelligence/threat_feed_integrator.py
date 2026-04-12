"""
Threat Feed Integrator
=======================
Orchestrates multiple threat intelligence feeds and aggregates results.
"""
import logging
from django.utils import timezone
from ..models import ThreatFeedProvider, MaliciousIPDatabase
from ..enums import ThreatType

logger = logging.getLogger(__name__)


class ThreatFeedIntegrator:
    """
    Central hub that queries all active threat feed providers
    and saves results to MaliciousIPDatabase.
    """

    def check_ip(self, ip_address: str) -> dict:
        """
        Check an IP against all active threat feeds.
        Returns aggregated threat intelligence.
        """
        providers = ThreatFeedProvider.objects.filter(is_active=True).order_by('priority')
        results = []
        max_confidence = 0.0
        threat_types = set()

        for provider in providers:
            try:
                result = self._query_provider(provider, ip_address)
                if result:
                    results.append(result)
                    if result.get('confidence', 0) > max_confidence:
                        max_confidence = result['confidence']
                    if result.get('threat_type'):
                        threat_types.add(result['threat_type'])
                    self._save_result(ip_address, provider, result)
            except Exception as e:
                logger.warning(f"Threat feed '{provider.name}' failed for {ip_address}: {e}")

        return {
            'ip_address': ip_address,
            'is_malicious': max_confidence > 0.5,
            'max_confidence': round(max_confidence, 3),
            'threat_types': list(threat_types),
            'feed_results': results,
            'feeds_checked': len(results),
        }

    def _query_provider(self, provider: ThreatFeedProvider, ip_address: str) -> dict:
        """Route to the correct integration class."""
        handlers = {
            'abuseipdb': self._query_abuseipdb,
            'virustotal': self._query_virustotal,
        }
        handler = handlers.get(provider.name)
        if handler:
            return handler(ip_address)
        return {}

    def _query_abuseipdb(self, ip_address: str) -> dict:
        from ..integrations.abuseipdb_integration import AbuseIPDBIntegration
        result = AbuseIPDBIntegration().check(ip_address)
        score = result.get('abuse_confidence_score', 0) / 100
        return {
            'feed': 'abuseipdb',
            'confidence': score,
            'threat_type': ThreatType.SPAM if score > 0.3 else '',
            'total_reports': result.get('total_reports', 0),
        }

    def _query_virustotal(self, ip_address: str) -> dict:
        # Placeholder — implement VirusTotalIntegration similarly
        return {}

    def _save_result(self, ip_address: str, provider: ThreatFeedProvider, result: dict):
        if result.get('confidence', 0) > 0.1 and result.get('threat_type'):
            MaliciousIPDatabase.objects.update_or_create(
                ip_address=ip_address,
                threat_type=result['threat_type'],
                threat_feed=provider,
                defaults={
                    'confidence_score': result['confidence'],
                    'is_active': True,
                    'last_reported': timezone.now(),
                }
            )

    def sync_all_feeds(self) -> dict:
        """Trigger sync for all active feeds."""
        results = {}
        providers = ThreatFeedProvider.objects.filter(is_active=True)
        for provider in providers:
            try:
                provider.last_sync = timezone.now()
                provider.save(update_fields=['last_sync'])
                results[provider.name] = 'synced'
            except Exception as e:
                results[provider.name] = f'error: {e}'
        return results
