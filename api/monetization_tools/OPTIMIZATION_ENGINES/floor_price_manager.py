"""OPTIMIZATION_ENGINES/floor_price_manager.py — Dynamic floor price management."""
from decimal import Decimal


class FloorPriceManager:
    """Manages and auto-adjusts floor prices per network/country/format."""

    @staticmethod
    def get_floor(network_id: int, ad_unit_id: int = None,
                   country: str = None, device_type: str = None,
                   ad_format: str = None) -> Decimal:
        from ..DATABASE_MODELS import FloorPriceConfigManager
        from ..models import FloorPriceConfig
        mgr = FloorPriceConfigManager()
        mgr.model = FloorPriceConfig
        return mgr.get_floor(network_id, ad_unit_id, country, device_type, ad_format)

    @staticmethod
    def auto_adjust(network_id: int, days: int = 7) -> Decimal:
        from ..AD_NETWORKS.network_optimizer import NetworkOptimizer
        return NetworkOptimizer.recommend_floor(network_id, days)

    @staticmethod
    def set_floor(network_id: int, ecpm: Decimal, country: str = None,
                   ad_format: str = None, tenant=None) -> object:
        from ..models import FloorPriceConfig
        obj, _ = FloorPriceConfig.objects.update_or_create(
            ad_network_id=network_id,
            country=country or "", ad_format=ad_format or "",
            defaults={"floor_ecpm": ecpm, "is_active": True, "tenant": tenant},
        )
        return obj
