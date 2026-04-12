"""Spam Detector — identifies IPs used for spam campaigns."""
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)


class SpamDetector:
    def __init__(self, ip_address: str, tenant=None):
        self.ip_address = ip_address
        self.tenant = tenant

    def check(self) -> dict:
        cache_key = f"pi:spam:{self.ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        db_result    = self._check_db()
        abuse_result = self._check_abuseipdb()
        confidence   = max(db_result.get('confidence', 0),
                           abuse_result.get('abuse_confidence_score', 0) / 100)

        result = {
            'ip_address':   self.ip_address,
            'is_spam':      confidence >= 0.4,
            'confidence':   round(confidence, 3),
            'report_count': abuse_result.get('total_reports', 0),
            'db_flagged':   db_result.get('found', False),
        }
        cache.set(cache_key, result, 3600)
        return result

    def _check_db(self) -> dict:
        try:
            from ..models import MaliciousIPDatabase
            from ..enums import ThreatType
            entry = MaliciousIPDatabase.objects.filter(
                ip_address=self.ip_address, threat_type=ThreatType.SPAM, is_active=True
            ).first()
            if entry:
                return {'found': True, 'confidence': float(entry.confidence_score),
                        'report_count': entry.report_count}
        except Exception:
            pass
        return {'found': False, 'confidence': 0.0}

    def _check_abuseipdb(self) -> dict:
        try:
            from ..integrations.abuseipdb_integration import AbuseIPDBIntegration
            return AbuseIPDBIntegration().check(self.ip_address)
        except Exception:
            return {'abuse_confidence_score': 0, 'total_reports': 0}

    @classmethod
    def flag_as_spam(cls, ip_address: str, feed_name: str = 'manual',
                     confidence: float = 0.8) -> bool:
        from ..models import ThreatFeedProvider, MaliciousIPDatabase
        from ..enums import ThreatType
        from django.utils import timezone
        try:
            provider, _ = ThreatFeedProvider.objects.get_or_create(
                name=feed_name,
                defaults={'display_name': feed_name, 'is_active': True, 'priority': 99}
            )
            MaliciousIPDatabase.objects.update_or_create(
                ip_address=ip_address, threat_type=ThreatType.SPAM,
                threat_feed=provider,
                defaults={'confidence_score': confidence, 'is_active': True,
                          'last_reported': timezone.now()}
            )
            cache.delete(f"pi:spam:{ip_address}")
            return True
        except Exception as e:
            logger.error(f"Flag spam failed: {e}")
            return False
