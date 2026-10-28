# services/offerwall/base.py
"""
BaseOfferwallAdapter — contract every platform adapter must implement.

"এক কাজের জন্য একটাই মালিক।"
The base class owns:
  • Postback signature verification
  • Conversion payload normalization
  • Duplicate-conversion guard (idempotency)
  • Credit dispatch to EarningService

Platform adapters only own:
  • Platform-specific field mapping
  • Platform-specific HMAC/hash algo
  • Platform-specific API calls (fetch offers, validate conversion)
"""
import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger("wallet.offerwall.base")

DEDUP_TTL = 86400 * 7  # 7 days — keep click_id dedup for a week


@dataclass
class OfferwallOffer:
    """Normalized offer representation across all platforms."""
    offer_id:      str
    title:         str
    payout_usd:    Decimal
    payout_bdt:    Decimal
    offer_type:    str          # cpa / cpi / cpc / cpl / video / survey
    platform:      str          # ogads / adgate / offertoro / monlix / cpalead
    url:           str
    icon_url:      str          = ""
    description:   str          = ""
    requirements:  str          = ""
    geo_countries: list         = field(default_factory=list)
    is_mobile:     bool         = False
    is_desktop:    bool         = True
    daily_cap:     int          = 0
    category:      str          = ""
    vertical:      str          = ""   # gaming / finance / health / dating / utilities
    device_types:  list         = field(default_factory=lambda: ["desktop", "mobile"])


@dataclass
class ConversionPayload:
    """Normalized inbound postback payload."""
    platform:      str
    click_id:      str
    offer_id:      str
    payout_usd:    Decimal
    user_id:       Optional[int]    = None
    sub_id:        str              = ""
    ip_address:    str              = ""
    user_agent:    str              = ""
    country_code:  str              = ""
    device_type:   str              = ""
    status:        str              = "approved"  # approved / pending / rejected
    raw:           dict             = field(default_factory=dict)


class BaseOfferwallAdapter(ABC):
    """
    Abstract base for all offerwall platform adapters.

    Subclasses MUST implement:
      platform_name   — str, e.g. "ogads"
      verify_postback — HMAC / hash check
      parse_postback  — QueryDict/body → ConversionPayload
      fetch_offers    — return list[OfferwallOffer]

    Subclasses MAY override:
      get_smartwall_url — smartwall embed URL
      get_offer_url     — tracking URL for a single offer
    """

    # ── Subclass must set these ───────────────────────────────────────
    platform_name: str = ""
    secret_setting: str = ""   # settings key for the postback secret

    # ── Public API ────────────────────────────────────────────────────

    @abstractmethod
    def verify_postback(self, request_data: dict, signature: str) -> bool:
        """Return True if the postback signature is valid."""

    @abstractmethod
    def parse_postback(self, request_data: dict) -> ConversionPayload:
        """Map raw query params → ConversionPayload."""

    @abstractmethod
    def fetch_offers(
        self,
        country_code: str = "BD",
        device_type: str = "desktop",
        limit: int = 50,
    ) -> list[OfferwallOffer]:
        """Pull live offers from the platform API."""

    def get_smartwall_url(self, user_id: int, sub_id: str = "") -> str:
        """Return the smartwall embed URL for this platform."""
        return ""

    def get_offer_url(self, offer: OfferwallOffer, user_id: int, sub_id: str = "") -> str:
        """Build a tracking URL for a single offer."""
        return offer.url

    # ── Conversion processing (owned by base — never overridden) ─────

    def process_conversion(self, payload: ConversionPayload) -> dict:
        """
        Idempotent conversion handler.
        1. Dedup check
        2. Resolve user → wallet
        3. EarningService.add_earning
        4. OfferConversion record (via EarningService)
        5. Postback upstream acknowledgment
        """
        dedup_key = f"ow_dedup:{self.platform_name}:{payload.click_id}:{payload.offer_id}"
        if cache.get(dedup_key):
            logger.info(
                f"[{self.platform_name}] Duplicate conversion ignored: "
                f"click_id={payload.click_id}"
            )
            return {"status": "duplicate", "click_id": payload.click_id}

        cache.set(dedup_key, "1", DEDUP_TTL)

        try:
            from django.contrib.auth import get_user_model
            from ..core.WalletService import WalletService
            from ..earning.EarningService import EarningService
            from ...choices import EarningSourceType
            from ...exchange_rates import convert_usd_to_bdt

            User = get_user_model()

            # Resolve user
            user = None
            if payload.user_id:
                try:
                    user = User.objects.get(id=payload.user_id)
                except User.DoesNotExist:
                    pass
            if user is None and payload.sub_id:
                # sub_id may encode user_id
                try:
                    user = User.objects.get(id=int(payload.sub_id))
                except (ValueError, User.DoesNotExist):
                    pass
            if user is None:
                logger.warning(
                    f"[{self.platform_name}] No user found for "
                    f"click_id={payload.click_id} sub_id={payload.sub_id!r}"
                )
                cache.delete(dedup_key)  # allow retry after user is linked
                return {"status": "error", "error": "user_not_found"}

            wallet_result = WalletService.get_or_create(user)
            wallet = wallet_result[0] if isinstance(wallet_result, tuple) else wallet_result

            # Convert USD → BDT
            payout_bdt = convert_usd_to_bdt(payload.payout_usd)

            result = EarningService.add_earning(
                wallet=wallet,
                amount=payout_bdt,
                source_type=EarningSourceType.OFFER_WALL,
                source_id=payload.offer_id,
                description=f"{self.platform_name.upper()} conversion",
                country_code=payload.country_code,
                ip_address=payload.ip_address,
                device_type=payload.device_type,
                metadata={
                    "platform":    self.platform_name,
                    "click_id":    payload.click_id,
                    "offer_id":    payload.offer_id,
                    "payout_usd":  str(payload.payout_usd),
                    "sub_id":      payload.sub_id,
                },
                click_id=payload.click_id,
                sub_id=payload.sub_id,
                user_agent=payload.user_agent,
                conversion_status=payload.status,
            )

            logger.info(
                f"[{self.platform_name}] Conversion credited: "
                f"user={user.id} click_id={payload.click_id} "
                f"usd={payload.payout_usd} bdt={payout_bdt}"
            )
            return {
                "status":   "credited",
                "user_id":  user.id,
                "payout_bdt": str(payout_bdt),
                "txn_id":   str(result["txn"].id) if result.get("txn") else None,
            }

        except Exception as exc:
            cache.delete(dedup_key)
            logger.error(
                f"[{self.platform_name}] Conversion processing error: {exc}",
                exc_info=True,
            )
            return {"status": "error", "error": str(exc)}

    # ── Shared HMAC helper ────────────────────────────────────────────

    @staticmethod
    def _hmac_sha256(secret: str, message: str) -> str:
        return hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _md5(value: str) -> str:
        return hashlib.md5(value.encode()).hexdigest()
