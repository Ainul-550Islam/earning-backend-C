"""
PROMOTION_MARKETING/seasonal_promotion.py — Seasonal & Holiday Promotions
"""
from django.utils import timezone
from api.marketplace.models import PromotionCampaign
from api.marketplace.enums import PromotionType
from api.marketplace.utils import unique_slugify
from decimal import Decimal

BD_HOLIDAYS = {
    "eid_ul_fitr":   "Eid ul-Fitr Sale",
    "eid_ul_adha":   "Eid ul-Adha Sale",
    "pohela_boishakh":"Pohela Boishakh Sale",
    "victory_day":   "Victory Day Sale",
    "independence":  "Independence Day Sale",
    "new_year":      "New Year Sale",
    "mothers_day":   "Mother's Day Sale",
}


def create_seasonal_campaign(tenant, created_by, holiday_key: str,
                              starts_at, ends_at, discount: Decimal = Decimal("15"),
                              product_ids: list = None) -> PromotionCampaign:
    name = BD_HOLIDAYS.get(holiday_key, f"Seasonal Sale {holiday_key}")
    slug = unique_slugify(PromotionCampaign, name)
    campaign = PromotionCampaign.objects.create(
        tenant=tenant, created_by=created_by, name=name, slug=slug,
        promotion_type=PromotionType.SEASONAL,
        discount_value=discount, discount_type="percent",
        starts_at=starts_at, ends_at=ends_at, is_active=True,
    )
    if product_ids:
        from api.marketplace.models import Product
        campaign.products.set(Product.objects.filter(pk__in=product_ids, tenant=tenant))
    return campaign


def get_upcoming_holidays(days_ahead: int = 60) -> list:
    return [
        {"key": k, "name": v, "discount_suggested": "15%"}
        for k, v in BD_HOLIDAYS.items()
    ]
