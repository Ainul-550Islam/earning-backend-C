"""TESTS/test_optimization.py - Optimization engine tests."""
from decimal import Decimal
from ..OPTIMIZATION_ENGINES.ad_auction_engine import AdAuctionEngine
from ..OPTIMIZATION_ENGINES.geo_optimizer import GeoOptimizer
from ..OPTIMIZATION_ENGINES.time_optimizer import TimeOptimizer
from ..OPTIMIZATION_ENGINES.device_optimizer import DeviceOptimizer


class TestAdAuctionEngine:
    def test_first_price(self):
        bids   = [{"cpm": 3.0}, {"cpm": 2.0}]
        winner = AdAuctionEngine.first_price(bids, Decimal("1.0"))
        assert winner["cpm"] == 3.0

    def test_below_floor(self):
        assert AdAuctionEngine.first_price([{"cpm": 0.5}], Decimal("1.0")) is None


class TestGeoOptimizer:
    def test_us_tier_1(self):       assert GeoOptimizer.tier("US") == 1
    def test_bd_tier_3(self):       assert GeoOptimizer.tier("BD") == 3
    def test_us_multiplier(self):   assert GeoOptimizer.ecpm_multiplier("US") == Decimal("3.0")
    def test_adjust_bid(self):
        adjusted = GeoOptimizer.adjust_bid(Decimal("1.0"), "US")
        assert adjusted == Decimal("3.0000")


class TestTimeOptimizer:
    def test_peak_hours_not_empty(self):
        assert len(TimeOptimizer.peak_hours()) > 0

    def test_multiplier_range(self):
        for h in range(24):
            m = TimeOptimizer.multiplier(h)
            assert Decimal("0.3") <= m <= Decimal("2.0")


class TestDeviceOptimizer:
    def test_mobile_format(self): assert DeviceOptimizer.best_format("mobile") == "rewarded_video"
    def test_desktop_format(self): assert DeviceOptimizer.best_format("desktop") == "native"
    def test_bid_adjust(self):
        assert DeviceOptimizer.adjust_bid(Decimal("1.0"), "desktop") == Decimal("1.5000")
