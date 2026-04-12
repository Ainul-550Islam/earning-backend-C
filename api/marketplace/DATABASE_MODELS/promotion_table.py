"""
DATABASE_MODELS/promotion_table.py — Promotion & Campaign Table Reference
"""
from api.marketplace.models import PromotionCampaign
from api.marketplace.enums import PromotionType
from django.utils import timezone


def live_campaigns(tenant) -> list:
    now = timezone.now()
    return list(PromotionCampaign.objects.filter(
        tenant=tenant, is_active=True, starts_at__lte=now, ends_at__gte=now
    ).prefetch_related("products","categories"))


def campaign_calendar(tenant, days: int = 30) -> list:
    from datetime import timedelta
    until = timezone.now() + timedelta(days=days)
    return list(PromotionCampaign.objects.filter(
        tenant=tenant, starts_at__lte=until
    ).values("name","promotion_type","starts_at","ends_at","is_active").order_by("starts_at"))


__all__ = ["PromotionCampaign","PromotionType","live_campaigns","campaign_calendar"]
