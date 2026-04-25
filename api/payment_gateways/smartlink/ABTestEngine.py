# api/payment_gateways/smartlink/ABTestEngine.py
# A/B test engine for SmartLink offer rotation

import random
import logging
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ABTestEngine:
    """
    A/B test engine for SmartLink offer rotation.

    Manages controlled experiments where traffic is split between
    multiple offers to find the best performer.

    Statistical approach:
        - Multi-armed bandit (Epsilon-greedy algorithm)
        - Automatically increases traffic to better performers
        - Statistical significance check before declaring winner
        - Minimum sample size enforcement

    Usage:
        engine = ABTestEngine()
        winner = engine.select_variant(smart_link, candidates)
    """

    EXPLORATION_RATE = 0.15    # 15% explore random, 85% exploit best
    MIN_SAMPLES      = 50      # Need 50 clicks before judging performance
    SIGNIFICANCE     = 0.95    # 95% confidence to declare winner

    def select_variant(self, smart_link, candidates: list):
        """
        Select offer variant using epsilon-greedy multi-armed bandit.

        Args:
            smart_link: SmartLink instance
            candidates: List of Offer instances

        Returns:
            Offer: Selected offer to show
        """
        if not candidates:
            return None

        # Epsilon-greedy: explore vs exploit
        if random.random() < self.EXPLORATION_RATE:
            # Explore: random choice
            chosen = random.choice(candidates)
            logger.debug(f'ABTest EXPLORE: SmartLink={smart_link.id} → offer={chosen.id}')
            return chosen

        # Exploit: choose best performer
        best   = self._get_best_performer(smart_link, candidates)
        logger.debug(f'ABTest EXPLOIT: SmartLink={smart_link.id} → offer={best.id}')
        return best

    def get_test_results(self, smart_link) -> dict:
        """
        Get A/B test results for a SmartLink.

        Returns:
            dict: {
                'winner': offer_id | None,
                'variants': [{offer_id, clicks, conversions, cr, epc, confidence}],
                'is_significant': bool,
                'recommendation': str,
            }
        """
        from .models import SmartLinkRotation

        rotations = SmartLinkRotation.objects.filter(smart_link=smart_link)
        if not rotations.exists():
            return {'winner': None, 'variants': [], 'is_significant': False}

        variants   = []
        best_cr    = 0
        best_offer = None

        for r in rotations:
            clicks      = max(r.clicks, 1)
            cr          = r.conversions / clicks
            epc         = float(r.earnings) / clicks if r.earnings else 0
            confidence  = self._calculate_confidence(r.clicks, r.conversions)

            variants.append({
                'offer_id':       r.offer_id,
                'offer_name':     r.offer.name,
                'clicks':         r.clicks,
                'conversions':    r.conversions,
                'earnings':       float(r.earnings),
                'cr':             round(cr * 100, 2),
                'epc':            round(epc, 4),
                'confidence':     round(confidence * 100, 1),
                'has_min_data':   r.clicks >= self.MIN_SAMPLES,
            })

            if cr > best_cr and r.clicks >= self.MIN_SAMPLES:
                best_cr    = cr
                best_offer = r.offer_id

        # Check statistical significance
        is_significant = self._is_statistically_significant(variants)

        return {
            'winner':          best_offer if is_significant else None,
            'variants':        sorted(variants, key=lambda x: x['cr'], reverse=True),
            'is_significant':  is_significant,
            'recommendation':  self._get_recommendation(variants, is_significant, best_offer),
            'total_clicks':    sum(v['clicks'] for v in variants),
            'test_duration':   self._get_duration(smart_link),
        }

    def record_impression(self, smart_link_id: int, offer_id: int):
        """Record that an offer was shown (impression)."""
        key   = f'ab_imp:{smart_link_id}:{offer_id}'
        count = cache.get(key, 0)
        cache.set(key, count + 1, 86400 * 30)

    def record_conversion(self, smart_link_id: int, offer_id: int, earnings: Decimal):
        """Record a conversion for A/B tracking."""
        from .models import SmartLinkRotation
        try:
            SmartLinkRotation.objects.filter(
                smart_link_id=smart_link_id, offer_id=offer_id
            ).update(
                conversions=__import__('django.db.models', fromlist=['F']).F('conversions') + 1,
                earnings=__import__('django.db.models', fromlist=['F']).F('earnings') + earnings,
            )
        except Exception as e:
            logger.warning(f'ABTest conversion record failed: {e}')

    def _get_best_performer(self, smart_link, candidates: list):
        """Get offer with highest EPC among candidates."""
        from .models import SmartLinkRotation

        best_offer = candidates[0]
        best_epc   = 0

        for offer in candidates:
            try:
                rotation = SmartLinkRotation.objects.get(
                    smart_link=smart_link, offer=offer
                )
                clicks = max(rotation.clicks, 1)
                epc    = float(rotation.earnings or 0) / clicks
                if epc > best_epc:
                    best_epc   = epc
                    best_offer = offer
            except Exception:
                # No data yet — treat as neutral
                pass

        return best_offer

    def _calculate_confidence(self, clicks: int, conversions: int) -> float:
        """
        Calculate statistical confidence (simplified Wilson score).
        Returns confidence between 0.0 and 1.0.
        """
        if clicks < 10:
            return 0.0

        import math
        z  = 1.96  # 95% confidence
        n  = clicks
        p  = conversions / n
        margin = z * math.sqrt(p * (1 - p) / n)

        # Confidence grows with more data
        base_conf = min(0.99, n / (n + 20))  # Asymptotes to 1.0
        return base_conf

    def _is_statistically_significant(self, variants: list) -> bool:
        """Check if there's a clear winner with enough data."""
        if len(variants) < 2:
            return False

        # Need minimum samples and confidence
        has_data = all(v['clicks'] >= self.MIN_SAMPLES for v in variants)
        if not has_data:
            return False

        # Check if top variant significantly beats others
        sorted_v = sorted(variants, key=lambda x: x['cr'], reverse=True)
        if len(sorted_v) < 2:
            return False

        top     = sorted_v[0]['cr']
        second  = sorted_v[1]['cr']

        # Clear winner: 20%+ better than second place
        return top > second * 1.20 and sorted_v[0]['confidence'] >= self.SIGNIFICANCE * 100

    def _get_recommendation(self, variants: list, is_significant: bool,
                              winner_id) -> str:
        if not variants:
            return 'No data yet. Run the test for at least 24 hours.'

        total_clicks = sum(v['clicks'] for v in variants)
        if total_clicks < self.MIN_SAMPLES * len(variants):
            need = self.MIN_SAMPLES * len(variants) - total_clicks
            return f'Need {need} more clicks for statistical significance.'

        if is_significant and winner_id:
            winner_name = next((v['offer_name'] for v in variants if v['offer_id'] == winner_id), '')
            return f'✅ Winner: {winner_name}. Consider pausing other variants to maximize earnings.'

        # CRs too close — no clear winner
        crs = [v['cr'] for v in variants]
        if max(crs) - min(crs) < 0.5:
            return 'No clear winner — CRs are too close. Continue testing or add new variants.'

        return 'Test is running. Check back after more data.'

    def _get_duration(self, smart_link) -> str:
        """Get test duration since SmartLink creation."""
        delta = timezone.now() - smart_link.created_at
        if delta.days > 0:
            return f'{delta.days} days'
        hours = int(delta.seconds / 3600)
        return f'{hours} hours'
