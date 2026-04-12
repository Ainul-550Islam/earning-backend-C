"""
api/ai_engine/AUTOMATION_AGENTS/bidding_agent.py
================================================
Bidding Agent — automated ad/offer bidding optimization।
CPC, CPA, CPM bid calculation এবং real-time adjustment।
ROI-maximizing bidding strategy।
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class BiddingAgent:
    """
    Smart automated bidding agent।
    Target CPA/ROI অনুযায়ী optimal bids calculate করো।
    """

    def calculate_bid(self, target_cpa: float, predicted_cvr: float,
                       max_bid: float = None, strategy: str = 'target_cpa') -> dict:
        """
        Optimal bid calculate করো।
        Strategies: target_cpa, target_roas, enhanced_cpc, maximize_conversions
        """
        if predicted_cvr <= 0:
            return {'bid': 0.01, 'reason': 'zero_conversion_rate', 'strategy': strategy}

        strategies = {
            'target_cpa':             self._target_cpa_bid,
            'target_roas':            self._target_roas_bid,
            'enhanced_cpc':           self._enhanced_cpc_bid,
            'maximize_conversions':   self._maximize_conv_bid,
        }
        bid_fn = strategies.get(strategy, self._target_cpa_bid)
        bid    = bid_fn(target_cpa, predicted_cvr)

        # Apply max bid cap
        if max_bid:
            bid = min(bid, max_bid)
        bid = max(0.01, round(bid, 4))

        return {
            'bid':            bid,
            'target_cpa':     target_cpa,
            'predicted_cvr':  predicted_cvr,
            'strategy':       strategy,
            'expected_cpa':   round(bid / max(predicted_cvr, 0.001), 2),
            'confidence':     0.80,
        }

    def _target_cpa_bid(self, target_cpa: float, cvr: float) -> float:
        """Target CPA = Bid / CVR → Bid = Target_CPA * CVR"""
        return target_cpa * cvr

    def _target_roas_bid(self, target_roas: float, cvr: float,
                          avg_order_value: float = 500) -> float:
        """Target ROAS bid calculation।"""
        return (avg_order_value / target_roas) * cvr

    def _enhanced_cpc_bid(self, base_cpc: float, cvr: float) -> float:
        """Enhanced CPC — adjust base CPC by predicted CVR।"""
        avg_cvr = 0.10
        adjustment = cvr / avg_cvr
        return base_cpc * min(2.0, max(0.5, adjustment))

    def _maximize_conv_bid(self, budget: float, cvr: float) -> float:
        """Maximize conversions within budget।"""
        return budget * 0.10 * cvr

    def adjust_bid_real_time(self, current_bid: float,
                               performance_data: dict) -> dict:
        """Real-time bid adjustment based on performance।"""
        ctr      = performance_data.get('ctr', 0.05)
        cvr      = performance_data.get('cvr', 0.10)
        actual_cpa = performance_data.get('actual_cpa', 0)
        target_cpa = performance_data.get('target_cpa', 100)
        budget_used = performance_data.get('budget_pct_used', 0.50)

        # Calculate bid adjustment factor
        adjustment = 1.0

        if actual_cpa > 0 and target_cpa > 0:
            cpa_ratio  = actual_cpa / target_cpa
            if cpa_ratio > 1.20:     adjustment *= 0.85   # CPA too high → lower bid
            elif cpa_ratio < 0.80:   adjustment *= 1.15   # CPA good → raise bid
            elif cpa_ratio < 0.50:   adjustment *= 1.30   # Great CPA → raise more

        if budget_used > 0.90:       adjustment *= 0.80   # Budget running out
        if ctr < 0.01:               adjustment *= 0.90   # Low CTR → likely irrelevant

        new_bid = round(current_bid * adjustment, 4)
        new_bid = max(0.01, new_bid)

        return {
            'current_bid':   current_bid,
            'new_bid':       new_bid,
            'adjustment':    round(adjustment, 4),
            'direction':     'increased' if new_bid > current_bid else 'decreased' if new_bid < current_bid else 'unchanged',
            'reason':        self._bid_reason(adjustment, cpa_ratio=actual_cpa/max(target_cpa,1) if actual_cpa else 1),
        }

    def _bid_reason(self, adj: float, cpa_ratio: float = 1.0) -> str:
        if adj > 1.10:   return f'Good performance — CPA ratio {cpa_ratio:.2f} below target'
        if adj < 0.90:   return f'Poor performance — CPA ratio {cpa_ratio:.2f} above target'
        return 'Performance on target — minor adjustment'

    def portfolio_bidding(self, campaigns: List[Dict],
                           total_budget: float) -> List[Dict]:
        """
        Multiple campaigns এর bidding portfolio optimize করো।
        Budget allocation + bid levels simultaneously।
        """
        if not campaigns or total_budget <= 0:
            return campaigns

        # Score each campaign by efficiency
        for c in campaigns:
            roi         = c.get('roi', 1.0)
            cvr         = c.get('cvr', 0.05)
            volume      = c.get('conversion_volume', 0)
            c['efficiency'] = roi * cvr * math.log1p(volume)

        total_eff = sum(c['efficiency'] for c in campaigns) or 1
        result    = []
        for camp in sorted(campaigns, key=lambda x: x['efficiency'], reverse=True):
            budget_share = camp['efficiency'] / total_eff
            allocated    = round(total_budget * budget_share, 2)
            new_bid      = self.calculate_bid(
                camp.get('target_cpa', 100),
                camp.get('cvr', 0.05),
                max_bid=allocated * 0.01,
            )
            result.append({
                **camp,
                'allocated_budget': allocated,
                'recommended_bid':  new_bid['bid'],
                'budget_share_pct': round(budget_share * 100, 2),
            })
        return result

    def detect_bid_manipulation(self, auction_data: dict) -> dict:
        """Bid manipulation / click fraud patterns detect করো।"""
        your_bid      = auction_data.get('your_bid', 0)
        winning_bid   = auction_data.get('winning_bid', 0)
        your_bid_count = auction_data.get('your_bid_count', 0)
        win_rate      = auction_data.get('win_rate', 0)
        anomaly_bids  = auction_data.get('anomalous_bids', 0)

        flags = []
        if winning_bid > your_bid * 5:
            flags.append('suspiciously_high_winning_bid')
        if win_rate < 0.01 and your_bid_count > 1000:
            flags.append('consistently_outbid — possible bid inflation')
        if anomaly_bids > your_bid_count * 0.20:
            flags.append('high_anomalous_bid_rate')

        return {
            'manipulation_suspected': len(flags) > 0,
            'flags':                  flags,
            'recommendation':         'Report to platform support' if flags else 'Normal auction activity',
        }
