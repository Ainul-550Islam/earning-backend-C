"""
api/ai_engine/OPTIMIZATION_ENGINES/ad_optimizer.py
====================================================
Ad Optimizer — ad campaign performance optimization।
CTR, CVR, ROAS maximize। Budget allocation, targeting, creative।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class AdOptimizer:
    """Comprehensive ad campaign optimization engine।"""

    def optimize_campaign(self, campaign_data: dict) -> dict:
        ctr    = float(campaign_data.get("ctr", 0.05))
        cvr    = float(campaign_data.get("cvr", 0.10))
        cpc    = float(campaign_data.get("cpc", 1.0))
        budget = float(campaign_data.get("budget", 1000))
        roas   = float(campaign_data.get("roas", 0))

        recommendations = []
        score = 0.0

        if ctr < 0.02:
            recommendations.append({"action": "refresh_creatives", "priority": "urgent",
                "reason": f"CTR {ctr:.1%} too low", "expected_lift": "50-150% CTR"})
            score -= 0.3
        if cvr < 0.05:
            recommendations.append({"action": "optimize_landing_page", "priority": "high",
                "reason": f"CVR {cvr:.1%} below benchmark", "expected_lift": "20-50% CVR"})
            score -= 0.2
        if roas < 1.0 and roas > 0:
            recommendations.append({"action": "pause_campaign", "priority": "critical",
                "reason": f"Negative ROAS: {roas:.2f}", "expected_action": "Stop bleeding"})
            score -= 0.5
        elif roas > 3.0:
            recommendations.append({"action": "scale_budget", "priority": "opportunity",
                "reason": f"Strong ROAS: {roas:.2f}", "expected_lift": "2-3x volume"})
            score += 0.3

        health = "excellent" if score >= 0 else "warning" if score >= -0.3 else "critical"
        return {
            "campaign_health":   health,
            "health_score":      round(max(0, 1.0 + score), 4),
            "current_metrics":   {"ctr": ctr, "cvr": cvr, "cpc": cpc, "roas": roas},
            "recommendations":   recommendations,
            "estimated_monthly_savings": round(budget * max(0, -score) * 0.2, 2),
        }

    def optimize_targeting(self, audience_data: dict) -> dict:
        segments = audience_data.get("segments", [])
        best_segments = sorted(segments, key=lambda x: float(x.get("roas", 0)), reverse=True)
        return {
            "top_segments":       best_segments[:3],
            "exclude_segments":   [s for s in segments if float(s.get("roas", 1)) < 0.5],
            "lookalike_source":   best_segments[0] if best_segments else None,
            "budget_allocation":  self._allocate_budget_by_roas(segments),
        }

    def _allocate_budget_by_roas(self, segments: List[Dict]) -> List[Dict]:
        total_roas = sum(max(float(s.get("roas", 0)), 0.1) for s in segments) or 1
        return [{
            "segment":      s.get("name"),
            "budget_share": round(max(float(s.get("roas", 0)), 0.1) / total_roas, 4),
        } for s in segments]

    def creative_ab_test_winner(self, variants: List[Dict]) -> dict:
        if not variants: return {"winner": None}
        winner = max(variants, key=lambda v: float(v.get("ctr", 0)) * float(v.get("cvr", 0)))
        return {
            "winner":          winner,
            "winning_metric":  "ctr_x_cvr",
            "winning_score":   round(float(winner.get("ctr", 0)) * float(winner.get("cvr", 0)), 6),
            "recommendation":  f"Deploy variant {winner.get('name', 'winner')} to 100%",
        }

    def frequency_capping(self, user_impressions: int, daily_cap: int = 5) -> dict:
        exceeded = user_impressions >= daily_cap
        return {
            "impressions":   user_impressions,
            "daily_cap":     daily_cap,
            "cap_reached":   exceeded,
            "remaining":     max(0, daily_cap - user_impressions),
            "action":        "stop_showing" if exceeded else "continue",
        }
