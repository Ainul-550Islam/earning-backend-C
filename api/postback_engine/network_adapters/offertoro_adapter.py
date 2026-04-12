"""
network_adapters/offertoro_adapter.py
───────────────────────────────────────
OfferToro Network Adapter.
Postback: ?user_id={user_id}&amount={amount}&oid={oid}&trans_id={trans_id}&type={type}
type: 1=approved, 2=rejected, 3=reversed
"""
from .base_adapter import BaseNetworkAdapter

class OfferToroAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "offertoro"
    FIELD_MAP = {
        "lead_id": "user_id", "offer_id": "oid", "payout": "amount",
        "transaction_id": "trans_id", "currency": "currency",
        "status": "type", "ip_address": "ip",
    }
    STATUS_MAP = {"1": "approved", "2": "rejected", "3": "rejected"}
    REQUIRED_FIELDS = ["lead_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status):
        return self.STATUS_MAP.get(str(raw_status).strip(), "approved") if raw_status else "approved"
