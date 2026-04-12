"""network_adapters/cake_adapter.py — CAKE affiliate platform adapter."""
from .base_adapter import BaseNetworkAdapter

class CakeAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "cake"
    FIELD_MAP = {
        "lead_id": "click_id", "offer_id": "offer_id", "payout": "payout",
        "currency": "currency", "transaction_id": "conversion_id", "status": "status",
    }
    STATUS_MAP = {"approved": "approved", "rejected": "rejected", "cancelled": "rejected"}
    REQUIRED_FIELDS = ["lead_id", "offer_id"]
    def get_network_key(self): return self.NETWORK_KEY
