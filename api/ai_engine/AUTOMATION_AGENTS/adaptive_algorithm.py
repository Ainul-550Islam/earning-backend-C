"""
api/ai_engine/AUTOMATION_AGENTS/adaptive_algorithm.py
======================================================
Adaptive Algorithm — context ও performance অনুযায়ী strategy পরিবর্তন করো।
Self-adapting system যা নিজে নিজে optimize করে।
A/B test results, user feedback, market conditions এর ভিত্তিতে adapt।
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AdaptiveAlgorithm:
    """
    Self-adapting optimization algorithm।
    Multiple strategies থেকে best-performing টা automatically select করো।
    """

    STRATEGIES = [
        "aggressive_growth",
        "retention_focused",
        "monetization_optimized",
        "engagement_maximized",
        "balanced_growth",
        "cost_efficiency",
    ]

    def __init__(self, strategy: str = "balanced_growth"):
        self.current_strategy = strategy
        self.strategy_scores: Dict[str, float] = {s: 0.5 for s in self.STRATEGIES}
        self.adaptation_history: List[Dict] = []

    def select_strategy(self, context: dict) -> str:
        """Context অনুযায়ী best strategy select করো।"""
        active_users  = context.get("active_users", 0)
        churn_rate    = context.get("churn_rate", 0.10)
        revenue_trend = context.get("revenue_trend", "stable")
        new_user_ratio = context.get("new_user_ratio", 0.30)
        cost_per_user = context.get("cost_per_user", 1.0)
        roi           = context.get("roi", 1.0)

        # Rule-based strategy selection
        if churn_rate > 0.30:
            strategy = "retention_focused"
            reason   = f"High churn rate ({churn_rate:.1%}) — focus on retention"

        elif revenue_trend == "declining" and roi < 0.5:
            strategy = "cost_efficiency"
            reason   = f"Revenue declining, ROI={roi:.2f} — optimize costs"

        elif new_user_ratio > 0.50 and active_users < 1000:
            strategy = "aggressive_growth"
            reason   = f"High new user ratio ({new_user_ratio:.1%}) — accelerate growth"

        elif roi > 2.0 and churn_rate < 0.10:
            strategy = "monetization_optimized"
            reason   = f"Strong ROI ({roi:.2f}) with low churn — maximize revenue"

        elif active_users > 10000 and new_user_ratio < 0.10:
            strategy = "engagement_maximized"
            reason   = "Mature user base — focus on engagement depth"

        else:
            strategy = "balanced_growth"
            reason   = "Balanced conditions — maintain steady growth"

        # Log adaptation
        self.adaptation_history.append({
            "strategy":  strategy,
            "reason":    reason,
            "context":   context,
        })

        self.current_strategy = strategy
        return strategy

    def get_strategy_parameters(self, strategy: str = None) -> dict:
        """Strategy এর specific parameters নিয়ে আসো।"""
        strategy = strategy or self.current_strategy

        params = {
            "aggressive_growth": {
                "ad_spend_multiplier":      1.50,
                "offer_reward_boost":       1.25,
                "notification_frequency":  "high",
                "referral_bonus_multiplier": 2.0,
                "onboarding_incentive":     True,
                "target_cpa_adjustment":    0.80,
            },
            "retention_focused": {
                "ad_spend_multiplier":      0.80,
                "offer_reward_boost":       1.40,
                "notification_frequency":  "medium",
                "winback_campaign":         True,
                "loyalty_bonus":            True,
                "churn_intervention_threshold": 0.50,
            },
            "monetization_optimized": {
                "ad_spend_multiplier":      1.20,
                "offer_reward_boost":       1.10,
                "notification_frequency":  "medium",
                "premium_offer_priority":   True,
                "upsell_aggressive":        True,
                "price_optimization":       True,
            },
            "engagement_maximized": {
                "ad_spend_multiplier":      1.10,
                "offer_reward_boost":       1.15,
                "notification_frequency":  "high",
                "streak_bonus":             True,
                "gamification_boost":       True,
                "daily_challenge":          True,
            },
            "cost_efficiency": {
                "ad_spend_multiplier":      0.60,
                "offer_reward_boost":       0.90,
                "notification_frequency":  "low",
                "focus_organic":            True,
                "cut_low_roi_channels":     True,
                "budget_cap":               True,
            },
            "balanced_growth": {
                "ad_spend_multiplier":      1.00,
                "offer_reward_boost":       1.00,
                "notification_frequency":  "medium",
                "maintain_current":         True,
            },
        }

        return params.get(strategy, params["balanced_growth"])

    def update_strategy_score(self, strategy: str, metric: str,
                               value: float, target: float):
        """Strategy performance score update করো।"""
        score_delta = 0.0
        if target > 0:
            performance = value / target
            if performance >= 1.10:    score_delta = +0.10
            elif performance >= 1.0:   score_delta = +0.05
            elif performance >= 0.90:  score_delta = 0.0
            elif performance >= 0.70:  score_delta = -0.05
            else:                      score_delta = -0.10

        current_score = self.strategy_scores.get(strategy, 0.5)
        new_score = max(0.1, min(1.0, current_score + score_delta))
        self.strategy_scores[strategy] = round(new_score, 4)

        logger.info(f"Strategy score updated: {strategy} [{metric}] {current_score:.3f} → {new_score:.3f}")

    def auto_adapt(self, performance_data: dict, context: dict) -> dict:
        """Fully autonomous strategy adaptation।"""
        # Select best strategy
        new_strategy = self.select_strategy(context)

        # Check if strategy change is warranted
        if new_strategy == self.current_strategy:
            return {
                "adapted":          False,
                "current_strategy": self.current_strategy,
                "reason":           "No adaptation needed",
            }

        old_strategy = self.current_strategy
        self.current_strategy = new_strategy
        params = self.get_strategy_parameters(new_strategy)

        return {
            "adapted":        True,
            "old_strategy":   old_strategy,
            "new_strategy":   new_strategy,
            "parameters":     params,
            "reason":         self.adaptation_history[-1].get("reason", ""),
            "impact":         f"Switching from {old_strategy} to {new_strategy}",
        }

    def simulate_strategy(self, strategy: str, base_metrics: dict,
                            days: int = 30) -> dict:
        """Strategy change হলে কী ফলাফল হবে সেটা simulate করো।"""
        params    = self.get_strategy_parameters(strategy)
        ad_mult   = params.get("ad_spend_multiplier", 1.0)
        rew_mult  = params.get("offer_reward_boost", 1.0)

        base_revenue   = base_metrics.get("daily_revenue", 1000)
        base_users     = base_metrics.get("active_users", 500)
        base_retention = base_metrics.get("retention_rate", 0.70)

        # Simplified simulation model
        if "growth" in strategy:
            projected_users   = round(base_users * (1 + 0.05 * days / 30), 0)
            projected_revenue = round(base_revenue * 1.15, 2)
        elif "retention" in strategy:
            projected_users   = round(base_users * (1 + 0.01 * days / 30), 0)
            projected_revenue = round(base_revenue * 1.08, 2)
            base_retention    = min(1.0, base_retention + 0.05)
        elif "monetization" in strategy:
            projected_users   = round(base_users * 0.98, 0)
            projected_revenue = round(base_revenue * 1.25, 2)
        else:
            projected_users   = round(base_users * (1 + 0.02 * days / 30), 0)
            projected_revenue = round(base_revenue * 1.05, 2)

        roi = projected_revenue / max(base_revenue * ad_mult, 1)

        return {
            "strategy":            strategy,
            "simulation_days":     days,
            "projected_users":     int(projected_users),
            "projected_revenue":   projected_revenue,
            "projected_retention": round(base_retention, 4),
            "projected_roi":       round(roi, 4),
            "confidence":          0.65,
            "note":                "Simulation based on historical patterns. Actual results may vary.",
        }
