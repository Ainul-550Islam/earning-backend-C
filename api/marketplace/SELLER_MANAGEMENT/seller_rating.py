"""
SELLER_MANAGEMENT/seller_rating.py — Seller Rating System
"""
from decimal import Decimal
from django.db.models import Avg, Count
from api.marketplace.models import SellerProfile, ProductReview


def recalculate_seller_rating(seller: SellerProfile) -> dict:
    reviews = ProductReview.objects.filter(product__seller=seller, is_approved=True)
    agg = reviews.aggregate(avg=Avg("rating"), total=Count("id"))
    avg   = round(agg["avg"] or 0, 2)
    total = agg["total"] or 0
    SellerProfile.objects.filter(pk=seller.pk).update(
        average_rating=avg, total_reviews=total
    )
    return {"average_rating": avg, "total_reviews": total}


def seller_rating_breakdown(seller: SellerProfile) -> dict:
    reviews = ProductReview.objects.filter(product__seller=seller, is_approved=True)
    distribution = {i: reviews.filter(rating=i).count() for i in range(1, 6)}
    total = sum(distribution.values())
    return {
        "average":       str(seller.average_rating),
        "total_reviews": total,
        "distribution":  distribution,
        "percentages":   {str(k): round(v/total*100,1) if total else 0 for k,v in distribution.items()},
        "trustworthy":   seller.average_rating >= 4.0 and total >= 10,
    }


def get_top_rated_sellers(tenant, limit: int = 10, min_reviews: int = 5) -> list:
    return list(
        SellerProfile.objects.filter(
            tenant=tenant, status="active", total_reviews__gte=min_reviews
        ).order_by("-average_rating","-total_sales")
        .values("store_name","store_slug","average_rating","total_reviews","total_sales","city")
        [:limit]
    )


def get_seller_nps(seller: SellerProfile) -> float:
    """Net Promoter Score based on reviews."""
    reviews = ProductReview.objects.filter(product__seller=seller, is_approved=True)
    total   = reviews.count()
    if total == 0:
        return 0.0
    promoters  = reviews.filter(rating__gte=5).count()   # 5 stars
    detractors = reviews.filter(rating__lte=2).count()   # 1-2 stars
    return round((promoters - detractors) / total * 100, 1)


def bulk_recalculate(tenant) -> int:
    """Recalculate ratings for all active sellers. Use as Celery task."""
    updated = 0
    for seller in SellerProfile.objects.filter(tenant=tenant, status="active").iterator(chunk_size=100):
        recalculate_seller_rating(seller)
        updated += 1
    return updated
