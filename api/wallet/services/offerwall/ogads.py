# services/offerwall/ogads.py
"""
OGAdsAdapter — OGAds CPA Network Integration.
Owner: OGAdsAdapter (এক কাজের জন্য একটাই মালিক)

OGAds specialities:
  • Mobile-first CPI/CPA (iOS + Android)
  • Smartwall (iframe embed)
  • Content Locker
  • API v2 for offer fetching
  • Postback: GET with MD5 signature: MD5(ip + secret + payout)

Postback URL format:
  /api/wallet/postback/ogads/?click_id={click_id}&payout={payout}
  &user_id={sub1}&offer_id={offer_id}&ip={ip}&sig={sig}
"""
import hashlib
import logging
import urllib.parse
from decimal import Decimal
from typing import Optional

from django.conf import settings

from .base import BaseOfferwallAdapter, ConversionPayload, OfferwallOffer

logger = logging.getLogger("wallet.offerwall.ogads")

OGADS_API_BASE  = "https://ogads.com"
OGADS_API_V2    = "https://api.ogads.com/v2"


class OGAdsAdapter(BaseOfferwallAdapter):
    """
    OGAds CPA network adapter.
    Single owner of all OGAds-specific postback parsing, signature
    verification, and API communication.
    """

    platform_name   = "ogads"
    secret_setting  = "OGADS_POSTBACK_SECRET"

    def __init__(self):
        self.api_key      = getattr(settings, "OGADS_API_KEY", "")
        self.secret       = getattr(settings, "OGADS_POSTBACK_SECRET", "")
        self.publisher_id = getattr(settings, "OGADS_PUBLISHER_ID", "")
        self.wall_id      = getattr(settings, "OGADS_WALL_ID", "")

    # ── Postback ──────────────────────────────────────────────────────

    def verify_postback(self, request_data: dict, signature: str = "") -> bool:
        """
        OGAds signature: MD5(ip_address + secret + payout)
        If OGADS_POSTBACK_SECRET is blank, skip verification (dev mode).
        """
        if not self.secret:
            logger.warning("[ogads] No secret configured — skipping sig check")
            return True

        ip      = request_data.get("ip", "")
        payout  = request_data.get("payout", "")
        sig     = request_data.get("sig", signature)
        expected = self._md5(f"{ip}{self.secret}{payout}")
        if not sig:
            return False
        return sig.lower() == expected.lower()

    def parse_postback(self, request_data: dict) -> ConversionPayload:
        """
        OGAds GET postback params:
          click_id, payout, sub1 (user_id), offer_id, ip, country, device
        """
        return ConversionPayload(
            platform     = self.platform_name,
            click_id     = str(request_data.get("click_id", "")),
            offer_id     = str(request_data.get("offer_id", "")),
            payout_usd   = Decimal(str(request_data.get("payout", "0") or "0")),
            user_id      = self._int_or_none(request_data.get("sub1")),
            sub_id       = str(request_data.get("sub1", "")),
            ip_address   = str(request_data.get("ip", "")),
            country_code = str(request_data.get("country", "")).upper(),
            device_type  = str(request_data.get("device", "desktop")),
            status       = "approved",
            raw          = dict(request_data),
        )

    # ── Offer Fetching ────────────────────────────────────────────────

    def fetch_offers(
        self,
        country_code: str = "BD",
        device_type: str = "desktop",
        limit: int = 50,
    ) -> list[OfferwallOffer]:
        """
        Fetch live offers from OGAds API v2.
        Returns empty list on error (non-blocking).
        """
        import requests

        if not self.api_key:
            logger.debug("[ogads] No API key — returning empty offer list")
            return []

        try:
            params = {
                "api_key":   self.api_key,
                "country":   country_code,
                "device":    "mobile" if device_type == "mobile" else "desktop",
                "limit":     limit,
                "type":      "all",
            }
            resp = requests.get(
                f"{OGADS_API_V2}/offers",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            offers = []
            for o in data.get("offers", []):
                offers.append(OfferwallOffer(
                    offer_id    = str(o.get("id", "")),
                    title       = o.get("name", ""),
                    payout_usd  = Decimal(str(o.get("payout", "0"))),
                    payout_bdt  = self._usd_to_bdt(Decimal(str(o.get("payout", "0")))),
                    offer_type  = self._map_type(o.get("type", "cpa")),
                    platform    = self.platform_name,
                    url         = o.get("tracking_url", ""),
                    icon_url    = o.get("icon", ""),
                    description = o.get("description", ""),
                    requirements= o.get("requirements", ""),
                    is_mobile   = o.get("is_mobile", False),
                    is_desktop  = o.get("is_desktop", True),
                    category    = o.get("category", ""),
                    vertical    = o.get("vertical", ""),
                ))
            return offers

        except Exception as exc:
            logger.warning(f"[ogads] fetch_offers failed: {exc}")
            return []

    # ── Smartwall ─────────────────────────────────────────────────────

    def get_smartwall_url(self, user_id: int, sub_id: str = "") -> str:
        """
        OGAds smartwall embed URL.
        The sub1 param carries user_id so postback can credit the right user.
        """
        if not self.publisher_id:
            return ""
        sub = sub_id or str(user_id)
        return (
            f"{OGADS_API_BASE}/gateway/generate.php"
            f"?pub_id={self.publisher_id}&sub1={sub}"
            f"&device=desktop"
        )

    def get_offer_url(self, offer: OfferwallOffer, user_id: int, sub_id: str = "") -> str:
        """Build per-user tracking URL for a single OGAds offer."""
        base = offer.url
        sep  = "&" if "?" in base else "?"
        sub  = sub_id or str(user_id)
        return f"{base}{sep}sub1={sub}&pub_id={self.publisher_id}"

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _int_or_none(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _map_type(raw: str) -> str:
        mapping = {
            "cpi": "cpi", "cpa": "cpa", "cpc": "cpc",
            "cpl": "cpl", "content_lock": "content_lock",
        }
        return mapping.get(raw.lower(), "cpa")

    @staticmethod
    def _usd_to_bdt(usd: Decimal) -> Decimal:
        try:
            from ...exchange_rates import convert_usd_to_bdt
            return convert_usd_to_bdt(usd)
        except Exception:
            return usd * Decimal("110")  # fallback rate
