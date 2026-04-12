"""
network_adapters/twitter_adapter.py
──────────────────────────────────────
Twitter/X Ads conversion postback.
"""
from .base_adapter import BaseNetworkAdapter

class TwitterAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "twitter"
    FIELD_MAP = {
        "lead_id": "click_id", "offer_id": "line_item_id", "payout": "conversion_value",
        "currency": "currency", "transaction_id": "event_id",
    }
    REQUIRED_FIELDS = ["lead_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
