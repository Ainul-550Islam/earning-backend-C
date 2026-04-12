"""AD_NETWORKS/bidding_manager.py — Header bidding / RTB auction engine."""
from decimal import Decimal
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class BiddingManager:
    """Runs header bidding auctions for premium ad inventory."""

    def __init__(self, timeout_ms: int = 500):
        self.timeout_ms = timeout_ms

    def run_auction(self, ad_unit_id: int,
                     floor_ecpm: Decimal = Decimal("0"),
                     context: dict = None) -> Optional[dict]:
        """
        Collect bids from all header-bidding partners and return the winner.
        In production this is async; here we return the highest mock bid.
        """
        from ..models import WaterfallConfig
        bidders = list(
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id, is_active=True, is_header_bidding=True
            ).select_related("ad_network").order_by("priority")
        )
        if not bidders:
            return None
        bids = []
        for b in bidders:
            bid_cpm = b.bid_floor or b.floor_ecpm or Decimal("0")
            if bid_cpm >= floor_ecpm:
                bids.append({
                    "network":   b.ad_network.display_name,
                    "cpm":       float(bid_cpm),
                    "timeout":   b.timeout_ms,
                    "waterfall": b,
                })
        if not bids:
            return None
        winner = max(bids, key=lambda x: x["cpm"])
        logger.info("Auction winner: %s at CPM=%.4f", winner["network"], winner["cpm"])
        return winner

    @staticmethod
    def second_price(bids: List[dict], floor: Decimal) -> Optional[dict]:
        """Second-price auction — winner pays second highest + $0.01."""
        sorted_bids = sorted(bids, key=lambda x: x.get("cpm", 0), reverse=True)
        if not sorted_bids:
            return None
        if Decimal(str(sorted_bids[0]["cpm"])) < floor:
            return None
        win_price = (
            Decimal(str(sorted_bids[1]["cpm"])) + Decimal("0.01")
            if len(sorted_bids) > 1
            else floor
        )
        result = dict(sorted_bids[0])
        result["winning_price"] = win_price
        return result
