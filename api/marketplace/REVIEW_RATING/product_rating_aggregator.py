"""
REVIEW_RATING/product_rating_aggregator.py — Product Rating Aggregation
"""
from django.db.models import Avg, Count
from api.marketplace.models import ProductReview, Product


def recalculate_product_rating(product: Product) -> dict:
    reviews = ProductReview.objects.filter(product=product, is_approved=True)
    agg = reviews.aggregate(avg=Avg("rating"), total=Count("id"))
    avg   = round(agg["avg"] or 0, 2)
    total = agg["total"] or 0
    Product.objects.filter(pk=product.pk).update(average_rating=avg, review_count=total)
    return {"average_rating": avg, "review_count": total}


def rating_distribution(product: Product) -> dict:
    reviews = ProductReview.objects.filter(product=product, is_approved=True)
    dist  = {i: reviews.filter(rating=i).count() for i in range(1, 6)}
    total = sum(dist.values())
    return {
        "average":  str(product.average_rating),
        "total":    product.review_count,
        "dist":     dist,
        "pct":      {str(k): round(v/total*100,1) if total else 0 for k,v in dist.items()},
    }


def batch_recalculate(tenant) -> int:
    """Recalculate all product ratings for a tenant. Used as Celery task."""
    updated = 0
    for product in Product.objects.filter(tenant=tenant).iterator(chunk_size=200):
        recalculate_product_rating(product)
        updated += 1
    return updated


def get_top_rated(tenant, category=None, limit: int = 12) -> list:
    qs = Product.objects.filter(tenant=tenant, status="active", review_count__gte=3)
    if category:
        qs = qs.filter(category=category)
    return list(qs.order_by("-average_rating","-review_count")[:limit])
