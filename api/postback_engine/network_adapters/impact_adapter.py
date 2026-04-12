"""
network_adapters/impact_adapter.py
────────────────────────────────────
Impact (impact.com) affiliate platform. Uses PascalCase param names.
"""
from .base_adapter import BaseNetworkAdapter

class ImpactAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "impact"
    FIELD_MAP = {
        "lead_id": "ClickId", "offer_id": "CampaignId", "payout": "Payout",
        "currency": "Currency", "transaction_id": "OrderId",
        "user_id": "CustomerId", "status": "ActionStatus",
    }
    STATUS_MAP = {
        "approved": "approved", "pending": "pending",
        "rejected": "rejected", "reversed": "rejected", "withdrawn": "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "offer_id"]
    def get_network_key(self): return self.NETWORK_KEY
