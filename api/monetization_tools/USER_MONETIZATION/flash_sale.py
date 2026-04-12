"""USER_MONETIZATION/flash_sale.py — Flash sale user-facing management."""
from ..services import FlashSaleService


class FlashSaleManager:
    @classmethod
    def live(cls, tenant=None) -> list:
        return list(FlashSaleService.get_live(tenant).values(
            "id", "name", "sale_type", "multiplier", "bonus_coins",
            "discount_pct", "starts_at", "ends_at",
        ))

    @classmethod
    def best_multiplier(cls, tenant=None, offer_type: str = "") -> object:
        return FlashSaleService.get_best_multiplier(tenant, offer_type)

    @classmethod
    def is_any_active(cls, tenant=None) -> bool:
        return FlashSaleService.get_live(tenant).exists()
