# services/offerwall/registry.py
"""
OfferwallRegistry — platform aggregator.
"এক কাজের জন্য একটাই মালিক।"
The registry owns:
  • Platform lookup by name
  • Multi-platform offer aggregation & ranking
  • Postback routing by platform slug
  • Offer category/vertical filtering
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("wallet.offerwall.registry")


class OfferwallRegistry:
    """
    Single entry point for all offerwall platform operations.
    Each platform is owned by its adapter; this class owns aggregation.
    """

    _adapters = {}   # lazy-loaded

    @classmethod
    def _get_adapters(cls) -> dict:
        if not cls._adapters:
            from .ogads      import OGAdsAdapter
            from .adgate     import AdGateAdapter
            from .offertoro  import OffertoroAdapter
            from .monlix     import MonlixAdapter
            from ..cpalead.CPALeadService import CPALeadService as _CPA

            cls._adapters = {
                "ogads":     OGAdsAdapter(),
                "adgate":    AdGateAdapter(),
                "offertoro": OffertoroAdapter(),
                "monlix":    MonlixAdapter(),
                # CPALead uses its own service, exposed as a thin adapter shim
                "cpalead":   _CPALeadShim(),
            }
        return cls._adapters

    @classmethod
    def get_adapter(cls, platform: str):
        """Return the adapter for `platform`. Raises KeyError if unknown."""
        adapters = cls._get_adapters()
        if platform not in adapters:
            raise KeyError(f"Unknown offerwall platform: {platform!r}. "
                           f"Known: {list(adapters.keys())}")
        return adapters[platform]

    @classmethod
    def route_postback(cls, platform: str, request_data: dict, signature: str = "") -> dict:
        """
        Route an inbound S2S postback to the correct platform adapter.
        Returns result dict from process_conversion.
        """
        try:
            adapter = cls.get_adapter(platform)
        except KeyError as exc:
            logger.warning(f"[registry] Unknown postback platform: {platform}")
            return {"status": "error", "error": str(exc)}

        if not adapter.verify_postback(request_data, signature):
            logger.warning(
                f"[registry] Invalid signature from {platform}: {request_data}"
            )
            return {"status": "error", "error": "invalid_signature"}

        payload = adapter.parse_postback(request_data)
        return adapter.process_conversion(payload)

    @classmethod
    def get_all_offers(
        cls,
        country_code: str = "BD",
        device_type: str = "desktop",
        platforms: Optional[list] = None,
        vertical: str = "",
        min_payout_usd: float = 0.0,
        limit_per_platform: int = 30,
        sort_by: str = "payout",   # payout | platform
    ) -> list:
        """
        Aggregate offers from all (or selected) platforms.
        Returns sorted, deduplicated list of OfferwallOffer objects.
        """
        adapters = cls._get_adapters()
        active   = platforms or list(adapters.keys())
        results  = []
        seen_ids = set()

        for name in active:
            adapter = adapters.get(name)
            if not adapter:
                continue
            try:
                offers = adapter.fetch_offers(
                    country_code=country_code,
                    device_type=device_type,
                    limit=limit_per_platform,
                )
                for o in offers:
                    dedup_key = f"{name}:{o.offer_id}"
                    if dedup_key in seen_ids:
                        continue
                    seen_ids.add(dedup_key)

                    if vertical and o.vertical and o.vertical != vertical:
                        continue
                    if o.payout_usd < Decimal(str(min_payout_usd)):
                        continue
                    results.append(o)

            except Exception as exc:
                logger.warning(f"[registry] {name} fetch_offers failed: {exc}")
                continue

        if sort_by == "payout":
            results.sort(key=lambda o: o.payout_usd, reverse=True)

        return results

    @classmethod
    def get_smartwall_urls(cls, user_id: int, sub_id: str = "") -> dict:
        """Return {platform: smartwall_url} for all configured platforms."""
        adapters = cls._get_adapters()
        urls = {}
        for name, adapter in adapters.items():
            try:
                url = adapter.get_smartwall_url(user_id, sub_id)
                if url:
                    urls[name] = url
            except Exception:
                pass
        return urls

    @classmethod
    def get_offers_by_vertical(
        cls,
        vertical: str,
        country_code: str = "BD",
        device_type: str = "desktop",
    ) -> list:
        """Get offers filtered by vertical (gaming/finance/health/dating/utilities)."""
        return cls.get_all_offers(
            country_code=country_code,
            device_type=device_type,
            vertical=vertical,
        )

    @classmethod
    def get_video_offers(
        cls,
        country_code: str = "BD",
        device_type: str = "desktop",
    ) -> list:
        """Get only video/watch-to-earn offers across all platforms."""
        all_offers = cls.get_all_offers(country_code=country_code, device_type=device_type)
        return [o for o in all_offers if o.offer_type == "video"]

    @classmethod
    def get_cpl_offers(cls, country_code: str = "US") -> list:
        """Get CPL (lead submit) offers — mainly from Monlix."""
        all_offers = cls.get_all_offers(country_code=country_code)
        return [o for o in all_offers if o.offer_type == "cpl"]


class _CPALeadShim:
    """
    Thin shim to expose CPALeadService via the adapter interface.
    CPAlead has its own service; this shim delegates to it so the
    registry can treat it uniformly.
    """
    platform_name = "cpalead"

    def verify_postback(self, request_data: dict, signature: str = "") -> bool:
        return True  # CPALead verifies internally

    def parse_postback(self, request_data: dict):
        from .base import ConversionPayload
        return ConversionPayload(
            platform     = "cpalead",
            click_id     = str(request_data.get("click_id", "")),
            offer_id     = str(request_data.get("offer_id", "")),
            payout_usd   = Decimal(str(request_data.get("payout", "0") or "0")),
            user_id      = None,
            sub_id       = str(request_data.get("sub1", "")),
            country_code = str(request_data.get("country", "")),
            raw          = dict(request_data),
        )

    def process_conversion(self, payload) -> dict:
        try:
            from ..cpalead.CPALeadService import CPALeadService
            return CPALeadService.record_conversion(
                click_id     = payload.click_id,
                offer_id     = payload.offer_id,
                payout       = payload.payout_usd,
                sub_id       = payload.sub_id,
                country_code = payload.country_code,
            )
        except Exception as exc:
            logger.error(f"[cpalead shim] process_conversion error: {exc}")
            return {"status": "error", "error": str(exc)}

    def fetch_offers(self, country_code="BD", device_type="desktop", limit=50) -> list:
        return []

    def get_smartwall_url(self, user_id: int, sub_id: str = "") -> str:
        return ""
