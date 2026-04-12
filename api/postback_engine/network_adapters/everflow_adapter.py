"""network_adapters/everflow_adapter.py — Everflow affiliate platform adapter."""
from .base_adapter import BaseNetworkAdapter

class EverflowAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "everflow"
    FIELD_MAP = {
        "lead_id": "transaction_id", "offer_id": "offer_id", "payout": "payout",
        "currency": "currency", "transaction_id": "conversion_id",
        "status": "status", "goal_id": "goal_id", "goal_value": "goal_value",
    }
    STATUS_MAP = {"approved": "approved", "pending": "pending", "rejected": "rejected", "reversed": "rejected"}
    REQUIRED_FIELDS = ["lead_id"]
    def get_network_key(self): return self.NETWORK_KEY
