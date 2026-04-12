"""
api/ai_engine/OPTIMIZATION_ENGINES/bid_optimizer.py
====================================================
Bid Optimizer — RTB (Real-Time Bidding) optimization।
Target CPA/ROAS based bidding, bid landscape analysis।
"""
import logging, math
from typing import List, Dict
logger = logging.getLogger(__name__)

class BidOptimizer:
    """Real-time bidding optimization engine।"""

    def calculate_optimal_bid(self, target_cpa: float, predicted_cvr: float,
                               quality_score: float = 1.0,
                               max_bid: float = None,
                               min_bid: float = 0.01) -> dict:
        if predicted_cvr <= 0:
            return {"bid": min_bid, "reason": "zero_cvr"}
        raw_bid   = target_cpa * predicted_cvr * quality_score
        final_bid = max(min_bid, min(raw_bid, max_bid) if max_bid else raw_bid)
        final_bid = round(final_bid, 4)
        return {
            "bid":            final_bid,
            "target_cpa":     target_cpa,
            "predicted_cvr":  predicted_cvr,
            "quality_score":  quality_score,
            "expected_cpa":   round(final_bid / max(predicted_cvr, 0.001), 2),
            "bid_floor":      min_bid,
        }

    def target_roas_bid(self, target_roas: float, predicted_cvr: float,
                         avg_order_value: float, max_bid: float = None) -> dict:
        if target_roas <= 0 or predicted_cvr <= 0:
            return {"bid": 0.01}
        bid = (avg_order_value * predicted_cvr) / target_roas
        return {
            "bid":           round(min(bid, max_bid) if max_bid else bid, 4),
            "target_roas":   target_roas,
            "predicted_cvr": predicted_cvr,
            "aov":           avg_order_value,
        }

    def bid_landscape_analysis(self, historical_bids: List[Dict]) -> dict:
        if not historical_bids: return {}
        bid_vals    = [float(b.get("bid", 0)) for b in historical_bids]
        win_rates   = [float(b.get("win_rate", 0)) for b in historical_bids]
        avg_bid     = sum(bid_vals) / len(bid_vals)
        avg_wr      = sum(win_rates) / len(win_rates)
        sorted_bids = sorted(bid_vals)
        n = len(sorted_bids)
        return {
            "avg_bid":        round(avg_bid, 4),
            "p25_bid":        round(sorted_bids[int(n*0.25)], 4),
            "p75_bid":        round(sorted_bids[int(n*0.75)], 4),
            "min_bid":        round(min(bid_vals), 4),
            "max_bid":        round(max(bid_vals), 4),
            "avg_win_rate":   round(avg_wr, 4),
            "recommended_bid": round(sorted_bids[int(n*0.60)], 4),
        }

    def dynamic_bid_adjustment(self, base_bid: float, adjustments: Dict[str, float]) -> dict:
        bid = base_bid
        applied = []
        for factor, multiplier in adjustments.items():
            bid    *= multiplier
            applied.append({"factor": factor, "multiplier": multiplier})
        return {
            "original_bid": base_bid,
            "final_bid":    round(bid, 4),
            "adjustments":  applied,
            "total_adjustment_pct": round((bid - base_bid) / max(base_bid, 0.001) * 100, 2),
        }

    def portfolio_bid_optimization(self, campaigns: List[Dict],
                                    total_budget: float) -> List[Dict]:
        if not campaigns or total_budget <= 0: return campaigns
        total_roas = sum(max(float(c.get("roas", 0.1)), 0.01) for c in campaigns)
        for c in campaigns:
            share = max(float(c.get("roas", 0.1)), 0.01) / total_roas
            c["allocated_budget"] = round(total_budget * share, 2)
            c["recommended_bid"]  = round(float(c.get("current_bid", 1.0)) *
                                          (1 + (float(c.get("roas", 1)) - 1) * 0.1), 4)
        return sorted(campaigns, key=lambda x: x.get("allocated_budget", 0), reverse=True)
