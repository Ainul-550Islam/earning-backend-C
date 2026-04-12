"""IP Reputation Service — aggregates reputation from multiple sources."""
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class IPReputationService:
    """Calculates a unified reputation score (0-100, higher = worse)."""

    def __init__(self, tenant=None):
        self.tenant = tenant

    def get_reputation(self, ip_address: str) -> dict:
        cache_key = f"pi:rep:{ip_address}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        scores = []
        sources = {}

        # AbuseIPDB
        try:
            from ..integrations.abuseipdb_integration import AbuseIPDBIntegration
            r = AbuseIPDBIntegration().check(ip_address)
            score = r.get('abuse_confidence_score', 0)
            scores.append(score)
            sources['abuseipdb'] = score
        except Exception:
            pass

        # IPQS
        try:
            from ..integrations.ipqualityscore_integration import IPQualityScoreIntegration
            r = IPQualityScoreIntegration(self.tenant).check(ip_address)
            if r.get('success'):
                score = r.get('fraud_score', 0)
                scores.append(score)
                sources['ipqs'] = score
        except Exception:
            pass

        # Malicious DB
        try:
            from ..models import MaliciousIPDatabase
            entries = MaliciousIPDatabase.objects.filter(ip_address=ip_address, is_active=True)
            if entries.exists():
                db_score = int(max(e.confidence_score for e in entries) * 100)
                scores.append(db_score)
                sources['local_db'] = db_score
        except Exception:
            pass

        avg_score = int(sum(scores) / len(scores)) if scores else 0
        result = {
            'ip_address': ip_address,
            'reputation_score': avg_score,
            'sources': sources,
            'is_malicious': avg_score >= 50,
            'sources_checked': len(sources),
        }
        cache.set(cache_key, result, 3600)
        return result
