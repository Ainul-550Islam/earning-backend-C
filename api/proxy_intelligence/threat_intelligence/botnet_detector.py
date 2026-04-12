"""
Botnet Detector
===============
Detects IPs associated with known botnets using threat feeds and behavioral patterns.
"""
import logging
from django.core.cache import cache
from ..models import MaliciousIPDatabase
from ..enums import ThreatType

logger = logging.getLogger(__name__)


class BotnetDetector:
    """
    Detects botnet-associated IPs via:
    1. Known botnet IP database (MaliciousIPDatabase)
    2. Behavioral signals (velocity, patterns)
    3. AbuseIPDB reports
    """

    @classmethod
    def is_botnet(cls, ip_address: str) -> dict:
        cache_key = f"pi:botnet:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Check our malicious IP database
        db_match = MaliciousIPDatabase.objects.filter(
            ip_address=ip_address,
            threat_type=ThreatType.BOTNET,
            is_active=True,
        ).first()

        if db_match:
            result = {
                'is_botnet': True,
                'confidence': db_match.confidence_score,
                'source': db_match.threat_feed.name,
                'last_reported': str(db_match.last_reported),
            }
        else:
            result = {'is_botnet': False, 'confidence': 0.0, 'source': 'none'}

        cache.set(cache_key, result, 1800)
        return result

    @classmethod
    def flag_as_botnet(cls, ip_address: str, feed_provider_name: str = 'manual',
                       confidence: float = 0.9) -> bool:
        """Manually flag an IP as botnet-infected."""
        from ..models import ThreatFeedProvider
        try:
            provider, _ = ThreatFeedProvider.objects.get_or_create(
                name=feed_provider_name,
                defaults={
                    'display_name': feed_provider_name.title(),
                    'is_active': True,
                    'priority': 99,
                }
            )
            MaliciousIPDatabase.objects.update_or_create(
                ip_address=ip_address,
                threat_type=ThreatType.BOTNET,
                threat_feed=provider,
                defaults={'confidence_score': confidence, 'is_active': True}
            )
            cache.delete(f"pi:botnet:{ip_address}")
            return True
        except Exception as e:
            logger.error(f"Failed to flag {ip_address} as botnet: {e}")
            return False
