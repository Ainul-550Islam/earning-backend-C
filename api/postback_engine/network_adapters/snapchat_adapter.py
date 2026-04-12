"""
network_adapters/snapchat_adapter.py
──────────────────────────────────────
Snapchat Ads conversion postback.
"""
from .base_adapter import BaseNetworkAdapter

class SnapchatAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "snapchat"
    FIELD_MAP = {
        "lead_id": "click_id", "offer_id": "campaign_id", "payout": "conversion_value",
        "currency": "currency", "transaction_id": "event_conversion_id",
    }
    REQUIRED_FIELDS = ["lead_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
