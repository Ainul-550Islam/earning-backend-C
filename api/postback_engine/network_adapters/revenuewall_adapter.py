"""network_adapters/revenuewall_adapter.py — Revenue Wall Adapter."""
from .base_adapter import BaseNetworkAdapter

class RevenueWallAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "revenuewall"
    FIELD_MAP = {
        "lead_id": "user_id", "offer_id": "offer_id", "payout": "payout",
        "transaction_id": "transaction_id", "status": "status", "currency": "currency",
    }
    REQUIRED_FIELDS = ["lead_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved" if not raw_status else super().normalise_status(raw_status)
