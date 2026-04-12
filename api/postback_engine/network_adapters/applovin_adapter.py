"""
network_adapters/applovin_adapter.py
──────────────────────────────────────
AppLovin MAX SSV (Server-Side Verification).
Postback: ?idfa={idfa}&amount={amount}&currency={currency}&event_id={event_id}&custom_data={custom_data}
Signature: SHA-256 hash of sorted query string + secret (in 'hash' param).
"""
from .base_adapter import BaseNetworkAdapter

class AppLovinAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "applovin"
    FIELD_MAP = {
        "lead_id": "idfa", "offer_id": "ad_unit_id", "payout": "amount",
        "currency": "currency", "transaction_id": "event_id",
        "user_id": "custom_data",
    }
    SIGNATURE_ALGORITHM = "sha256"
    SIGNATURE_PARAM = "hash"
    REQUIRED_FIELDS = ["payout"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
