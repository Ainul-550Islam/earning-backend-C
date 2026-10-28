# services/offerwall/offertoro.py
"""
OffertoroAdapter — Offertoro Network Integration.
Owner: OffertoroAdapter (এক কাজের জন্য একটাই মালিক)

Offertoro specialities:
  • Multi-currency payout (USD, EUR, GBP native)
  • Real-time S2S postback
  • Offer wall + surveys + videos
  • Postback: GET with MD5(user_id + secret)
  • High payout CPA for Tier-1 geos

Postback URL format:
  /api/wallet/postback/offertoro/?user_id={uid}&reward={reward}
  &oid={offer_id}&txid={tx_id}&hash={hash}&currency={currency}
"""
import hashlib
import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings

from .base import BaseOfferwallAdapter, ConversionPayload, OfferwallOffer

logger = logging.getLogger("wallet.offerwall.offertoro")

OFFERTORO_API   = "https://www.offertoro.com/api/v1"
OFFERTORO_WALL  = "https://www.offertoro.com/ifr"


class OffertoroAdapter(BaseOfferwallAdapter):
    """
    Offertoro platform adapter.
    Owns all Offertoro-specific multi-currency postback and API logic.
    """

    platform_name  = "offertoro"
    secret_setting = "OFFERTORO_SECRET_KEY"

    # Offertoro pays in USD but tracks in virtual currency (coins)
    # coins_per_dollar controls the virtual → real conversion
    COINS_PER_DOLLAR = 100

    def __init__(self):
        self.pub_id  = getattr(settings, "OFFERTORO_PUB_ID", "")
        self.app_id  = getattr(settings, "OFFERTORO_APP_ID", "")
        self.secret  = getattr(settings, "OFFERTORO_SECRET_KEY", "")
        self.api_key = getattr(settings, "OFFERTORO_API_KEY", "")

    # ── Postback ──────────────────────────────────────────────────────

    def verify_postback(self, request_data: dict, signature: str = "") -> bool:
        """
        Offertoro signature: MD5(user_id + secret)
        """
        if not self.secret:
            logger.warning("[offertoro] No secret — skipping sig check")
            return True

        user_id  = str(request_data.get("user_id", ""))
        sig      = request_data.get("hash", signature)
        expected = hashlib.md5(f"{user_id}{self.secret}".encode()).hexdigest()

        if not sig:
            return False
        return sig.lower() == expected.lower()

    def parse_postback(self, request_data: dict) -> ConversionPayload:
        """
        Offertoro GET postback params:
          user_id, reward (coins), oid (offer_id), txid, hash,
          currency (USD/EUR/GBP), ip, country
        """
        # Reward arrives as coins → convert to USD
        raw_coins  = Decimal(str(request_data.get("reward", "0") or "0"))
        payout_usd = raw_coins / Decimal(str(self.COINS_PER_DOLLAR))

        # Offertoro may send currency override
        currency   = str(request_data.get("currency", "USD")).upper()
        if currency != "USD":
            # Convert to USD if EUR/GBP
            payout_usd = self._to_usd(payout_usd, currency)

        return ConversionPayload(
            platform     = self.platform_name,
            click_id     = str(request_data.get("txid", "")),
            offer_id     = str(request_data.get("oid", "")),
            payout_usd   = payout_usd,
            user_id      = self._int_or_none(request_data.get("user_id")),
            sub_id       = str(request_data.get("user_id", "")),
            ip_address   = str(request_data.get("ip", "")),
            country_code = str(request_data.get("country", "")).upper(),
            device_type  = str(request_data.get("device", "desktop")),
            status       = "approved",
            raw          = {
                **dict(request_data),
                "original_currency": currency,
                "original_coins":    str(raw_coins),
            },
        )

    # ── Offer Fetching ────────────────────────────────────────────────

    def fetch_offers(
        self,
        country_code: str = "BD",
        device_type: str = "desktop",
        limit: int = 50,
    ) -> list[OfferwallOffer]:
        """Fetch offers from Offertoro API."""
        import requests

        if not self.api_key or not self.pub_id:
            logger.debug("[offertoro] No API credentials — returning empty list")
            return []

        try:
            params = {
                "api_key":    self.api_key,
                "pub_id":     self.pub_id,
                "app_id":     self.app_id,
                "country":    country_code,
                "device":     device_type,
                "limit":      limit,
            }
            resp = requests.get(
                f"{OFFERTORO_API}/offers",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            offers = []
            for o in data.get("offers", []):
                payout_raw = Decimal(str(o.get("payout_usd", o.get("payout", "0"))))
                offers.append(OfferwallOffer(
                    offer_id     = str(o.get("id", "")),
                    title        = o.get("name", ""),
                    payout_usd   = payout_raw,
                    payout_bdt   = self._usd_to_bdt(payout_raw),
                    offer_type   = self._map_type(o.get("type", "cpa")),
                    platform     = self.platform_name,
                    url          = o.get("url", ""),
                    icon_url     = o.get("image", ""),
                    description  = o.get("description", ""),
                    requirements = o.get("requirements", ""),
                    geo_countries= o.get("countries", [country_code]),
                    category     = o.get("category", ""),
                    vertical     = o.get("vertical", ""),
                ))
            return offers

        except Exception as exc:
            logger.warning(f"[offertoro] fetch_offers failed: {exc}")
            return []

    # ── Smartwall ─────────────────────────────────────────────────────

    def get_smartwall_url(self, user_id: int, sub_id: str = "") -> str:
        """Offertoro iframe wall URL."""
        if not self.pub_id or not self.app_id:
            return ""
        return (
            f"{OFFERTORO_WALL}/show/{self.pub_id}/{self.app_id}"
            f"/?user_id={user_id}"
        )

    # ── Multi-currency helpers ────────────────────────────────────────

    @staticmethod
    def _to_usd(amount: Decimal, currency: str) -> Decimal:
        """Simple EUR/GBP → USD conversion (uses exchange_rates if available)."""
        try:
            from ...exchange_rates import convert_to_usd
            return convert_to_usd(amount, currency)
        except Exception:
            rates = {"EUR": Decimal("1.08"), "GBP": Decimal("1.25")}
            return amount * rates.get(currency, Decimal("1"))

    @staticmethod
    def _int_or_none(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _map_type(raw: str) -> str:
        return {"cpi": "cpi", "cpa": "cpa", "cpc": "cpc",
                "survey": "survey", "video": "video",
                "cpl": "cpl"}.get(raw.lower(), "cpa")

    @staticmethod
    def _usd_to_bdt(usd: Decimal) -> Decimal:
        try:
            from ...exchange_rates import convert_usd_to_bdt
            return convert_usd_to_bdt(usd)
        except Exception:
            return usd * Decimal("110")
