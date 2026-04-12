"""TESTS/test_ad_networks.py - Ad network integration tests."""
from decimal import Decimal
from ..AD_NETWORKS.bidding_manager import BiddingManager


class TestBiddingManager:
    def test_second_price_returns_winner(self):
        bids = [
            {"network": "A", "cpm": 3.0},
            {"network": "B", "cpm": 2.5},
            {"network": "C", "cpm": 1.5},
        ]
        result = BiddingManager.second_price(bids, Decimal("1.0"))
        assert result is not None
        assert result["network"] == "A"
        assert result["winning_price"] == Decimal("2.51")

    def test_second_price_below_floor_returns_none(self):
        bids = [{"network": "A", "cpm": 0.5}]
        result = BiddingManager.second_price(bids, Decimal("1.0"))
        assert result is None

    def test_first_price_auction(self):
        from ..OPTIMIZATION_ENGINES.ad_auction_engine import AdAuctionEngine
        bids   = [{"cpm": 3.0, "n": "A"}, {"cpm": 2.0, "n": "B"}]
        winner = AdAuctionEngine.first_price(bids, Decimal("1.0"))
        assert winner["cpm"] == 3.0
