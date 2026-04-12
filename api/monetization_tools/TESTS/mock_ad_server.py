"""TESTS/mock_ad_server.py - Mock ad server for testing."""
from decimal import Decimal
import random


class MockAdServer:
    DEFAULT_ECPM = Decimal("2.50")

    @classmethod
    def request_ad(cls, ad_unit_id: int, country: str = "BD",
                    device_type: str = "mobile", user_id: str = "") -> dict:
        return {
            "ad_unit_id": ad_unit_id,
            "ad_markup":  "<div class='mock-ad'>Mock Ad</div>",
            "ecpm":       float(cls.DEFAULT_ECPM),
            "network":    "mock_network",
            "country":    country,
            "device":     device_type,
            "filled":     True,
            "latency_ms": random.randint(50, 200),
        }

    @classmethod
    def simulate_impression(cls, ad_unit_id: int) -> dict:
        return {"event": "impression", "unit": ad_unit_id,
                "revenue": float(cls.DEFAULT_ECPM / 1000)}

    @classmethod
    def simulate_click(cls, ad_unit_id: int) -> dict:
        return {"event": "click", "unit": ad_unit_id, "revenue": 0.005}

    @classmethod
    def simulate_no_fill(cls, ad_unit_id: int) -> dict:
        return {"ad_unit_id": ad_unit_id, "filled": False, "reason": "no_demand"}
