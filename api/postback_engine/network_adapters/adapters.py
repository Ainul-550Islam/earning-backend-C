"""
network_adapters/adapters.py
─────────────────────────────
All CPA network adapters with complete field mapping,
status normalisation, and macro support.
"""
from .base_adapter import BaseNetworkAdapter


# ── CPALead ────────────────────────────────────────────────────────────────────

class CPALeadAdapter(BaseNetworkAdapter):
    """
    CPALead postback format:
      GET /postback/cpalead/?sub1={sub1}&amount={amount}&oid={oid}&sid={sid}&status={status}
    Status: CPALead sends no status param on success (only fires on approved).
    """
    NETWORK_KEY = "cpalead"
    FIELD_MAP = {
        "lead_id":        "sub1",
        "offer_id":       "oid",
        "payout":         "amount",
        "transaction_id": "sid",
        "currency":       "currency",
        "status":         "status",
        "sub_id":         "sub2",
        "user_id":        "sub3",
    }
    STATUS_MAP = {
        "1": "approved",
        "0": "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "payout"]

    def get_network_key(self): return self.NETWORK_KEY


# ── AdGate Media ───────────────────────────────────────────────────────────────

class AdGateAdapter(BaseNetworkAdapter):
    """
    AdGate Media postback:
      GET /postback/adgate/?user_id={user_id}&reward={reward}&offer_id={offer_id}&token={token}
    """
    NETWORK_KEY = "adgate"
    FIELD_MAP = {
        "lead_id":        "user_id",
        "offer_id":       "offer_id",
        "payout":         "reward",
        "transaction_id": "token",
        "currency":       "currency",
        "status":         "status",
    }
    STATUS_MAP = {
        "approved":  "approved",
        "rejected":  "rejected",
        "reversed":  "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "payout"]

    def get_network_key(self): return self.NETWORK_KEY


# ── OfferToro ──────────────────────────────────────────────────────────────────

class OfferToroAdapter(BaseNetworkAdapter):
    """
    OfferToro postback:
      GET /postback/offertoro/?user_id={user_id}&amount={amount}&oid={oid}&trans_id={trans_id}
    """
    NETWORK_KEY = "offertoro"
    FIELD_MAP = {
        "lead_id":        "user_id",
        "offer_id":       "oid",
        "payout":         "amount",
        "transaction_id": "trans_id",
        "currency":       "currency",
        "status":         "type",     # OfferToro uses 'type' for status
    }
    STATUS_MAP = {
        "1": "approved",
        "2": "rejected",
        "3": "reversed",
    }
    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self): return self.NETWORK_KEY


# ── Adscend Media ──────────────────────────────────────────────────────────────

class AdscendAdapter(BaseNetworkAdapter):
    """
    Adscend Media postback:
      GET /postback/adscend/?uid={uid}&amount={amount}&campaign_id={campaign_id}&tid={tid}
    """
    NETWORK_KEY = "adscend"
    FIELD_MAP = {
        "lead_id":        "uid",
        "offer_id":       "campaign_id",
        "payout":         "amount",
        "transaction_id": "tid",
        "status":         "status",
    }
    STATUS_MAP = {
        "approved":   "approved",
        "chargeback": "rejected",
        "reversed":   "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "payout"]

    def get_network_key(self): return self.NETWORK_KEY


# ── Revenue Wall ───────────────────────────────────────────────────────────────

class RevenueWallAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "revenuewall"
    FIELD_MAP = {
        "lead_id":        "user_id",
        "offer_id":       "offer_id",
        "payout":         "payout",
        "transaction_id": "transaction_id",
        "status":         "status",
    }
    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self): return self.NETWORK_KEY


# ── AppLovin MAX ───────────────────────────────────────────────────────────────

class AppLovinAdapter(BaseNetworkAdapter):
    """
    AppLovin MAX server-side verification:
      GET /postback/applovin/?idfa={idfa}&amount={amount}&currency={currency}&event_id={event_id}&user_id={user_id}
    AppLovin only fires on success, no status param.
    """
    NETWORK_KEY = "applovin"
    FIELD_MAP = {
        "lead_id":        "idfa",
        "offer_id":       "ad_unit_id",
        "payout":         "amount",
        "currency":       "currency",
        "transaction_id": "event_id",
        "user_id":        "custom_data",
    }
    SIGNATURE_ALGORITHM = "sha256"
    SIGNATURE_PARAM = "hash"
    REQUIRED_FIELDS = ["payout"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        # AppLovin only fires postbacks on reward events
        return "approved"


# ── Unity Ads ──────────────────────────────────────────────────────────────────

class UnityAdsAdapter(BaseNetworkAdapter):
    """
    Unity Ads S2S rewarded callback:
      GET /postback/unity/?productid={productid}&userid={userid}&placementid={placementid}&value={value}&sid={sid}
    """
    NETWORK_KEY = "unity"
    FIELD_MAP = {
        "lead_id":        "productid",
        "offer_id":       "placementid",
        "payout":         "value",
        "currency":       "currency",
        "transaction_id": "sid",
        "user_id":        "userid",
    }
    REQUIRED_FIELDS = ["user_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"


# ── IronSource ─────────────────────────────────────────────────────────────────

class IronSourceAdapter(BaseNetworkAdapter):
    """
    IronSource server-to-server rewarded ad callback.
    """
    NETWORK_KEY = "ironsource"
    FIELD_MAP = {
        "user_id":        "userId",
        "offer_id":       "placementId",
        "payout":         "rewardAmount",
        "currency":       "rewardName",
        "transaction_id": "eventId",
        "lead_id":        "userId",
    }
    SIGNATURE_PARAM = "signature"
    REQUIRED_FIELDS = ["user_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"


# ── AdMob SSV ─────────────────────────────────────────────────────────────────

class AdMobAdapter(BaseNetworkAdapter):
    """
    Google AdMob Server-Side Verification (SSV).
    Uses ECDSA signature, not HMAC.
    """
    NETWORK_KEY = "admob"
    FIELD_MAP = {
        "user_id":        "user_id",
        "lead_id":        "user_id",
        "offer_id":       "ad_unit",
        "payout":         "reward_amount",
        "currency":       "reward_item",
        "transaction_id": "transaction_id",
    }
    SIGNATURE_ALGORITHM = "ecdsa"
    SIGNATURE_PARAM = "signature"
    REQUIRED_FIELDS = ["transaction_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"


# ── Facebook Audience Network ──────────────────────────────────────────────────

class FacebookAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "facebook"
    FIELD_MAP = {
        "lead_id":        "user_id",
        "offer_id":       "placement_id",
        "payout":         "reward_amount",
        "currency":       "currency",
        "transaction_id": "transaction_id",
    }
    REQUIRED_FIELDS = ["transaction_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"


# ── Google (IMA SDK) ───────────────────────────────────────────────────────────

class GoogleAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "google"
    FIELD_MAP = {
        "lead_id":        "user_id",
        "offer_id":       "ad_break_id",
        "payout":         "reward_amount",
        "currency":       "reward_type",
        "transaction_id": "transaction_id",
    }
    REQUIRED_FIELDS = ["transaction_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"


# ── TikTok ─────────────────────────────────────────────────────────────────────

class TikTokAdapter(BaseNetworkAdapter):
    """
    TikTok for Business conversion postback.
    """
    NETWORK_KEY = "tiktok"
    FIELD_MAP = {
        "lead_id":        "click_id",
        "offer_id":       "campaign_id",
        "payout":         "value",
        "currency":       "currency",
        "transaction_id": "event_id",
    }
    STATUS_MAP = {
        "complete": "approved",
        "failed":   "rejected",
    }
    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self): return self.NETWORK_KEY


# ── Impact (impact.com) ────────────────────────────────────────────────────────

class ImpactAdapter(BaseNetworkAdapter):
    """
    Impact affiliate platform.
    Uses PascalCase parameter names.
    """
    NETWORK_KEY = "impact"
    FIELD_MAP = {
        "lead_id":        "ClickId",
        "offer_id":       "CampaignId",
        "payout":         "Payout",
        "currency":       "Currency",
        "transaction_id": "OrderId",
        "user_id":        "CustomerId",
        "status":         "ActionStatus",
    }
    STATUS_MAP = {
        "approved":  "approved",
        "pending":   "pending",
        "rejected":  "rejected",
        "reversed":  "rejected",
        "withdrawn": "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "offer_id"]

    def get_network_key(self): return self.NETWORK_KEY


# ── CAKE ───────────────────────────────────────────────────────────────────────

class CakeAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "cake"
    FIELD_MAP = {
        "lead_id":        "click_id",
        "offer_id":       "offer_id",
        "payout":         "payout",
        "currency":       "currency",
        "transaction_id": "conversion_id",
        "status":         "status",
    }
    STATUS_MAP = {
        "approved":  "approved",
        "rejected":  "rejected",
        "cancelled": "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "offer_id"]

    def get_network_key(self): return self.NETWORK_KEY


# ── HasOffers / TUNE ───────────────────────────────────────────────────────────

class HasOffersAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "hasoffers"
    FIELD_MAP = {
        "lead_id":        "transaction_id",
        "offer_id":       "offer_id",
        "payout":         "payout",
        "currency":       "currency",
        "transaction_id": "conversion_id",
        "user_id":        "affiliate_id",
        "status":         "status",
    }
    STATUS_MAP = {
        "approved":  "approved",
        "pending":   "pending",
        "rejected":  "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "offer_id"]

    def get_network_key(self): return self.NETWORK_KEY


# ── Everflow ───────────────────────────────────────────────────────────────────

class EverflowAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "everflow"
    FIELD_MAP = {
        "lead_id":        "transaction_id",
        "offer_id":       "offer_id",
        "payout":         "payout",
        "currency":       "currency",
        "transaction_id": "conversion_id",
        "status":         "status",
        "goal_id":        "goal_id",
        "goal_value":     "goal_value",
    }
    STATUS_MAP = {
        "approved":  "approved",
        "pending":   "pending",
        "rejected":  "rejected",
        "reversed":  "rejected",
    }
    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self): return self.NETWORK_KEY


# ── Tapjoy ─────────────────────────────────────────────────────────────────────

class TapjoyAdapter(BaseNetworkAdapter):
    """
    Tapjoy Direct Play / offerwall postback.
    """
    NETWORK_KEY = "tapjoy"
    FIELD_MAP = {
        "lead_id":        "snuid",
        "offer_id":       "id",
        "payout":         "virtual_currency",
        "transaction_id": "verifier",
        "user_id":        "snuid",
    }
    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"


# ── AdGem ──────────────────────────────────────────────────────────────────────

class AdGemAdapter(BaseNetworkAdapter):
    """
    AdGem offerwall postback.
    """
    NETWORK_KEY = "adgem"
    FIELD_MAP = {
        "lead_id":        "player_id",
        "offer_id":       "offer_id",
        "payout":         "amount",
        "transaction_id": "order_id",
        "user_id":        "player_id",
        "status":         "status",
    }
    STATUS_MAP = {
        "1": "approved",
        "0": "rejected",
    }
    REQUIRED_FIELDS = ["lead_id", "payout"]

    def get_network_key(self): return self.NETWORK_KEY


# ── Snapchat ───────────────────────────────────────────────────────────────────

class SnapchatAdapter(BaseNetworkAdapter):
    NETWORK_KEY = "snapchat"
    FIELD_MAP = {
        "lead_id":        "click_id",
        "offer_id":       "campaign_id",
        "payout":         "conversion_value",
        "currency":       "currency",
        "transaction_id": "event_conversion_id",
    }
    REQUIRED_FIELDS = ["lead_id"]

    def get_network_key(self): return self.NETWORK_KEY

    def normalise_status(self, raw_status: str) -> str:
        return "approved"


# ── Generic / Fallback ──────────────────────────────────────────────────────────

class _GenericAdapter(BaseNetworkAdapter):
    """
    Fallback adapter: no field renaming, raw params passed through.
    Attempts to auto-detect standard field names.
    """
    _AUTO_DETECT_ALIASES = {
        "lead_id":        ["lead_id", "click_id", "sub_id", "sub1", "uid", "user_id"],
        "offer_id":       ["offer_id", "oid", "campaign_id", "offer"],
        "payout":         ["payout", "amount", "reward", "value", "commission"],
        "currency":       ["currency", "cur"],
        "transaction_id": ["transaction_id", "tid", "conv_id", "sid", "order_id"],
        "status":         ["status", "type", "state"],
    }

    def __init__(self, network_key: str):
        self.NETWORK_KEY = network_key

    def normalise(self, raw_payload: dict) -> dict:
        result = dict(raw_payload)

        # Auto-detect standard field names from aliases
        for standard_name, aliases in self._AUTO_DETECT_ALIASES.items():
            if standard_name not in result:
                for alias in aliases:
                    if alias in raw_payload and alias != standard_name:
                        result[standard_name] = raw_payload[alias]
                        break

        if "payout" in result:
            result["payout"] = self._coerce_payout(result["payout"])
        return result

    def get_network_key(self): return self.NETWORK_KEY


# ── Adapter Registry & Factory ─────────────────────────────────────────────────

ADAPTER_REGISTRY: dict[str, type] = {
    "cpalead":    CPALeadAdapter,
    "adgate":     AdGateAdapter,
    "offertoro":  OfferToroAdapter,
    "adscend":    AdscendAdapter,
    "revenuewall":RevenueWallAdapter,
    "applovin":   AppLovinAdapter,
    "unity":      UnityAdsAdapter,
    "ironsource": IronSourceAdapter,
    "admob":      AdMobAdapter,
    "facebook":   FacebookAdapter,
    "google":     GoogleAdapter,
    "tiktok":     TikTokAdapter,
    "snapchat":   SnapchatAdapter,
    "impact":     ImpactAdapter,
    "cake":       CakeAdapter,
    "hasoffers":  HasOffersAdapter,
    "everflow":   EverflowAdapter,
    "tapjoy":     TapjoyAdapter,
    "adgem":      AdGemAdapter,
}


def get_adapter(network_key: str) -> BaseNetworkAdapter:
    """
    Return the appropriate adapter for a network_key.
    Falls back to generic auto-detecting adapter if not registered.
    """
    adapter_cls = ADAPTER_REGISTRY.get(network_key)
    if adapter_cls:
        return adapter_cls()
    return _GenericAdapter(network_key)
