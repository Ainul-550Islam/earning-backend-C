"""
network_adapters/facebook_adapter.py
──────────────────────────────────────
Facebook Audience Network rewarded ad callback.
"""
from .base_adapter import BaseNetworkAdapter

class FacebookAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "facebook"
    FIELD_MAP = {
        "lead_id": "user_id", "offer_id": "placement_id", "payout": "reward_amount",
        "currency": "currency", "transaction_id": "transaction_id",
    }
    REQUIRED_FIELDS = ["transaction_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
