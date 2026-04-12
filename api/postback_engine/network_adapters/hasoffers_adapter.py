"""network_adapters/hasoffers_adapter.py — HasOffers / TUNE platform adapter."""
from .base_adapter import BaseNetworkAdapter

class HasOffersAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "hasoffers"
    FIELD_MAP = {
        "lead_id": "transaction_id", "offer_id": "offer_id", "payout": "payout",
        "currency": "currency", "transaction_id": "conversion_id",
        "user_id": "affiliate_id", "status": "status",
    }
    STATUS_MAP = {"approved": "approved", "pending": "pending", "rejected": "rejected"}
    REQUIRED_FIELDS = ["lead_id", "offer_id"]
    def get_network_key(self): return self.NETWORK_KEY
