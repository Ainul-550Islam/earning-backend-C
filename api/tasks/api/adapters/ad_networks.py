"""
api/adapters/ad_networks.py
Ad network adapter stubs — OGAds, AdGate Media, Monlix, OfferToro, CPAlead
Each platform's live client lives in api/external/<platform>.py (to be created).
This adapter exposes a unified interface consumed by tasks/cpalead_tasks.py
and tasks/offer_tasks.py so task code never talks to external SDKs directly.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AdNetworkAdapterBase:
    platform_name: str = "base"

    def fetch_offers(self, pub_id: str, country: str = "US", limit: int = 50) -> list:
        raise NotImplementedError

    def process_postback(self, data: dict) -> dict:
        raise NotImplementedError

    def validate_conversion(self, transaction_id: str, offer_id: str) -> bool:
        raise NotImplementedError


class CPALeadAdapter(AdNetworkAdapterBase):
    """CPAlead S2S postback + offer feed adapter."""
    platform_name = "cpalead"

    def fetch_offers(self, pub_id: str, country: str = "US", limit: int = 50) -> list:
        logger.info("[CPAlead] fetch_offers pub=%s country=%s", pub_id, country)
        # TODO: call api/external/cpalead.py client
        return []

    def process_postback(self, data: dict) -> dict:
        from api.tasks.cpalead_tasks import cpalead_process_postback
        return cpalead_process_postback.delay(data)

    def validate_conversion(self, transaction_id: str, offer_id: str) -> bool:
        # TODO: CPAlead conversion verification endpoint
        return True


class OGAdsAdapter(AdNetworkAdapterBase):
    """
    OGAds content locker & offerwall adapter.
    OGAds uses a REST API at https://ogads.com/api/
    Required env vars: OGADS_API_KEY, OGADS_PUB_ID
    Postback URL pattern: /postback/ogads/?click_id={aff_sub}&payout={payout}
    """
    platform_name = "ogads"

    def fetch_offers(self, pub_id: str, country: str = "US", limit: int = 50) -> list:
        """
        GET https://ogads.com/api/offers
        ?api_key=KEY&country=US&os=all&limit=50
        Returns JSON list of offer dicts with: offer_id, name, payout, countries, type
        """
        logger.info("[OGAds] fetch_offers pub=%s country=%s", pub_id, country)
        # TODO: import and call api.external.ogads client when created
        return []

    def process_postback(self, data: dict) -> dict:
        """
        OGAds postback params: click_id, offer_id, payout, ip, status
        status values: 'approved' | 'reversed'
        """
        logger.info("[OGAds] process_postback data=%s", data)
        # Delegate to generic postback task
        from api.tasks.postback_tasks import process_postback_task
        return {"status": "queued", "platform": "ogads"}

    def validate_conversion(self, transaction_id: str, offer_id: str) -> bool:
        return True


class AdGateMediaAdapter(AdNetworkAdapterBase):
    """
    AdGate Media offerwall adapter.
    REST API: https://adgatemedia.com/api/v1/
    Required env vars: ADGATE_API_KEY, ADGATE_WALL_ID
    Postback: /postback/adgate/?user_id={user_id}&amount={amount}&currency={currency}
    """
    platform_name = "adgate"

    def fetch_offers(self, pub_id: str, country: str = "US", limit: int = 50) -> list:
        """
        GET https://adgatemedia.com/api/v1/offers
        ?wall_id=WALL&api_key=KEY&country=US&limit=50
        Returns: offer_id, name, description, payout, currency, countries[], type
        """
        logger.info("[AdGate] fetch_offers pub=%s country=%s", pub_id, country)
        return []

    def process_postback(self, data: dict) -> dict:
        """
        AdGate postback: user_id, amount, currency (points or USD), offer_id, transaction_id
        """
        logger.info("[AdGate] process_postback data=%s", data)
        return {"status": "queued", "platform": "adgate"}

    def validate_conversion(self, transaction_id: str, offer_id: str) -> bool:
        return True


class OfferToroAdapter(AdNetworkAdapterBase):
    """
    OfferToro offerwall adapter.
    REST API: https://www.offertoro.com/api/
    Required env vars: OFFERTORO_APP_ID, OFFERTORO_SECRET
    Postback: /postback/offertoro/?user_id={userId}&amount={amount}&token={token}
    """
    platform_name = "offertoro"

    def fetch_offers(self, pub_id: str, country: str = "US", limit: int = 50) -> list:
        """
        GET https://www.offertoro.com/api/served/offers/
        ?app_id=APP_ID&pub_id=PUB_ID&user_id=USER_ID&country=US
        Returns: offer_id, name, payout, currency, image_url, instructions, countries
        """
        logger.info("[OfferToro] fetch_offers pub=%s country=%s", pub_id, country)
        return []

    def process_postback(self, data: dict) -> dict:
        """
        OfferToro postback: userId, amount, token, transactionId, offerId
        Security: HMAC-SHA256 signature via token field
        """
        logger.info("[OfferToro] process_postback data=%s", data)
        return {"status": "queued", "platform": "offertoro"}

    def validate_conversion(self, transaction_id: str, offer_id: str) -> bool:
        return True


class MonlixAdapter(AdNetworkAdapterBase):
    """
    Monlix offerwall adapter.
    REST API: https://api.monlix.com/v1/
    Required env vars: MONLIX_APP_ID, MONLIX_API_KEY
    Postback: /postback/monlix/?user_id={userid}&amount={amount}&app_id={appid}
    Supports: CPA, CPI, CPE (Cost Per Engagement), Surveys
    """
    platform_name = "monlix"

    def fetch_offers(self, pub_id: str, country: str = "US", limit: int = 50) -> list:
        """
        GET https://api.monlix.com/v1/offers
        ?app_id=APP_ID&api_key=API_KEY&user_id=USER_ID&ip=IP&country=US&limit=50
        Returns: offer_id, title, description, payout, currency, type (cpa/cpi/survey),
                 requirements, image_url, time_estimate, countries[]
        """
        logger.info("[Monlix] fetch_offers pub=%s country=%s", pub_id, country)
        return []

    def process_postback(self, data: dict) -> dict:
        """
        Monlix postback: userid, amount, app_id, offer_id, transaction_id, type
        type: 'cpa' | 'cpi' | 'survey' | 'cpe'
        Security: IP whitelist + HMAC token
        """
        logger.info("[Monlix] process_postback data=%s", data)
        return {"status": "queued", "platform": "monlix"}

    def validate_conversion(self, transaction_id: str, offer_id: str) -> bool:
        return True


# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, AdNetworkAdapterBase] = {
    "cpalead": CPALeadAdapter(),
    "ogads": OGAdsAdapter(),
    "adgate": AdGateMediaAdapter(),
    "offertoro": OfferToroAdapter(),
    "monlix": MonlixAdapter(),
}


def get_adapter(platform: str) -> Optional[AdNetworkAdapterBase]:
    """Return the adapter for the given platform slug, or None if unknown."""
    return _REGISTRY.get(platform.lower())


def list_platforms() -> list[str]:
    return list(_REGISTRY.keys())
