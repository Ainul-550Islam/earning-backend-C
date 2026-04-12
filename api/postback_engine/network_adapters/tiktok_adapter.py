"""
network_adapters/tiktok_adapter.py
────────────────────────────────────
TikTok for Business conversion postback.
"""
from .base_adapter import BaseNetworkAdapter

class TikTokAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "tiktok"
    FIELD_MAP = {
        "lead_id": "click_id", "offer_id": "campaign_id", "payout": "value",
        "currency": "currency", "transaction_id": "event_id",
    }
    STATUS_MAP = {"complete": "approved", "failed": "rejected"}
    REQUIRED_FIELDS = ["lead_id"]
    def get_network_key(self): return self.NETWORK_KEY
