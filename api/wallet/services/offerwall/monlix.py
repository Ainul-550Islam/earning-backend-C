# services/offerwall/monlix.py
"""
MonlixAdapter — Monlix Network Integration.
Owner: MonlixAdapter (এক কাজের জন্য একটাই মালিক)

Monlix specialities:
  • CPL (Cost Per Lead): email submit, pin submit, zip/postal submit
  • Surveys (direct integration with panel providers)
  • Mobile-first offer wall
  • Postback: SHA-256 signature with timestamp
  • High-volume low-payout model (many small conversions)

Postback format:
  /api/wallet/postback/monlix/?userid={uid}&amount={amount}
  &offerid={oid}&transid={tid}&signature={sig}&timestamp={ts}
  sig = SHA256(uid + secret + amount + timestamp)
"""
import hashlib
import logging
import time
from decimal import Decimal
from typing import Optional

from django.conf import settings

from .base import BaseOfferwallAdapter, ConversionPayload, OfferwallOffer

logger = logging.getLogger("wallet.offerwall.monlix")

MONLIX_API  = "https://api.monlix.com/v1"
MONLIX_WALL = "https://wall.monlix.com"


class MonlixAdapter(BaseOfferwallAdapter):
    """
    Monlix platform adapter.
    Owns all Monlix-specific CPL/survey/lead-submit postback logic.
    """

    platform_name  = "monlix"
    secret_setting = "MONLIX_SECRET_KEY"

    # Monlix payout types
    LEAD_TYPES = {
        "email_submit": "CPL — Email Submit",
        "pin_submit":   "CPL — PIN Submit",
        "zip_submit":   "CPL — ZIP/Postal Submit",
        "cc_submit":    "CPL — Credit Card Submit",
        "survey":       "Survey",
        "cpa":          "CPA",
        "cpi":          "CPI",
    }

    def __init__(self):
        self.app_id  = getattr(settings, "MONLIX_APP_ID", "")
        self.secret  = getattr(settings, "MONLIX_SECRET_KEY", "")
        self.api_key = getattr(settings, "MONLIX_API_KEY", "")

    # ── Postback ──────────────────────────────────────────────────────

    def verify_postback(self, request_data: dict, signature: str = "") -> bool:
        """
        Monlix signature: SHA256(userid + secret + amount + timestamp)
        Allows ±300s timestamp drift.
        """
        if not self.secret:
            logger.warning("[monlix] No secret — skipping sig check")
            return True

        user_id   = str(request_data.get("userid", ""))
        amount    = str(request_data.get("amount", ""))
        timestamp = str(request_data.get("timestamp", ""))
        sig       = request_data.get("signature", signature)

        # Replay protection: reject if timestamp > 5 min old
        try:
            ts_int = int(timestamp)
            if abs(time.time() - ts_int) > 300:
                logger.warning(f"[monlix] Stale postback timestamp: {ts_int}")
                return False
        except (TypeError, ValueError):
            pass

        expected = hashlib.sha256(
            f"{user_id}{self.secret}{amount}{timestamp}".encode()
        ).hexdigest()

        if not sig:
            return False
        return sig.lower() == expected.lower()

    def parse_postback(self, request_data: dict) -> ConversionPayload:
        """
        Monlix GET postback:
          userid, amount (USD cents), offerid, transid,
          signature, timestamp, lead_type, country, ip
        """
        # Monlix amount is in USD cents
        raw_cents  = Decimal(str(request_data.get("amount", "0") or "0"))
        payout_usd = raw_cents / Decimal("100")

        lead_type = str(request_data.get("lead_type", "cpa")).lower()
        # Map CPL types to our offer_type
        offer_type = "cpl" if "submit" in lead_type else lead_type

        return ConversionPayload(
            platform     = self.platform_name,
            click_id     = str(request_data.get("transid", "")),
            offer_id     = str(request_data.get("offerid", "")),
            payout_usd   = payout_usd,
            user_id      = self._int_or_none(request_data.get("userid")),
            sub_id       = str(request_data.get("userid", "")),
            ip_address   = str(request_data.get("ip", "")),
            country_code = str(request_data.get("country", "")).upper(),
            device_type  = str(request_data.get("device", "desktop")),
            status       = "approved",
            raw          = {
                **dict(request_data),
                "lead_type":   lead_type,
                "mapped_type": offer_type,
            },
        )

    # ── Offer Fetching ────────────────────────────────────────────────

    def fetch_offers(
        self,
        country_code: str = "BD",
        device_type: str = "desktop",
        limit: int = 50,
    ) -> list[OfferwallOffer]:
        """Fetch Monlix offers via API."""
        import requests

        if not self.api_key or not self.app_id:
            logger.debug("[monlix] No API credentials — returning empty list")
            return []

        try:
            params = {
                "api_key":   self.api_key,
                "app_id":    self.app_id,
                "country":   country_code,
                "platform":  "desktop" if device_type == "desktop" else "mobile",
                "limit":     limit,
            }
            resp = requests.get(
                f"{MONLIX_API}/offers",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            offers = []
            for o in data.get("data", data.get("offers", [])):
                payout_raw = Decimal(str(o.get("payout", "0")))
                lead_type  = str(o.get("lead_type", o.get("type", "cpa"))).lower()
                offer_type = "cpl" if "submit" in lead_type else self._map_type(lead_type)

                offers.append(OfferwallOffer(
                    offer_id     = str(o.get("id", "")),
                    title        = o.get("title", o.get("name", "")),
                    payout_usd   = payout_raw,
                    payout_bdt   = self._usd_to_bdt(payout_raw),
                    offer_type   = offer_type,
                    platform     = self.platform_name,
                    url          = o.get("url", ""),
                    icon_url     = o.get("icon", o.get("image", "")),
                    description  = o.get("description", ""),
                    requirements = o.get("requirements", ""),
                    is_mobile    = device_type == "mobile",
                    is_desktop   = device_type == "desktop",
                    category     = o.get("category", ""),
                    vertical     = o.get("vertical", ""),
                ))
            return offers

        except Exception as exc:
            logger.warning(f"[monlix] fetch_offers failed: {exc}")
            return []

    # ── Smartwall ─────────────────────────────────────────────────────

    def get_smartwall_url(self, user_id: int, sub_id: str = "") -> str:
        """Monlix wall embed URL."""
        if not self.app_id:
            return ""
        return (
            f"{MONLIX_WALL}/app/{self.app_id}"
            f"?userid={user_id}"
        )

    # ── Survey routing helpers ────────────────────────────────────────

    def get_survey_offers(
        self,
        country_code: str = "BD",
        min_payout_usd: float = 0.05,
    ) -> list[OfferwallOffer]:
        """Return only survey-type Monlix offers above minimum payout."""
        all_offers = self.fetch_offers(country_code)
        return [
            o for o in all_offers
            if o.offer_type == "survey"
            and o.payout_usd >= Decimal(str(min_payout_usd))
        ]

    def get_cpl_offers(
        self,
        lead_type: str = "email_submit",
        country_code: str = "US",
    ) -> list[OfferwallOffer]:
        """Return CPL offers filtered by lead type (email/pin/zip submit)."""
        all_offers = self.fetch_offers(country_code)
        return [o for o in all_offers if o.offer_type == "cpl"]

    # ── Helpers ───────────────────────────────────────────────────────

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
