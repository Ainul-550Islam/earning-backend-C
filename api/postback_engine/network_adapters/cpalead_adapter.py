"""
network_adapters/cpalead_adapter.py
─────────────────────────────────────
CPALead Network Adapter — Production-ready.

CPALead Postback URL format:
  GET /api/postback_engine/postback/cpalead/
      ?sub1={sub1}          ← our click_id / user_id
      &oid={oid}            ← offer ID
      &amount={amount}      ← payout in USD
      &sid={sid}            ← unique transaction ID
      &currency={currency}  ← currency code (optional, defaults USD)
      &status={status}      ← 1=approved, 0=rejected (optional)

Authentication:
  - HMAC-SHA256 signature in X-Postback-Signature header OR &sig= param
  - Timestamp in X-Postback-Timestamp header OR &ts= param
  - IP whitelist from CPALead's server IP list

CPALead-specific notes:
  - Only fires postbacks on APPROVED conversions (no status=0 by default)
  - sub1 carries our user/click identifier
  - sub2, sub3 available for additional tracking params
  - Payout is in USD by default
"""
from .base_adapter import BaseNetworkAdapter
from decimal import Decimal


class CPALeadAdapter(BaseNetworkAdapter):
    """
    CPALead network adapter with full field mapping,
    status normalisation, and macro expansion.
    """

    NETWORK_KEY = "cpalead"

    FIELD_MAP = {
        # Standard field name → CPALead param name
        "lead_id":        "sub1",      # Our click_id / user identifier
        "offer_id":       "oid",       # CPALead offer ID
        "payout":         "amount",    # USD payout amount
        "transaction_id": "sid",       # CPALead unique session/transaction ID
        "currency":       "currency",  # Currency code
        "status":         "status",    # Conversion status (1/0)
        "sub_id":         "sub2",      # Secondary tracking param
        "user_id":        "sub3",      # Tertiary tracking param (user ID)
        "offer_name":     "name",      # Offer name (if provided)
        "goal_id":        "goal",      # Goal identifier
    }

    # CPALead-specific status codes
    STATUS_MAP = {
        "1":        "approved",   # Approved conversion
        "0":        "rejected",   # Rejected / chargeback
        "approved": "approved",
        "rejected": "rejected",
    }

    # Fields that CPALead always sends (hard requirements)
    REQUIRED_FIELDS = ["lead_id", "payout"]

    # CPALead uses HMAC-SHA256 with the 'sig' query parameter
    SIGNATURE_ALGORITHM = "hmac_sha256"
    SIGNATURE_PARAM = "sig"
    TIMESTAMP_PARAM = "ts"

    def get_network_key(self) -> str:
        return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        """
        CPALead only sends postbacks for approved conversions by default.
        When status is absent → treat as approved.
        """
        if not raw_status:
            return "approved"
        return self.STATUS_MAP.get(str(raw_status).strip(), "approved")

    def get_postback_url_template(self) -> str:
        """
        Template for the outbound confirmation URL to send back to CPALead
        after we process their postback.
        """
        return (
            "https://cpalead.com/dashboard/reports/campaign_postback.php"
            "?offer={offer_id}&sub={click_id}&amount={payout}&status={status}"
        )
