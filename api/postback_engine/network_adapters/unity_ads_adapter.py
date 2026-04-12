"""
network_adapters/unity_ads_adapter.py
───────────────────────────────────────
Unity Ads rewarded ad S2S callback.
Postback: ?productid={productid}&userid={userid}&placementid={placementid}&value={value}&sid={sid}
"""
from .base_adapter import BaseNetworkAdapter

class UnityAdsAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "unity"
    FIELD_MAP = {
        "lead_id": "productid", "offer_id": "placementid", "payout": "value",
        "currency": "currency", "transaction_id": "sid", "user_id": "userid",
    }
    REQUIRED_FIELDS = ["user_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
