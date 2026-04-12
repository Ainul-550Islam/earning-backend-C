"""
network_adapters/admob_adapter.py
───────────────────────────────────
Google AdMob SSV (Server-Side Verification).
Uses ECDSA P-256 signature — verify against Google's public key.
Postback: ?ad_unit={ad_unit}&reward_amount={reward_amount}&reward_item={reward_item}&transaction_id={transaction_id}&user_id={user_id}
"""
from .base_adapter import BaseNetworkAdapter

class AdMobAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "admob"
    FIELD_MAP = {
        "lead_id": "user_id", "offer_id": "ad_unit", "payout": "reward_amount",
        "currency": "reward_item", "transaction_id": "transaction_id", "user_id": "user_id",
    }
    SIGNATURE_ALGORITHM = "ecdsa"
    SIGNATURE_PARAM = "signature"
    REQUIRED_FIELDS = ["transaction_id"]
    def get_network_key(self): return self.NETWORK_KEY
    def normalise_status(self, raw_status): return "approved"
