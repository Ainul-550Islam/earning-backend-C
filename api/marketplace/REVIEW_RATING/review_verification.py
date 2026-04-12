"""
REVIEW_RATING/review_verification.py — Verified Purchase Review System
"""
from api.marketplace.models import ProductReview, OrderItem
from django.utils import timezone


def mark_verified_purchase(review: ProductReview) -> bool:
    """Check if reviewer actually purchased this product and mark accordingly."""
    purchased = OrderItem.objects.filter(
        order__user=review.user,
        variant__product=review.product,
        item_status="delivered",
    ).exists()
    if purchased != review.is_verified_purchase:
        review.is_verified_purchase = purchased
        review.save(update_fields=["is_verified_purchase"])
    return purchased


def verify_all_reviews(tenant) -> dict:
    """Batch verify all reviews for a tenant. Run as Celery task."""
    reviews = ProductReview.objects.filter(
        product__tenant=tenant, is_approved=True
    ).select_related("user","product")
    updated = 0
    for review in reviews:
        old = review.is_verified_purchase
        new = mark_verified_purchase(review)
        if old != new:
            updated += 1
    return {"total_checked": reviews.count(), "updated": updated}


def can_user_review(user, product) -> dict:
    """Check if user is eligible to write a review."""
    from api.marketplace.constants import REVIEW_WINDOW_DAYS
    from datetime import timedelta

    # Already reviewed?
    if ProductReview.objects.filter(user=user, product=product).exists():
        return {"can_review": False, "reason": "Already reviewed this product"}

    # Purchased?
    delivery = OrderItem.objects.filter(
        order__user=user,
        variant__product=product,
        item_status="delivered",
    ).order_by("-created_at").first()

    if not delivery:
        return {"can_review": False, "reason": "Purchase required to review"}

    # Within review window?
    days_since = (timezone.now() - delivery.created_at).days
    if days_since > REVIEW_WINDOW_DAYS:
        return {"can_review": False, "reason": f"Review window expired ({REVIEW_WINDOW_DAYS} days)"}

    return {"can_review": True, "order_item_id": delivery.pk}
