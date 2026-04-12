"""
api/ai_engine/OPTIMIZATION_ENGINES/budget_optimizer.py
=======================================================
Budget Optimizer — ad campaign budget allocation।
Multi-channel, multi-campaign budget distribution।
ROI maximization under budget constraints।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class BudgetOptimizer:
    """Budget allocation optimization engine।"""

    def optimize(self, channels: List[Dict], total_budget: float,
                 objective: str = "roas") -> List[Dict]:
        if not channels or total_budget <= 0: return channels

        # Score channels by objective
        for ch in channels:
            if objective == "roas":
                ch["_score"] = float(ch.get("roas", 0))
            elif objective == "conversions":
                ch["_score"] = float(ch.get("conversions", 0))
            elif objective == "cpa":
                ch["_score"] = 1.0 / max(float(ch.get("cpa", 1)), 0.001)
            else:
                ch["_score"] = float(ch.get("revenue", 0))

        total_score = sum(max(ch["_score"], 0.001) for ch in channels)
        allocated_sum = 0.0
        result = []
        for i, ch in enumerate(sorted(channels, key=lambda x: x["_score"], reverse=True)):
            share     = ch["_score"] / total_score
            allocated = round(total_budget * share, 2)
            if i == len(channels) - 1:
                allocated = round(total_budget - allocated_sum, 2)
            min_budget = float(ch.get("min_budget", 0))
            allocated  = max(allocated, min_budget)
            allocated_sum += allocated
            result.append({
                **{k: v for k, v in ch.items() if not k.startswith("_")},
                "allocated_budget": allocated,
                "budget_share_pct": round(share * 100, 2),
                "expected_roas":    ch.get("roas", 0),
            })
        return result

    def daily_budget_pacing(self, monthly_budget: float,
                             days_remaining: int,
                             spend_to_date: float) -> dict:
        remaining_budget = monthly_budget - spend_to_date
        daily_budget     = remaining_budget / max(days_remaining, 1)
        pacing_rate      = spend_to_date / monthly_budget if monthly_budget > 0 else 0
        ideal_pacing     = 1.0 - (days_remaining / 30.0)
        status = "on_pace" if abs(pacing_rate - ideal_pacing) < 0.05 else                  "overspending" if pacing_rate > ideal_pacing else "underspending"
        return {
            "recommended_daily": round(daily_budget, 2),
            "remaining_budget":  round(remaining_budget, 2),
            "pacing_rate":       round(pacing_rate, 4),
            "status":            status,
            "days_remaining":    days_remaining,
            "adjustment_needed": status != "on_pace",
        }

    def roi_maximization(self, opportunities: List[Dict],
                          budget: float) -> dict:
        """Knapsack-style ROI maximization।"""
        sorted_opps = sorted(opportunities, key=lambda x: float(x.get("roi", 0)), reverse=True)
        selected = []
        remaining = budget
        for opp in sorted_opps:
            cost = float(opp.get("cost", 0))
            roi  = float(opp.get("roi", 0))
            if cost <= remaining and roi > 0:
                selected.append(opp)
                remaining -= cost
        total_revenue = sum(float(o.get("cost", 0)) * float(o.get("roi", 0)) for o in selected)
        total_cost    = sum(float(o.get("cost", 0)) for o in selected)
        return {
            "selected":         selected,
            "total_cost":       round(total_cost, 2),
            "total_revenue":    round(total_revenue, 2),
            "overall_roi":      round((total_revenue - total_cost) / max(total_cost, 0.001), 4),
            "remaining_budget": round(remaining, 2),
        }
