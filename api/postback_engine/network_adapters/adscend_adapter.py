"""
network_adapters/adscend_adapter.py
─────────────────────────────────────
Adscend Media Adapter.
Postback: ?uid={uid}&amount={amount}&campaign_id={campaign_id}&tid={tid}
"""
from .base_adapter import BaseNetworkAdapter

class AdscendAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "adscend"
    FIELD_MAP = {
        "lead_id": "uid", "offer_id": "campaign_id", "payout": "amount",
        "transaction_id": "tid", "status": "status", "currency": "currency",
    }
    STATUS_MAP = {"approved": "approved", "chargeback": "rejected", "reversed": "rejected"}
    REQUIRED_FIELDS = ["lead_id", "payout"]
    def get_network_key(self): return self.NETWORK_KEY
