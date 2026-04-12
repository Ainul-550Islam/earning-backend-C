"""
api/ai_engine/PREDICTION_ENGINES/inventory_predictor.py
========================================================
Inventory Predictor — offer/ad inventory ও budget depletion prediction।
কখন restock করতে হবে, কোন offer শেষ হয়ে যাবে predict করো।
Marketing campaign planning ও budget management এর জন্য critical।
"""

import logging
import math
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class InventoryPredictor:
    """
    Offer ও ad budget inventory depletion prediction engine।
    Poisson process + trend-based forecasting।
    """

    def predict_depletion(
        self,
        current_inventory: float,
        daily_burn_rate: float,
        refill_threshold_pct: float = 0.20,
        safety_buffer_days: int = 3,
    ) -> dict:
        """
        কত দিনে inventory শেষ হবে সেটা predict করো।

        Args:
            current_inventory:    current quantity/budget
            daily_burn_rate:      average daily consumption
            refill_threshold_pct: percentage at which to trigger refill alert
            safety_buffer_days:   safety buffer before depletion
        """
        if daily_burn_rate <= 0:
            return {
                "days_remaining":     None,
                "needs_refill":       False,
                "depletion_date":     None,
                "status":             "no_consumption",
                "recommendation":     "No active consumption detected.",
            }

        days_remaining = current_inventory / daily_burn_rate
        refill_trigger_qty = current_inventory * refill_threshold_pct
        days_to_refill_trigger = (current_inventory - refill_trigger_qty) / daily_burn_rate

        # Depletion date
        from django.utils import timezone
        from datetime import timedelta
        depletion_date = timezone.now() + timedelta(days=days_remaining)
        refill_alert_date = timezone.now() + timedelta(days=days_to_refill_trigger)

        # Status classification
        if days_remaining <= safety_buffer_days:
            status = "critical"
            recommendation = f"URGENT: Inventory depletes in {days_remaining:.1f} days. Refill immediately!"
        elif days_remaining <= 7:
            status = "warning"
            recommendation = f"Refill within {int(days_remaining) - safety_buffer_days} days to avoid stockout."
        elif days_remaining <= 14:
            status = "caution"
            recommendation = "Plan refill for next week."
        else:
            status = "healthy"
            recommendation = "Inventory levels healthy. Monitor weekly."

        return {
            "current_inventory":     round(current_inventory, 2),
            "daily_burn_rate":       round(daily_burn_rate, 4),
            "days_remaining":        round(days_remaining, 1),
            "depletion_date":        depletion_date.strftime("%Y-%m-%d %H:%M"),
            "refill_alert_date":     refill_alert_date.strftime("%Y-%m-%d %H:%M"),
            "needs_immediate_refill": days_remaining <= safety_buffer_days,
            "needs_refill_soon":     days_remaining <= 7,
            "refill_trigger_qty":    round(refill_trigger_qty, 2),
            "status":                status,
            "recommendation":        recommendation,
        }

    def predict_offer_inventory(self, offer_id: str, tenant_id=None) -> dict:
        """Specific offer এর inventory prediction।"""
        try:
            from api.ad_networks.models import Offer
            offer = Offer.objects.get(id=offer_id)

            # Available completions left
            max_completions = getattr(offer, "max_completions", None)
            current_completions = getattr(offer, "completion_count", 0)
            available = (max_completions - current_completions) if max_completions else float("inf")

            # Daily completion rate (last 7 days)
            from ..models import PredictionLog
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count

            week_ago = timezone.now() - timedelta(days=7)
            daily_rate = PredictionLog.objects.filter(
                prediction_type="conversion",
                entity_id=str(offer_id),
                created_at__gte=week_ago,
            ).count() / 7.0 or 1.0

            if available == float("inf"):
                return {
                    "offer_id":         str(offer_id),
                    "offer_name":       getattr(offer, "title", "Unknown"),
                    "status":           "unlimited",
                    "recommendation":   "No inventory limit set.",
                }

            return {
                "offer_id":              str(offer_id),
                "offer_name":            getattr(offer, "title", "Unknown"),
                **self.predict_depletion(available, daily_rate),
            }

        except Exception as e:
            logger.error(f"Offer inventory prediction error [{offer_id}]: {e}")
            return {"offer_id": str(offer_id), "error": str(e)}

    def predict_budget_burnout(
        self,
        campaign_budget: float,
        amount_spent: float,
        campaign_start_date,
        campaign_end_date,
        daily_spend_history: List[float] = None,
    ) -> dict:
        """
        Marketing campaign budget burnout prediction।
        Early overspend ও underspend detection।
        """
        from django.utils import timezone
        from datetime import timedelta

        remaining_budget = campaign_budget - amount_spent
        pct_spent        = amount_spent / max(campaign_budget, 0.001)

        # Campaign timing
        now          = timezone.now()
        total_days   = (campaign_end_date - campaign_start_date).days or 1
        elapsed_days = (now - campaign_start_date).days or 1
        remaining_days = (campaign_end_date - now).days

        pct_time_elapsed = elapsed_days / total_days

        # Expected spend vs actual
        expected_spend     = campaign_budget * pct_time_elapsed
        spend_variance_pct = ((amount_spent - expected_spend) / max(expected_spend, 0.001)) * 100

        # Daily burn rate
        daily_rate = amount_spent / max(elapsed_days, 1)
        if daily_spend_history:
            # Use recent trend (last 3 days weighted)
            recent  = daily_spend_history[-3:] if len(daily_spend_history) >= 3 else daily_spend_history
            daily_rate = sum(recent) / len(recent)

        # Projected total spend
        projected_total = amount_spent + (daily_rate * max(remaining_days, 0))
        projected_pct   = projected_total / max(campaign_budget, 0.001)

        # Pacing status
        if spend_variance_pct > 20:
            pacing = "overpacing"
            alert  = f"Budget will be exhausted {remaining_days - int(remaining_budget / daily_rate)} days early!"
        elif spend_variance_pct < -20:
            pacing = "underpacing"
            alert  = "Underspending detected — consider increasing bids or expanding targeting."
        else:
            pacing = "on_track"
            alert  = "Budget pacing is healthy."

        days_until_depletion = int(remaining_budget / max(daily_rate, 0.001))

        return {
            "campaign_budget":      campaign_budget,
            "amount_spent":         round(amount_spent, 2),
            "remaining_budget":     round(remaining_budget, 2),
            "pct_budget_spent":     round(pct_spent * 100, 2),
            "pct_time_elapsed":     round(pct_time_elapsed * 100, 2),
            "spend_variance_pct":   round(spend_variance_pct, 2),
            "daily_burn_rate":      round(daily_rate, 2),
            "projected_total_spend": round(projected_total, 2),
            "projected_pct_of_budget": round(projected_pct * 100, 2),
            "days_until_depletion": days_until_depletion,
            "remaining_campaign_days": remaining_days,
            "pacing_status":        pacing,
            "alert":                alert,
            "recommended_daily_budget": round(remaining_budget / max(remaining_days, 1), 2),
        }

    def multi_offer_inventory_forecast(
        self,
        offers: List[Dict],
        days_ahead: int = 14,
    ) -> List[Dict]:
        """
        Multiple offers এর inventory একসাথে forecast করো।
        Priority queue তৈরি করো — কোনগুলো আগে refill দরকার।
        """
        results = []
        for offer in offers:
            current  = float(offer.get("current_inventory", 1000))
            burn     = float(offer.get("daily_burn_rate", 10))
            forecast = self.predict_depletion(current, burn)
            days_rem = forecast.get("days_remaining", 999)

            results.append({
                **offer,
                "inventory_forecast": forecast,
                "priority_score":     round(1 / max(days_rem, 0.1), 4),
                "in_danger":          days_rem is not None and days_rem <= days_ahead,
            })

        # Sort by priority — most urgent first
        return sorted(results, key=lambda x: x["priority_score"], reverse=True)

    def calculate_safety_stock(
        self,
        avg_daily_demand: float,
        demand_std: float,
        lead_time_days: int = 3,
        service_level: float = 0.95,
    ) -> dict:
        """
        Safety stock calculation (Inventory management formula)।
        Service level → z-score → safety stock।
        """
        z_scores = {0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
        z = z_scores.get(service_level, 1.65)

        safety_stock    = z * demand_std * math.sqrt(lead_time_days)
        reorder_point   = (avg_daily_demand * lead_time_days) + safety_stock
        max_stock       = reorder_point + (avg_daily_demand * 7)  # 7 day replenishment cycle

        return {
            "avg_daily_demand": round(avg_daily_demand, 4),
            "demand_std":       round(demand_std, 4),
            "lead_time_days":   lead_time_days,
            "service_level":    service_level,
            "z_score":          z,
            "safety_stock":     round(safety_stock, 2),
            "reorder_point":    round(reorder_point, 2),
            "max_stock_level":  round(max_stock, 2),
            "recommendation":   f"Reorder when inventory drops below {reorder_point:.0f} units.",
        }
