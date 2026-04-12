"""OPTIMIZATION_ENGINES/ad_auction_engine.py — RTB auction engine."""
from decimal import Decimal
from typing import List, Optional


class AdAuctionEngine:
    """First/second-price auction for real-time bidding."""

    @staticmethod
    def first_price(bids: List[dict], floor: Decimal) -> Optional[dict]:
        valid = [b for b in bids if Decimal(str(b.get("cpm", 0))) >= floor]
        if not valid:
            return None
        winner = max(valid, key=lambda b: float(b["cpm"]))
        return dict(winner)

    @staticmethod
    def second_price(bids: List[dict], floor: Decimal) -> Optional[dict]:
        valid  = sorted([b for b in bids if Decimal(str(b.get("cpm", 0))) >= floor],
                        key=lambda b: float(b["cpm"]), reverse=True)
        if not valid:
            return None
        result = dict(valid[0])
        result["clearing_price"] = Decimal(str(valid[1]["cpm"])) + Decimal("0.01") if len(valid) > 1 else floor
        return result

    @staticmethod
    def vickrey(bids: List[dict], floor: Decimal) -> Optional[dict]:
        """Alias for second-price auction (Vickrey auction)."""
        return AdAuctionEngine.second_price(bids, floor)

    @staticmethod
    def validate_bid(bid: dict, floor: Decimal) -> bool:
        try:
            return Decimal(str(bid.get("cpm", 0))) >= floor
        except Exception:
            return False
