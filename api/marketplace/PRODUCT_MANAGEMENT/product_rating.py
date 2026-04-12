"""
PRODUCT_MANAGEMENT/product_rating.py — Rating aggregation
"""
from django.db.models import Avg, Count
from api.marketplace.models import Product, ProductReview


def recalculate_rating(product: Product):
    agg = ProductReview.objects.filter(
        product=product, is_approved=True
    ).aggregate(avg=Avg("rating"), count=Count("id"))
    Product.objects.filter(pk=product.pk).update(
        average_rating=round(agg["avg"] or 0, 2),
        review_count=agg["count"] or 0,
    )


def rating_distribution(product: Product) -> dict:
    dist = {i: 0 for i in range(1, 6)}
    reviews = ProductReview.objects.filter(product=product, is_approved=True)
    for r in reviews.values("rating"):
        dist[r["rating"]] += 1
    return dist
