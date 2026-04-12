"""
REVIEW_RATING/seller_rating_aggregator.py — Seller Rating Aggregation
"""
from django.db.models import Avg, Count
from api.marketplace.models import ProductReview, SellerProfile


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
    dist = {i: reviews.filter(rating=i).count() for i in range(1, 6)}
    total = sum(dist.values())
    return {
        "average":       str(seller.average_rating),
        "total_reviews": seller.total_reviews,
        "distribution":  dist,
        "percentages": {
            str(k): round(v / total * 100, 1) if total else 0
            for k, v in dist.items()
        },
    }


def get_top_rated_sellers(tenant, limit: int = 10) -> list:
    return list(
        SellerProfile.objects.filter(tenant=tenant, status="active", total_reviews__gte=5)
        .order_by("-average_rating","-total_reviews")[:limit]
        .values("store_name","store_slug","average_rating","total_reviews","total_sales")
    )
