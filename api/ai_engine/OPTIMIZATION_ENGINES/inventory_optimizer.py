"""
api/ai_engine/OPTIMIZATION_ENGINES/inventory_optimizer.py
==========================================================
Inventory Optimizer — offer/ad budget ও slot management।
Fill rate maximize করো, waste minimize করো।
Ad network waterfall ও direct offer inventory balance।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class InventoryOptimizer:
    """
    Digital inventory optimization।
    Offer slots, ad impressions, budget allocation।
    """

    def optimize_allocation(self, offers: List[Dict],
                             total_budget: float) -> List[Dict]:
        """Budget-constrained offer inventory allocation।"""
        if not offers or total_budget <= 0:
            return offers

        # Priority score compute করো
        for o in offers:
            ctr    = float(o.get("expected_ctr", 0.05))
            cvr    = float(o.get("expected_cvr", 0.10))
            reward = float(o.get("reward_amount", 100))
            o["priority_score"] = round(ctr * cvr * reward, 4)

        total_priority = sum(o["priority_score"] for o in offers) or 1
        allocated_sum  = 0
        result         = []

        for i, offer in enumerate(sorted(offers, key=lambda x: x["priority_score"], reverse=True)):
            share       = offer["priority_score"] / total_priority
            allocation  = round(total_budget * share, 2)
            if i == len(offers) - 1:
                allocation = round(total_budget - allocated_sum, 2)

            min_budget  = offer.get("min_budget", 0)
            allocation  = max(allocation, min_budget)

            result.append({
                **offer,
                "allocated_budget": allocation,
                "budget_share_pct": round(share * 100, 2),
            })
            allocated_sum += allocation

        return result

    def forecast_inventory(self, historical_impressions: List[float],
                            days_ahead: int = 7) -> dict:
        """Future inventory (impressions/slots) forecast।"""
        if not historical_impressions:
            return {"forecast": [], "method": "no_data"}

        n   = len(historical_impressions)
        avg = sum(historical_impressions) / n
        trend = (historical_impressions[-1] - historical_impressions[0]) / max(n - 1, 1)
        forecast = [round(max(0, avg + trend * (i + 1)), 0) for i in range(days_ahead)]

        return {
            "forecast":      forecast,
            "avg_daily":     round(avg, 0),
            "trend":         "growing" if trend > 0 else "declining" if trend < 0 else "stable",
            "days_ahead":    days_ahead,
            "total_forecast": round(sum(forecast), 0),
        }

    def detect_inventory_waste(self, inventory_data: dict) -> dict:
        """Unused inventory ও waste detect করো।"""
        total       = inventory_data.get("total_slots", 0)
        filled      = inventory_data.get("filled_slots", 0)
        fill_rate   = filled / max(total, 1)
        wasted      = total - filled
        waste_value = wasted * inventory_data.get("avg_cpm", 1.0) / 1000

        alerts = []
        if fill_rate < 0.70:
            alerts.append(f"Low fill rate: {fill_rate:.1%} — add backup networks")
        if fill_rate < 0.50:
            alerts.append("CRITICAL: >50% inventory wasted — immediate action needed")

        return {
            "total_slots":   total,
            "filled_slots":  filled,
            "wasted_slots":  wasted,
            "fill_rate":     round(fill_rate, 4),
            "waste_value":   round(waste_value, 2),
            "alerts":        alerts,
            "status":        "healthy" if fill_rate >= 0.85 else "warning" if fill_rate >= 0.70 else "critical",
        }

    def optimize_floor_price(self, bid_history: List[float],
                               target_fill: float = 0.85) -> dict:
        """Optimal floor price for target fill rate।"""
        if not bid_history:
            return {"optimal_floor": 0.50}

        sorted_bids = sorted(bid_history)
        target_idx  = int(len(sorted_bids) * (1 - target_fill))
        optimal     = sorted_bids[target_idx] if target_idx < len(sorted_bids) else sorted_bids[-1]

        return {
            "optimal_floor":      round(optimal, 4),
            "target_fill_rate":   target_fill,
            "bid_count":          len(bid_history),
            "avg_bid":            round(sum(bid_history) / len(bid_history), 4),
            "p25_bid":            round(sorted_bids[int(len(sorted_bids) * 0.25)], 4),
            "p75_bid":            round(sorted_bids[int(len(sorted_bids) * 0.75)], 4),
        }

    def rebalance_network_mix(self, performance_data: List[Dict]) -> List[Dict]:
        """Network performance based mix rebalancing।"""
        for net in performance_data:
            ecpm      = float(net.get("ecpm", 1.0))
            fill_rate = float(net.get("fill_rate", 0.70))
            net["effective_ecpm"] = round(ecpm * fill_rate, 4)

        total_eff = sum(n["effective_ecpm"] for n in performance_data) or 1
        for net in performance_data:
            net["recommended_share"] = round(net["effective_ecpm"] / total_eff * 100, 2)

        return sorted(performance_data, key=lambda x: x["effective_ecpm"], reverse=True)
