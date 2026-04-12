"""
network_adapters/offerwall_adapter.py
───────────────────────────────────────
Generic Offerwall Network Adapter.
Used as a base for all offerwall-type networks (CPALead, AdGate, OfferToro, etc.)
and as a fallback for offerwall networks without a specific adapter.

Offerwall networks share common patterns:
  - Virtual currency rewards (points, coins, gems)
  - user_id is a game/app player identifier
  - Reward amount is in virtual currency units, not USD
  - Conversion = user completes an offer (survey, install, registration)
  - Postbacks fire immediately on completion (no hold period)

Postback URL pattern (generic):
  GET /api/postback_engine/postback/{network_key}/
      ?user_id={user_id}
      &amount={amount}
      &offer_id={offer_id}
      &transaction_id={transaction_id}
"""
from .base_adapter import BaseNetworkAdapter


class OfferwallAdapter(BaseNetworkAdapter):
    """
    Generic offerwall adapter. Handles common offerwall postback patterns.
    Override FIELD_MAP in subclasses for network-specific param names.
    """

    NETWORK_KEY = "offerwall"

    FIELD_MAP = {
        "lead_id":        "user_id",
        "offer_id":       "offer_id",
        "payout":         "amount",
        "transaction_id": "transaction_id",
        "currency":       "currency",
        "status":         "status",
        "sub_id":         "sub_id",
    }

    # Offerwall networks only fire on approved conversions
    STATUS_MAP = {
        "1": "approved",
        "0": "rejected",
        "approved": "approved",
        "rejected": "rejected",
        "reversed": "rejected",
    }

    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self) -> str:
        return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        """Most offerwall networks only fire on success — default to approved."""
        if not raw_status:
            return "approved"
        return self.STATUS_MAP.get(str(raw_status).lower().strip(), "approved")


# ── OfferToro ─────────────────────────────────────────────────────────────────

class OfferToroAdapter(OfferwallAdapter):
    """
    OfferToro Postback:
      ?user_id={user_id}&amount={amount}&oid={oid}&trans_id={trans_id}&type={type}
    type: 1=approved, 2=rejected, 3=reversed
    """
    NETWORK_KEY = "offertoro"
    FIELD_MAP = {
        "lead_id":        "user_id",
        "offer_id":       "oid",
        "payout":         "amount",
        "transaction_id": "trans_id",
        "currency":       "currency",
        "status":         "type",
        "ip_address":     "ip",
    }
    STATUS_MAP = {"1": "approved", "2": "rejected", "3": "rejected"}

    def get_network_key(self): return self.NETWORK_KEY


# ── AdGem ─────────────────────────────────────────────────────────────────────

class AdGemAdapter(OfferwallAdapter):
    """
    AdGem Postback:
      ?player_id={player_id}&amount={amount}&offer_id={offer_id}&order_id={order_id}
    """
    NETWORK_KEY = "adgem"
    FIELD_MAP = {
        "lead_id":        "player_id",
        "offer_id":       "offer_id",
        "payout":         "amount",
        "transaction_id": "order_id",
        "status":         "status",
        "currency":       "currency",
        "user_id":        "player_id",
    }
    STATUS_MAP = {"1": "approved", "0": "rejected"}
    REQUIRED_FIELDS = ["lead_id", "payout"]

    def get_network_key(self): return self.NETWORK_KEY


# ── Tapjoy ────────────────────────────────────────────────────────────────────

class TapjoyAdapter(OfferwallAdapter):
    """
    Tapjoy Direct Play Postback:
      ?snuid={snuid}&id={id}&virtual_currency={vc}&verifier={verifier}
    """
    NETWORK_KEY = "tapjoy"
    FIELD_MAP = {
        "lead_id":        "snuid",
        "offer_id":       "id",
        "payout":         "virtual_currency",
        "transaction_id": "verifier",
        "user_id":        "snuid",
        "currency":       "currency",
    }
    SIGNATURE_PARAM = "verifier"
    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"  # Tapjoy only fires on completion


# ── RevenueWall ───────────────────────────────────────────────────────────────

class RevenueWallAdapter(OfferwallAdapter):
    """Revenue Wall offerwall postback adapter."""
    NETWORK_KEY = "revenuewall"

    def get_network_key(self): return self.NETWORK_KEY


# ── Adscend Media ─────────────────────────────────────────────────────────────

class AdscendAdapter(OfferwallAdapter):
    """
    Adscend Media Postback:
      ?uid={uid}&amount={amount}&campaign_id={campaign_id}&tid={tid}
    """
    NETWORK_KEY = "adscend"
    FIELD_MAP = {
        "lead_id":        "uid",
        "offer_id":       "campaign_id",
        "payout":         "amount",
        "transaction_id": "tid",
        "status":         "status",
        "currency":       "currency",
    }
    STATUS_MAP = {
        "approved":   "approved",
        "chargeback": "rejected",
        "reversed":   "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "payout"]

    def get_network_key(self): return self.NETWORK_KEY
