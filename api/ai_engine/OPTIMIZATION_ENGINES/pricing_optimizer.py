"""
api/ai_engine/OPTIMIZATION_ENGINES/pricing_optimizer.py
=========================================================
Pricing Optimizer — dynamic reward/offer pricing।
Elasticity-based, competition-aware, ML-driven pricing।
Offerwall reward amounts, subscription prices।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class PricingOptimizer:
    """Dynamic pricing optimization for offers and rewards।"""

    def optimize_reward(self, offer_data: dict, market_data: dict = None) -> dict:
        market_data = market_data or {}
        current_reward  = float(offer_data.get("reward_amount", 100))
        cost_per_action = float(offer_data.get("cost_per_action", current_reward * 0.7))
        market_avg      = float(market_data.get("avg_market_reward", current_reward))
        demand_score    = float(market_data.get("demand_score", 0.5))
        competition     = float(market_data.get("competition_index", 1.0))

        # Base: match market
        optimal = market_avg

        # Demand adjustment
        if demand_score > 0.70:
            optimal *= 0.92    # High demand → lower reward (still attractive)
        elif demand_score < 0.30:
            optimal *= 1.15    # Low demand → higher reward to attract users

        # Competition adjustment
        if competition > 1.2:
            optimal *= 1.05    # High competition → slightly above market

        # Margin floor
        min_reward = cost_per_action * 1.05
        optimal    = max(optimal, min_reward)
        optimal    = round(optimal, 2)

        return {
            "optimal_reward":   optimal,
            "current_reward":   current_reward,
            "change_pct":       round((optimal - current_reward) / max(current_reward, 0.001) * 100, 2),
            "direction":        "increase" if optimal > current_reward else "decrease" if optimal < current_reward else "maintain",
            "margin_pct":       round((optimal - cost_per_action) / max(optimal, 0.001) * 100, 2),
            "market_avg":       market_avg,
        }

    def subscription_pricing(self, tier_data: List[Dict],
                              target_arpu: float) -> List[Dict]:
        """Subscription tier pricing optimization।"""
        result = []
        for tier in tier_data:
            current_price  = float(tier.get("price", 0))
            conversion_rate = float(tier.get("conversion_rate", 0.05))
            value_score    = float(tier.get("value_score", 0.5))

            # Willingness to pay estimate
            wtp = target_arpu / max(conversion_rate, 0.001)
            optimal_price = round(min(wtp * value_score, current_price * 1.5), 2)
            result.append({
                **tier,
                "optimal_price":   optimal_price,
                "current_price":   current_price,
                "price_change":    round(optimal_price - current_price, 2),
                "wtp_estimate":    round(wtp, 2),
            })
        return result

    def volume_discount_optimizer(self, base_price: float,
                                   volume_tiers: List[int]) -> List[Dict]:
        """Volume discount tiers optimize করো।"""
        discounts = []
        for i, volume in enumerate(volume_tiers):
            discount_rate = min(0.05 * (i + 1), 0.30)   # Max 30% discount
            tier_price    = round(base_price * (1 - discount_rate), 2)
            discounts.append({
                "min_volume":    volume,
                "unit_price":    tier_price,
                "discount_pct":  round(discount_rate * 100, 1),
                "savings_per_unit": round(base_price - tier_price, 2),
            })
        return discounts

    def competitive_pricing(self, competitor_prices: List[float],
                             our_value_premium: float = 0.05) -> dict:
        """Competitor prices থেকে optimal price calculate।"""
        if not competitor_prices:
            return {"optimal_price": 0.0}
        avg_price = sum(competitor_prices) / len(competitor_prices)
        min_price = min(competitor_prices)
        max_price = max(competitor_prices)
        optimal   = round(avg_price * (1 + our_value_premium), 2)
        return {
            "optimal_price":     optimal,
            "market_avg":        round(avg_price, 2),
            "market_min":        min_price,
            "market_max":        max_price,
            "vs_market_pct":     round(our_value_premium * 100, 2),
            "positioning":       "premium" if optimal > avg_price else "competitive",
        }
