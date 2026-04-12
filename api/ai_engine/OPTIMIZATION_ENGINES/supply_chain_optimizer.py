"""
api/ai_engine/OPTIMIZATION_ENGINES/supply_chain_optimizer.py
=============================================================
Supply Chain Optimizer — digital offer supply chain optimization।
Ad network → Publisher → User এর মধ্যে offer flow optimize করো।
Inventory, fill rate, revenue share optimize করো।
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class SupplyChainOptimizer:
    """
    Digital ad/offer supply chain optimization।
    Multi-network inventory management।
    """

    def optimize_network_mix(self, networks: List[Dict],
                              total_traffic: int = 10000) -> List[Dict]:
        """
        Multiple ad networks এর মধ্যে traffic optimally distribute করো।
        networks: [{'name': 'AdMob', 'ecpm': 2.5, 'fill_rate': 0.85, 'priority': 1}]
        """
        if not networks:
            return []

        # Score each network by revenue potential
        for n in networks:
            ecpm      = float(n.get('ecpm', 1.0))
            fill_rate = float(n.get('fill_rate', 0.70))
            n['revenue_score'] = round(ecpm * fill_rate, 4)

        total_score = sum(n['revenue_score'] for n in networks) or 1
        result = []
        remaining_traffic = total_traffic

        sorted_networks = sorted(networks, key=lambda x: x['revenue_score'], reverse=True)

        for i, network in enumerate(sorted_networks):
            share = network['revenue_score'] / total_score
            allocated = round(total_traffic * share)
            if i == len(sorted_networks) - 1:
                allocated = remaining_traffic  # Give remainder to last

            expected_fills   = round(allocated * network.get('fill_rate', 0.70))
            expected_revenue = round(expected_fills * network.get('ecpm', 1.0) / 1000, 2)

            result.append({
                **network,
                'traffic_allocated': allocated,
                'expected_fills':    expected_fills,
                'expected_revenue':  expected_revenue,
                'traffic_share_pct': round(share * 100, 2),
            })
            remaining_traffic -= allocated

        return result

    def waterfall_optimization(self, networks: List[Dict]) -> List[Dict]:
        """
        Waterfall (sequential) network priority setup।
        Highest eCPM → lowest fallback।
        """
        sorted_net = sorted(networks, key=lambda x: float(x.get('ecpm', 0)), reverse=True)
        return [
            {**n, 'waterfall_position': i + 1,
             'is_primary': i == 0, 'is_fallback': i == len(sorted_net) - 1}
            for i, n in enumerate(sorted_net)
        ]

    def header_bidding_simulation(self, bids: List[Dict],
                                   floor_price: float = 0.50) -> dict:
        """
        Header bidding auction simulation।
        Highest bid wins, above floor price।
        """
        valid_bids = [b for b in bids if float(b.get('bid', 0)) >= floor_price]
        if not valid_bids:
            return {'winner': None, 'winning_bid': 0.0, 'reason': 'No bids above floor'}

        winner = max(valid_bids, key=lambda x: float(x.get('bid', 0)))
        # Second-price auction
        sorted_bids = sorted(valid_bids, key=lambda x: float(x.get('bid', 0)), reverse=True)
        clearing_price = float(sorted_bids[1].get('bid', floor_price)) if len(sorted_bids) > 1 else floor_price

        return {
            'winner':          winner.get('network', 'unknown'),
            'winning_bid':     float(winner.get('bid', 0)),
            'clearing_price':  round(clearing_price, 4),
            'total_bids':      len(bids),
            'valid_bids':      len(valid_bids),
            'floor_price':     floor_price,
            'revenue':         round(clearing_price, 4),
        }

    def optimize_fill_rate(self, current_fill: float, target_fill: float = 0.90) -> dict:
        """Fill rate improve করার recommendations।"""
        gap = target_fill - current_fill
        actions = []

        if gap > 0.20:
            actions.append({'action': 'add_backup_networks', 'priority': 'urgent'})
            actions.append({'action': 'lower_floor_price', 'priority': 'high'})
        elif gap > 0.10:
            actions.append({'action': 'optimize_ad_formats', 'priority': 'medium'})
            actions.append({'action': 'increase_request_timeout', 'priority': 'medium'})
        elif gap > 0:
            actions.append({'action': 'fine_tune_targeting', 'priority': 'low'})

        return {
            'current_fill':   current_fill,
            'target_fill':    target_fill,
            'gap':            round(gap, 4),
            'actions':        actions,
            'estimated_lift': f"{gap * 100:.1f}% fill rate improvement possible",
        }

    def inventory_forecast(self, historical_requests: List[float],
                            days_ahead: int = 7) -> dict:
        """Future ad inventory forecast।"""
        if not historical_requests:
            return {'forecast': [], 'method': 'no_data'}

        avg   = sum(historical_requests) / len(historical_requests)
        trend = (historical_requests[-1] - historical_requests[0]) / max(len(historical_requests), 1)
        forecast = [round(max(0, avg + trend * (i + 1)), 0) for i in range(days_ahead)]

        return {
            'forecast':         forecast,
            'avg_daily_req':    round(avg, 0),
            'trend':            'growing' if trend > 0 else 'declining' if trend < 0 else 'stable',
            'days_ahead':       days_ahead,
        }
