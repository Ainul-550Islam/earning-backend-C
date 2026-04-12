"""
MARKETPLACE_SAFETY/review_manipulation.py — Fake Review Detection
"""
from django.db.models import Count, Avg
from django.utils import timezone


def detect_fake_reviews(product) -> dict:
    from api.marketplace.models import ProductReview
    flags = []

    reviews = ProductReview.objects.filter(product=product, is_approved=True)
    if reviews.count() < 3:
        return {"product_id": product.pk, "risk": "low", "flags": []}

    # Sudden review spike
    last_7_days = reviews.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count()
    older       = reviews.filter(created_at__lt=timezone.now() - timezone.timedelta(days=7)).count()
    if last_7_days > older * 3 and last_7_days > 10:
        flags.append({"type": "review_spike", "recent": last_7_days, "older": older})

    # All 5-star with short body
    five_star_short = reviews.filter(rating=5, body__regex=r"^.{0,30}$").count()
    if five_star_short > reviews.count() * 0.7:
        flags.append({"type": "low_quality_5star", "count": five_star_short})

    # Same user reviewing many products of same seller
    seller = product.seller
    if seller:
        suspicious_users = (
            ProductReview.objects.filter(product__seller=seller, rating=5)
            .values("user")
            .annotate(cnt=Count("id"))
            .filter(cnt__gte=5)
        )
        if suspicious_users.exists():
            flags.append({"type": "repeat_5star_reviewer", "user_count": suspicious_users.count()})

    risk = "high" if len(flags) >= 2 else ("medium" if flags else "low")
    return {"product_id": product.pk, "risk": risk, "flags": flags}


def detect_seller_review_farm(tenant) -> list:
    from api.marketplace.models import ProductReview, SellerProfile
    suspicious = []
    for seller in SellerProfile.objects.filter(tenant=tenant, status="active"):
        result = detect_fake_reviews.__wrapped__ if hasattr(detect_fake_reviews, "__wrapped__") else lambda p: {"flags":[]}
        reviews = ProductReview.objects.filter(product__seller=seller)
        if reviews.count() < 5:
            continue
        avg = reviews.aggregate(avg=Avg("rating"))["avg"] or 0
        if avg >= 4.9 and reviews.count() >= 20:
            suspicious.append({
                "seller": seller.store_name,
                "avg_rating": str(round(avg, 2)),
                "review_count": reviews.count(),
                "risk": "high",
            })
    return suspicious
