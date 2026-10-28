# services/offerwall/adgate.py
"""
AdGateAdapter — AdGate Media Integration.
Owner: AdGateAdapter (এক কাজের জন্য একটাই মালিক)

AdGate Media specialities:
  • Video reward offers (watch-to-earn)
  • Engagement tracking (percentage watched)
  • Offer wall + surveys
  • Postback: GET with SHA-1 signature
  • API: adgatemedia.com/api

Postback format:
  /api/wallet/postback/adgate/?user_id={user_id}&reward={reward}
  &offer_id={offer_id}&transaction_id={tid}&hash={hash}
  hash = SHA1(user_id + secret + reward)
"""
import hashlib
import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings

from .base import BaseOfferwallAdapter, ConversionPayload, OfferwallOffer

logger = logging.getLogger("wallet.offerwall.adgate")

ADGATE_API_BASE = "https://wall.adgaterewards.com"
ADGATE_API_V1   = "https://adgatemedia.com/api/v1"


class AdGateAdapter(BaseOfferwallAdapter):
    """
    AdGate Media adapter.
    Single owner of all AdGate-specific postback, video reward tracking,
    and engagement metric handling.
    """

    platform_name  = "adgate"
    secret_setting = "ADGATE_SECRET_KEY"

    def __init__(self):
        self.api_key    = getattr(settings, "ADGATE_API_KEY", "")
        self.secret     = getattr(settings, "ADGATE_SECRET_KEY", "")
        self.wall_hash  = getattr(settings, "ADGATE_WALL_HASH", "")

    # ── Postback ──────────────────────────────────────────────────────

    def verify_postback(self, request_data: dict, signature: str = "") -> bool:
        """
        AdGate signature: SHA1(user_id + secret + reward)
        """
        if not self.secret:
            logger.warning("[adgate] No secret configured — skipping sig check")
            return True

        user_id = str(request_data.get("user_id", ""))
        reward  = str(request_data.get("reward", ""))
        sig     = request_data.get("hash", signature)

        expected = hashlib.sha1(
            f"{user_id}{self.secret}{reward}".encode()
        ).hexdigest()

        if not sig:
            return False
        return sig.lower() == expected.lower()

    def parse_postback(self, request_data: dict) -> ConversionPayload:
        """
        AdGate GET postback:
          user_id, reward (in points/cents), offer_id, transaction_id,
          hash, country, ip, device_type, video_pct (video completion %)
        """
        # AdGate rewards are in cents → convert to USD
        raw_reward = Decimal(str(request_data.get("reward", "0") or "0"))
        payout_usd = raw_reward / Decimal("100")

        # Video completion tracking
        video_pct = int(request_data.get("video_pct", 100) or 100)
        status    = "approved" if video_pct >= 80 else "pending"

        return ConversionPayload(
            platform     = self.platform_name,
            click_id     = str(request_data.get("transaction_id", "")),
            offer_id     = str(request_data.get("offer_id", "")),
            payout_usd   = payout_usd,
            user_id      = self._int_or_none(request_data.get("user_id")),
            sub_id       = str(request_data.get("user_id", "")),
            ip_address   = str(request_data.get("ip", "")),
            country_code = str(request_data.get("country", "")).upper(),
            device_type  = str(request_data.get("device_type", "desktop")),
            status       = status,
            raw          = {
                **dict(request_data),
                "video_completion_pct": video_pct,
            },
        )

    # ── Offer Fetching ────────────────────────────────────────────────

    def fetch_offers(
        self,
        country_code: str = "BD",
        device_type: str = "desktop",
        limit: int = 50,
    ) -> list[OfferwallOffer]:
        """Fetch AdGate Media offers via API."""
        import requests

        if not self.api_key:
            logger.debug("[adgate] No API key — returning empty offer list")
            return []

        try:
            params = {
                "api_key": self.api_key,
                "country": country_code,
                "device":  device_type,
                "limit":   limit,
            }
            resp = requests.get(
                f"{ADGATE_API_V1}/offers",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            offers = []
            for o in data.get("offers", data if isinstance(data, list) else []):
                offer_type = "video" if o.get("is_video") else self._map_type(o.get("type", "cpa"))
                offers.append(OfferwallOffer(
                    offer_id    = str(o.get("offerid", o.get("id", ""))),
                    title       = o.get("name", ""),
                    payout_usd  = Decimal(str(o.get("payout", "0"))),
                    payout_bdt  = self._usd_to_bdt(Decimal(str(o.get("payout", "0")))),
                    offer_type  = offer_type,
                    platform    = self.platform_name,
                    url         = o.get("tracking_url", o.get("url", "")),
                    icon_url    = o.get("picture", ""),
                    description = o.get("description", ""),
                    requirements= o.get("requirements", ""),
                    is_mobile   = device_type == "mobile",
                    is_desktop  = device_type == "desktop",
                    category    = o.get("category", ""),
                    vertical    = o.get("vertical", ""),
                ))
            return offers

        except Exception as exc:
            logger.warning(f"[adgate] fetch_offers failed: {exc}")
            return []

    # ── Smartwall ─────────────────────────────────────────────────────

    def get_smartwall_url(self, user_id: int, sub_id: str = "") -> str:
        """AdGate wall embed URL."""
        if not self.wall_hash:
            return ""
        return (
            f"{ADGATE_API_BASE}/{self.wall_hash}"
            f"?user_id={user_id}&aff_sub={sub_id or user_id}"
        )

    # ── Video Reward specific ─────────────────────────────────────────

    def get_video_offers(
        self,
        country_code: str = "BD",
        device_type: str = "desktop",
    ) -> list[OfferwallOffer]:
        """Return only video-type offers from AdGate."""
        all_offers = self.fetch_offers(country_code, device_type)
        return [o for o in all_offers if o.offer_type == "video"]

    def calculate_video_reward(
        self,
        base_payout_usd: Decimal,
        completion_pct: int,
    ) -> Decimal:
        """
        Scale reward by completion percentage.
        <50% watched → 0
        50-79% → 50% reward
        ≥80% → full reward
        """
        if completion_pct >= 80:
            return base_payout_usd
        elif completion_pct >= 50:
            return base_payout_usd * Decimal("0.50")
        else:
            return Decimal("0")

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
                "survey": "survey", "video": "video"}.get(raw.lower(), "cpa")

    @staticmethod
    def _usd_to_bdt(usd: Decimal) -> Decimal:
        try:
            from ...exchange_rates import convert_usd_to_bdt
            return convert_usd_to_bdt(usd)
        except Exception:
            return usd * Decimal("110")
