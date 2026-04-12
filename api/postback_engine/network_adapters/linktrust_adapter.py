"""
network_adapters/linktrust_adapter.py
───────────────────────────────────────
LinkTrust affiliate tracking platform.
Postback: ?sub1={sub1}&amount={amount}&offer_id={offer_id}&trans_id={trans_id}
"""
from .base_adapter import BaseNetworkAdapter

class LinkTrustAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "linktrust"
    FIELD_MAP = {
        "lead_id": "sub1", "offer_id": "offer_id", "payout": "amount",
        "transaction_id": "trans_id", "currency": "currency", "status": "status",
        "sub_id": "sub2", "user_id": "sub3",
    }
    STATUS_MAP = {"approved": "approved", "pending": "pending", "declined": "rejected"}
    REQUIRED_FIELDS = ["lead_id"]
    def get_network_key(self): return self.NETWORK_KEY
