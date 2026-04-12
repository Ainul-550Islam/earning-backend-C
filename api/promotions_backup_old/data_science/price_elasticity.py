# =============================================================================
# api/promotions/data_science/price_elasticity.py
# Price Elasticity — Reward পরিবর্তনে task completion কেমন বদলায়
# Point elasticity, arc elasticity, optimal price finder
# =============================================================================

import logging
import math
from dataclasses import dataclass
from django.core.cache import cache

logger = logging.getLogger('data_science.price_elasticity')
CACHE_PREFIX_PE = 'ds:pe:{}'


@dataclass
class ElasticityResult:
    platform:         str
    category:         str
    elasticity:       float      # Price elasticity of demand (PED)
    interpretation:   str        # 'elastic', 'inelastic', 'unit_elastic'
    optimal_price_usd: float     # Revenue-maximizing price
    current_price_usd: float
    price_suggestion:  str       # 'increase', 'decrease', 'maintain'
    expected_volume_change: float  # % change if optimal price applied
    revenue_impact_usd:    float


@dataclass
class PricePoint:
    price_usd:  float
    volume:     int        # Task completions at this price
    revenue:    float      # Total revenue


class PriceElasticityAnalyzer:
    """
    Price Elasticity of Demand (PED) analysis।

    PED = (% change in quantity) / (% change in price)

    Interpretation:
    |PED| > 1  → Elastic: price বাড়ালে volume বেশি কমে (revenue কমে)
    |PED| < 1  → Inelastic: price বাড়ালে volume কম কমে (revenue বাড়ে)
    |PED| = 1  → Unit elastic: revenue unchanged

    Use cases:
    - Optimal reward price set করা
    - Platform commission rate decide করা
    - Campaign budget recommendation
    """

    def analyze(self, platform: str, category: str) -> ElasticityResult:
        """Platform + category এর price elasticity analyze করে।"""
        cache_key = CACHE_PREFIX_PE.format(f'{platform}:{category}')
        cached    = cache.get(cache_key)
        if cached:
            return ElasticityResult(**cached)

        price_points = self._collect_price_volume_data(platform, category)

        if len(price_points) < 2:
            return self._default_result(platform, category)

        ped              = self._calculate_arc_elasticity(price_points)
        current_price    = price_points[-1].price_usd
        optimal_price    = self._find_optimal_price(price_points, ped)

        if abs(ped) > 1.2:
            interpretation = 'elastic'
            suggestion     = 'decrease' if current_price > optimal_price else 'increase'
        elif abs(ped) < 0.8:
            interpretation = 'inelastic'
            suggestion     = 'increase'  # Revenue বাড়বে
        else:
            interpretation = 'unit_elastic'
            suggestion     = 'maintain'

        # Volume change estimate
        price_change_pct = (optimal_price - current_price) / max(current_price, 0.001)
        vol_change_pct   = ped * price_change_pct

        # Revenue impact
        current_vol      = price_points[-1].volume
        new_vol          = current_vol * (1 + vol_change_pct)
        rev_impact       = (new_vol * optimal_price) - price_points[-1].revenue

        result = ElasticityResult(
            platform=platform, category=category,
            elasticity=round(ped, 3), interpretation=interpretation,
            optimal_price_usd=round(optimal_price, 4),
            current_price_usd=round(current_price, 4),
            price_suggestion=suggestion,
            expected_volume_change=round(vol_change_pct * 100, 1),
            revenue_impact_usd=round(rev_impact, 2),
        )
        cache.set(cache_key, result.__dict__, timeout=3600 * 12)
        return result

    def optimal_reward_for_budget(self, budget_usd: float, target_completions: int) -> float:
        """Budget ও target completions দিলে optimal reward calculate করে।"""
        if target_completions <= 0:
            return 0.0
        base_reward = budget_usd / target_completions
        # Apply 1.1x factor for buffer
        return round(min(base_reward * 1.1, budget_usd * 0.8 / max(target_completions, 1)), 4)

    def simulate_price_change(
        self, current_price: float, new_price: float, current_volume: int, ped: float
    ) -> dict:
        """Price change এ কী হবে তা simulate করে।"""
        price_change_pct = (new_price - current_price) / max(current_price, 0.001)
        vol_change_pct   = ped * price_change_pct
        new_volume       = max(0, int(current_volume * (1 + vol_change_pct)))
        current_rev      = current_price * current_volume
        new_rev          = new_price * new_volume

        return {
            'current_price':   current_price,
            'new_price':       new_price,
            'current_volume':  current_volume,
            'new_volume':      new_volume,
            'volume_change':   new_volume - current_volume,
            'current_revenue': round(current_rev, 2),
            'new_revenue':     round(new_rev, 2),
            'revenue_change':  round(new_rev - current_rev, 2),
            'elasticity_used': ped,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _collect_price_volume_data(self, platform: str, category: str) -> list:
        try:
            from api.promotions.models import Campaign, TaskSubmission
            from api.promotions.choices import SubmissionStatus
            from django.db.models import Count, Avg

            data = (
                Campaign.objects
                .filter(platform__name__iexact=platform, category__name__iexact=category)
                .annotate(
                    completions=Count('submissions', filter=__import__('django').db.models.Q(submissions__status=SubmissionStatus.APPROVED)),
                )
                .values('reward_per_task_usd', 'completions')
                .order_by('reward_per_task_usd')
            )
            points = []
            for d in data:
                price = float(d.get('reward_per_task_usd') or 0)
                vol   = d.get('completions') or 0
                if price > 0:
                    points.append(PricePoint(price_usd=price, volume=vol, revenue=price * vol))
            return points
        except Exception:
            return []

    @staticmethod
    def _calculate_arc_elasticity(points: list) -> float:
        """Arc elasticity — midpoint method।"""
        if len(points) < 2:
            return -1.0
        elasticities = []
        for i in range(1, len(points)):
            p1, p2 = points[i-1], points[i]
            if p1.price_usd == p2.price_usd:
                continue
            midpoint_price = (p1.price_usd + p2.price_usd) / 2
            midpoint_vol   = (p1.volume + p2.volume) / 2 or 1
            pct_change_vol   = (p2.volume - p1.volume) / midpoint_vol
            pct_change_price = (p2.price_usd - p1.price_usd) / midpoint_price
            if pct_change_price != 0:
                elasticities.append(pct_change_vol / pct_change_price)
        if not elasticities:
            return -1.0
        return round(sum(elasticities) / len(elasticities), 3)

    @staticmethod
    def _find_optimal_price(points: list, ped: float) -> float:
        """Revenue-maximizing price।"""
        if not points:
            return 0.05
        max_rev_point = max(points, key=lambda p: p.revenue)
        return max_rev_point.price_usd

    def _default_result(self, platform: str, category: str) -> ElasticityResult:
        return ElasticityResult(
            platform=platform, category=category,
            elasticity=-1.0, interpretation='unknown',
            optimal_price_usd=0.05, current_price_usd=0.05,
            price_suggestion='maintain', expected_volume_change=0.0,
            revenue_impact_usd=0.0,
        )
