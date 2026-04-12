"""OPTIMIZATION_ENGINES/header_bidding.py — Header bidding orchestration."""
from decimal import Decimal
from typing import List, Optional


class HeaderBiddingEngine:
    """Orchestrates parallel bids from multiple demand partners."""

    def __init__(self, timeout_ms: int = 500):
        self.timeout_ms = timeout_ms

    def collect_bids(self, ad_unit_id: int, floor: Decimal = Decimal("0")) -> List[dict]:
        from ..models import WaterfallConfig
        bidders = list(
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id, is_active=True, is_header_bidding=True
            ).select_related("ad_network").order_by("priority")
        )
        bids = []
        for b in bidders:
            cpm = b.bid_floor or b.floor_ecpm or Decimal("0")
            if cpm >= floor:
                bids.append({"network": b.ad_network.display_name,
                              "cpm": cpm, "waterfall_id": b.id})
        return bids

    def auction(self, bids: List[dict], floor: Decimal = Decimal("0")) -> Optional[dict]:
        valid = [b for b in bids if Decimal(str(b.get("cpm", 0))) >= floor]
        return max(valid, key=lambda b: float(b["cpm"])) if valid else None

    def second_price(self, bids: List[dict], floor: Decimal) -> Optional[dict]:
        sorted_bids = sorted(bids, key=lambda b: float(b.get("cpm", 0)), reverse=True)
        if not sorted_bids or Decimal(str(sorted_bids[0]["cpm"])) < floor:
            return None
        win_price = Decimal(str(sorted_bids[1]["cpm"])) + Decimal("0.01") if len(sorted_bids) > 1 else floor
        result    = dict(sorted_bids[0])
        result["winning_price"] = win_price
        return result
