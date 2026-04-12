"""
network_adapters/google_adapter.py
────────────────────────────────────
Google IMA SDK / Ad Manager rewarded callback.
"""
from .base_adapter import BaseNetworkAdapter

class GoogleAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "google"
    FIELD_MAP = {
        "lead_id": "user_id", "offer_id": "ad_break_id", "payout": "reward_amount",
        "currency": "reward_type", "transaction_id": "transaction_id",
    }
    REQUIRED_FIELDS = ["transaction_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
