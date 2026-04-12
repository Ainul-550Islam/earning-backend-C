"""
api/ai_engine/OPTIMIZATION_ENGINES/price_optimizer.py
======================================================
Price Optimizer — dynamic pricing for offers/rewards।
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class PriceOptimizer:
    """Demand-based dynamic pricing।"""

    def optimize(self, item_id: str, base_price: float, context: dict = None) -> dict:
        context = context or {}
        demand_score    = context.get('demand_score', 0.5)
        competition     = context.get('competition_factor', 1.0)
        user_ltv_segment = context.get('ltv_segment', 'medium')

        multiplier = 1.0
        if demand_score > 0.8: multiplier *= 1.20
        elif demand_score > 0.6: multiplier *= 1.10
        elif demand_score < 0.3: multiplier *= 0.85

        ltv_discounts = {'premium': 1.15, 'high': 1.05, 'medium': 1.0, 'low': 0.90}
        multiplier *= ltv_discounts.get(user_ltv_segment, 1.0)
        multiplier /= max(0.5, competition)

        optimized_price = round(base_price * multiplier, 2)

        return {
            'item_id':         item_id,
            'base_price':      base_price,
            'optimized_price': optimized_price,
            'multiplier':      round(multiplier, 4),
            'reason':          self._reason(multiplier),
        }

    def _reason(self, mult: float) -> str:
        if mult > 1.1: return 'High demand — price increased'
        if mult < 0.9: return 'Low demand — price discounted'
        return 'Stable pricing'


"""
api/ai_engine/OPTIMIZATION_ENGINES/bid_optimizer.py
====================================================
Bid Optimizer — CPC/CPA bid optimization।
"""


class BidOptimizer:
    """Ad bid optimization for maximum ROI।"""

    def optimize_bid(self, campaign_id: str, current_bid: float,
                     performance_data: dict) -> dict:
        ctr  = performance_data.get('ctr', 0.02)
        cvr  = performance_data.get('conversion_rate', 0.05)
        cpa  = performance_data.get('target_cpa', 100.0)

        expected_value = ctr * cvr * cpa
        optimal_bid    = round(expected_value * 0.8, 2)
        optimal_bid    = max(0.01, min(optimal_bid, current_bid * 1.5))

        return {
            'campaign_id':   campaign_id,
            'current_bid':   current_bid,
            'optimal_bid':   optimal_bid,
            'expected_cpa':  round(cpa, 2),
            'bid_change_pct': round((optimal_bid - current_bid) / current_bid * 100, 2),
        }


"""
api/ai_engine/OPTIMIZATION_ENGINES/budget_optimizer.py
=======================================================
Budget Optimizer — campaign budget allocation।
"""


class BudgetOptimizer:
    """Optimal budget allocation across campaigns/channels。"""

    def allocate(self, total_budget: float, channels: List[Dict]) -> List[Dict]:
        """
        ROI অনুযায়ী budget allocate করো।
        channels: [{'name': 'email', 'roi': 2.5, 'min_budget': 100}, ...]
        """
        if not channels or total_budget <= 0:
            return []

        total_roi = sum(max(0.01, c.get('roi', 1.0)) for c in channels)
        result = []
        remaining = total_budget

        for ch in channels:
            roi_share  = ch.get('roi', 1.0) / total_roi
            allocation = round(total_budget * roi_share, 2)
            allocation = max(ch.get('min_budget', 0), allocation)
            allocation = min(allocation, remaining)
            result.append({**ch, 'allocated_budget': allocation, 'budget_share': round(roi_share, 4)})
            remaining -= allocation

        return result
