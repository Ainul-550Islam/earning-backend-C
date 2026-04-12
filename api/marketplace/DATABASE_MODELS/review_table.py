"""
DATABASE_MODELS/review_table.py — Review & Rating Table Reference
"""
from api.marketplace.models import ProductReview
from django.db.models import Avg, Count


def pending_moderation(tenant) -> list:
    return list(ProductReview.objects.filter(
        product__tenant=tenant, is_approved=False
    ).select_related("product","user").order_by("-created_at"))


def review_stats(tenant) -> dict:
    qs = ProductReview.objects.filter(product__tenant=tenant)
    agg = qs.aggregate(avg=Avg("rating"), total=Count("id"))
    return {
        "total":     agg["total"] or 0,
        "approved":  qs.filter(is_approved=True).count(),
        "pending":   qs.filter(is_approved=False).count(),
        "avg_rating":str(round(agg["avg"] or 0, 2)),
        "verified":  qs.filter(is_verified_purchase=True).count(),
    }


__all__ = ["ProductReview","pending_moderation","review_stats"]
