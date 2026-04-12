"""
api/ai_engine/PREDICTION_ENGINES/price_optimizer.py
====================================================
Price Optimizer — dynamic pricing prediction।
Offer reward, ad bid, product price optimization।
Demand elasticity + competitive pricing।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class PriceOptimizer:
    """Dynamic price optimization engine।"""

    def optimize(self, item_data: dict, context: dict = None) -> dict:
        context = context or {}
        current = float(item_data.get('current_price', 100))
        cost    = float(item_data.get('cost', current * 0.5))
        demand  = float(context.get('demand_score', 0.5))
        supply  = float(context.get('supply_score', 0.5))
        elasticity = float(item_data.get('price_elasticity', -1.2))

        # Price = cost * markup
        base_markup = 2.0
        demand_adj  = 1.0 + (demand - 0.5) * 0.4   # ±20%
        supply_adj  = 1.0 - (supply - 0.5) * 0.2   # ±10%
        optimal     = round(cost * base_markup * demand_adj * supply_adj, 2)
        optimal     = max(cost * 1.1, min(optimal, current * 2.0))

        revenue_at_optimal = optimal * demand
        revenue_at_current = current * demand
        lift = round((revenue_at_optimal - revenue_at_current) / max(revenue_at_current, 0.001) * 100, 2)

        return {
            'optimal_price':   optimal,
            'current_price':   current,
            'price_change':    round(optimal - current, 2),
            'change_pct':      round((optimal - current) / max(current, 0.001) * 100, 2),
            'direction':       'increase' if optimal > current else 'decrease' if optimal < current else 'maintain',
            'expected_margin': round((optimal - cost) / max(optimal, 0.001) * 100, 2),
            'revenue_lift_pct': lift,
            'confidence':      0.72,
        }

    def ab_price_test(self, control_price: float, test_price: float,
                       control_conversions: int, test_conversions: int,
                       control_views: int, test_views: int) -> dict:
        """A/B price test statistical analysis।"""
        control_cvr = control_conversions / max(control_views, 1)
        test_cvr    = test_conversions    / max(test_views, 1)
        control_rev = control_price * control_conversions
        test_rev    = test_price    * test_conversions
        winner = 'test' if test_rev > control_rev else 'control'
        lift   = round((test_rev - control_rev) / max(control_rev, 0.001) * 100, 2)
        return {
            'winner':          winner,
            'control_revenue': round(control_rev, 2),
            'test_revenue':    round(test_rev, 2),
            'revenue_lift_pct': lift,
            'control_cvr':    round(control_cvr, 4),
            'test_cvr':       round(test_cvr, 4),
            'recommendation': f"Use {'test' if winner == 'test' else 'control'} price ({test_price if winner == 'test' else control_price})",
        }

    def elasticity_estimate(self, price_points: List[float],
                             demand_points: List[float]) -> dict:
        """Price elasticity of demand estimate।"""
        if len(price_points) < 2 or len(demand_points) < 2:
            return {'elasticity': -1.2, 'type': 'assumed'}
        pct_price  = (price_points[-1] - price_points[0]) / max(price_points[0], 0.001)
        pct_demand = (demand_points[-1] - demand_points[0]) / max(demand_points[0], 0.001)
        elasticity = pct_demand / max(abs(pct_price), 0.001) * (-1 if pct_price > 0 else 1)
        return {
            'elasticity':    round(elasticity, 4),
            'type':          'elastic' if abs(elasticity) > 1 else 'inelastic',
            'interpretation': 'Demand sensitive to price' if abs(elasticity) > 1 else 'Demand not sensitive',
        }

    def dynamic_bid_price(self, target_cpa: float, predicted_cvr: float,
                           quality_score: float = 1.0,
                           max_bid: float = None) -> dict:
        """CPA target থেকে optimal bid calculate।"""
        if predicted_cvr <= 0:
            return {'bid': 0.0, 'reason': 'zero_cvr'}
        raw_bid   = target_cpa * predicted_cvr * quality_score
        final_bid = round(min(raw_bid, max_bid) if max_bid else raw_bid, 4)
        final_bid = max(0.01, final_bid)
        return {
            'bid':           final_bid,
            'target_cpa':    target_cpa,
            'predicted_cvr': predicted_cvr,
            'quality_score': quality_score,
            'expected_cpa':  round(final_bid / max(predicted_cvr, 0.001), 2),
        }
