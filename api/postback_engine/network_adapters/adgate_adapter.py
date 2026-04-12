"""
network_adapters/adgate_adapter.py
────────────────────────────────────
AdGate Media Network Adapter — Production-ready.

AdGate Postback URL format:
  GET /api/postback_engine/postback/adgate/
      ?user_id={user_id}        ← our user/click identifier
      &reward={reward}          ← reward amount (virtual currency or USD)
      &offer_id={offer_id}      ← AdGate offer ID
      &token={token}            ← unique transaction token
      &status={status}          ← approved / rejected / reversed
      &ip={ip}                  ← user IP (for fraud checking)
      &user_agent={user_agent}  ← user agent string

Authentication:
  - HMAC-MD5 or HMAC-SHA256 signature in &hash= param
  - IP whitelist from AdGate's server list

AdGate-specific notes:
  - Reward is in the publisher's configured virtual currency
  - user_id should be set to our click_id or user.id
  - Supports reversal postbacks (status=reversed)
  - token is globally unique per conversion
"""
from .base_adapter import BaseNetworkAdapter


class AdGateAdapter(BaseNetworkAdapter):
    """AdGate Media adapter with full field mapping and status normalisation."""

    NETWORK_KEY = "adgate"

    FIELD_MAP = {
        "lead_id":        "user_id",      # Our user/click identifier
        "offer_id":       "offer_id",     # AdGate offer ID
        "payout":         "reward",       # Reward amount
        "transaction_id": "token",        # Unique transaction token
        "currency":       "currency",     # Currency code
        "status":         "status",       # approved / rejected / reversed
        "sub_id":         "sub_id",       # Additional tracking param
        "click_id":       "click_id",     # Our click_id (if passed as click_id)
        "ip_address":     "ip",           # User IP
        "user_agent_str": "user_agent",   # User agent
    }

    # AdGate-specific status codes
    STATUS_MAP = {
        "approved":  "approved",
        "rejected":  "rejected",
        "reversed":  "rejected",   # Reversal = we lose the payout
        "chargeback":"rejected",
        "1":         "approved",
        "0":         "rejected",
    }

    REQUIRED_FIELDS = ["lead_id", "payout"]

    SIGNATURE_ALGORITHM = "hmac_sha256"
    SIGNATURE_PARAM = "hash"
    TIMESTAMP_PARAM = "ts"

    def get_network_key(self) -> str:
        return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        if not raw_status:
            return "approved"
        return self.STATUS_MAP.get(str(raw_status).lower().strip(), "approved")
