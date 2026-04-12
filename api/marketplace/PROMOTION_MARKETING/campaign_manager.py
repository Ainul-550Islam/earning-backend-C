"""
PROMOTION_MARKETING/campaign_manager.py — Marketing Campaign Manager
=====================================================================
Central orchestrator for all promotional campaigns.
Manages lifecycle: draft → scheduled → live → ended → archived
"""
from __future__ import annotations
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from api.marketplace.models import PromotionCampaign, Product, Category
from api.marketplace.enums import PromotionType

logger = logging.getLogger(__name__)


class CampaignManager:

    # ── CRUD ──────────────────────────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def create_campaign(cls, tenant, created_by, name: str, promotion_type: str,
                        discount_value: Decimal, discount_type: str,
                        starts_at, ends_at, product_ids: list = None,
                        category_ids: list = None, **kwargs) -> PromotionCampaign:
        from api.marketplace.utils import unique_slugify
        slug = unique_slugify(PromotionCampaign, name)
        campaign = PromotionCampaign.objects.create(
            tenant=tenant, created_by=created_by, name=name, slug=slug,
            promotion_type=promotion_type, discount_value=discount_value,
            discount_type=discount_type, starts_at=starts_at, ends_at=ends_at,
            is_active=True, **kwargs
        )
        if product_ids:
            campaign.products.set(Product.objects.filter(pk__in=product_ids, tenant=tenant))
        if category_ids:
            campaign.categories.set(Category.objects.filter(pk__in=category_ids, tenant=tenant))
        logger.info("[Campaign] Created: %s (%s)", name, promotion_type)
        return campaign

    @classmethod
    def get_live(cls, tenant) -> list:
        now = timezone.now()
        return list(PromotionCampaign.objects.filter(
            tenant=tenant, is_active=True,
            starts_at__lte=now, ends_at__gte=now,
        ).prefetch_related("products", "categories"))

    @classmethod
    def get_upcoming(cls, tenant, days: int = 7) -> list:
        now = timezone.now()
        future = now + timezone.timedelta(days=days)
        return list(PromotionCampaign.objects.filter(
            tenant=tenant, is_active=True,
            starts_at__gt=now, starts_at__lte=future,
        ))

    @classmethod
    def deactivate_ended(cls, tenant) -> int:
        count = PromotionCampaign.objects.filter(
            tenant=tenant, is_active=True, ends_at__lt=timezone.now()
        ).update(is_active=False)
        if count:
            logger.info("[Campaign] Deactivated %s ended campaigns", count)
        return count

    # ── Discount calculation ──────────────────────────────────────────────────
    @classmethod
    def apply_campaign_to_product(cls, product: Product, price: Decimal) -> dict:
        now = timezone.now()
        campaign = PromotionCampaign.objects.filter(
            tenant=product.tenant, is_active=True,
            starts_at__lte=now, ends_at__gte=now,
            products=product,
        ).first() or PromotionCampaign.objects.filter(
            tenant=product.tenant, is_active=True,
            starts_at__lte=now, ends_at__gte=now,
            categories=product.category,
        ).first()

        if not campaign:
            return {"discounted_price": price, "discount_amount": Decimal("0"), "campaign": None}

        if campaign.discount_type == "percent":
            discount = price * campaign.discount_value / 100
        else:
            discount = campaign.discount_value

        discount = min(discount, price)
        return {
            "discounted_price": (price - discount).quantize(Decimal("0.01")),
            "discount_amount":  discount.quantize(Decimal("0.01")),
            "campaign":         campaign.name,
        }

    # ── Performance analytics ─────────────────────────────────────────────────
    @classmethod
    def campaign_performance(cls, campaign: PromotionCampaign) -> dict:
        from api.marketplace.models import Order, OrderItem
        from api.marketplace.enums import OrderStatus
        from django.db.models import Sum, Count
        product_ids = list(campaign.products.values_list("pk", flat=True))
        items = OrderItem.objects.filter(
            variant__product_id__in=product_ids,
            order__created_at__range=[campaign.starts_at, campaign.ends_at],
        )
        agg = items.aggregate(revenue=Sum("subtotal"), orders=Count("order", distinct=True))
        return {
            "campaign":       campaign.name,
            "status":         "live" if campaign.is_live else "ended",
            "total_revenue":  str(agg["revenue"] or 0),
            "total_orders":   agg["orders"] or 0,
            "products_count": campaign.products.count(),
        }
