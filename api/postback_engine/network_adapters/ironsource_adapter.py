"""
network_adapters/ironsource_adapter.py
────────────────────────────────────────
IronSource rewarded ad S2S callback.
Postback: ?userId={userId}&placementId={placementId}&rewardAmount={rewardAmount}&rewardName={rewardName}&eventId={eventId}
"""
from .base_adapter import BaseNetworkAdapter

class IronSourceAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "ironsource"
    FIELD_MAP = {
        "lead_id": "userId", "offer_id": "placementId", "payout": "rewardAmount",
        "currency": "rewardName", "transaction_id": "eventId", "user_id": "userId",
    }
    SIGNATURE_PARAM = "signature"
    REQUIRED_FIELDS = ["user_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
