# api/offer_inventory/ai_optimization/a_b_testing.py
"""
A/B Testing Engine.
Consistent hashing ensures same user always gets same variant.
Tracks conversion metrics per variant.
"""
import hashlib
import logging
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ABTestingEngine:
    """Consistent A/B assignment + metric tracking."""

    @staticmethod
    def get_variant(test_name: str, user_id,
                    traffic_split: float = 0.5) -> str:
        """
        Deterministic variant assignment.
        Same user always → same variant (consistent hashing).
        """
        raw      = f'{test_name}:{user_id}'
        hash_int = int(hashlib.md5(raw.encode()).hexdigest(), 16)
        bucket   = (hash_int % 10000) / 10000.0
        return 'A' if bucket < traffic_split else 'B'

    @staticmethod
    def record_event(test_name: str, variant: str,
                     event: str, value: float = 1.0):
        """Record a test event (impression, click, conversion, revenue)."""
        key     = f'ab:{test_name}:{variant}:{event}'
        current = cache.get(key) or {'count': 0, 'total': 0.0}
        current['count'] += 1
        current['total'] += value
        cache.set(key, current, 86400 * 14)   # 2-week window

    @staticmethod
    def get_results(test_name: str) -> dict:
        """Fetch current A/B results."""
        results = {}
        for variant in ('A', 'B'):
            for event in ('impression', 'click', 'conversion', 'revenue'):
                key  = f'ab:{test_name}:{variant}:{event}'
                data = cache.get(key) or {'count': 0, 'total': 0.0}
                results[f'{variant}_{event}_count'] = data['count']
                results[f'{variant}_{event}_total'] = round(data['total'], 4)

        # CVR per variant
        for v in ('A', 'B'):
            clicks = results.get(f'{v}_click_count', 0)
            convs  = results.get(f'{v}_conversion_count', 0)
            results[f'{v}_cvr'] = round(convs / clicks * 100, 2) if clicks else 0.0

        return results

    @staticmethod
    def determine_winner(test_name: str,
                         min_conversions: int = 100) -> str:
        """
        Determine winning variant based on CVR.
        Returns 'A', 'B', or '' (insufficient data).
        """
        results = ABTestingEngine.get_results(test_name)
        a_conv  = results.get('A_conversion_count', 0)
        b_conv  = results.get('B_conversion_count', 0)

        if a_conv < min_conversions or b_conv < min_conversions:
            return ''   # Insufficient data

        a_cvr = results.get('A_cvr', 0.0)
        b_cvr = results.get('B_cvr', 0.0)

        winner = 'A' if a_cvr >= b_cvr else 'B'
        logger.info(f'A/B winner for {test_name}: {winner} (A={a_cvr}% B={b_cvr}%)')
        return winner

    @staticmethod
    def save_winner(test_id: str, winner: str, user=None):
        """Persist winner to ABTestGroup model."""
        from api.offer_inventory.models import ABTestGroup
        from django.utils import timezone
        ABTestGroup.objects.filter(id=test_id).update(
            winner   =winner,
            status   ='completed',
            ended_at =timezone.now(),
        )
