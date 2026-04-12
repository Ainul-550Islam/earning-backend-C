"""
PRODUCT_MANAGEMENT/product_review.py — Product Review Business Logic
"""
from django.utils import timezone
from api.marketplace.models import ProductReview, Product
from api.marketplace.constants import REVIEW_WINDOW_DAYS


def get_product_reviews(product: Product, approved_only: bool = True,
                         sort_by: str = "newest", limit: int = None):
    qs = ProductReview.objects.filter(product=product)
    if approved_only:
        qs = qs.filter(is_approved=True)

    order_map = {
        "newest":     "-created_at",
        "oldest":     "created_at",
        "highest":    "-rating",
        "lowest":     "rating",
        "helpful":    "-helpful_count",
        "verified":   "-is_verified_purchase",
    }
    qs = qs.order_by(order_map.get(sort_by, "-created_at")).select_related("user")
    return qs[:limit] if limit else qs


def create_review(product: Product, user, order_item, rating: int, title: str,
                  body: str, images: list = None) -> dict:
    """Create a product review with eligibility check."""
    from api.marketplace.REVIEW_RATING.review_verification import can_user_review
    check = can_user_review(user, product)
    if not check["can_review"]:
        return {"success": False, "error": check["reason"]}

    from api.marketplace.REVIEW_RATING.review_moderation import auto_moderate
    review = ProductReview.objects.create(
        tenant=product.tenant, product=product, order_item=order_item,
        user=user, rating=rating, title=title, body=body,
        images=images or [], is_verified_purchase=True,
    )
    moderation = auto_moderate(review)

    # Update product rating
    from api.marketplace.REVIEW_RATING.product_rating_aggregator import recalculate_product_rating
    recalculate_product_rating(product)

    return {
        "success":   True,
        "review_id": review.pk,
        "approved":  moderation["approved"],
        "flags":     moderation["flags"],
    }


def moderate_review(review_id: int, approve: bool, moderator=None) -> dict:
    try:
        review = ProductReview.objects.get(pk=review_id)
        review.is_approved = approve
        review.save(update_fields=["is_approved"])
        if approve:
            from api.marketplace.REVIEW_RATING.product_rating_aggregator import recalculate_product_rating
            recalculate_product_rating(review.product)
        return {"success": True, "approved": approve}
    except ProductReview.DoesNotExist:
        return {"success": False, "error": "Review not found"}


def get_review_summary(product: Product) -> dict:
    from api.marketplace.REVIEW_RATING.product_rating_aggregator import rating_distribution
    return rating_distribution(product)


def get_featured_reviews(product: Product, limit: int = 3) -> list:
    """Get most helpful verified reviews."""
    return list(
        ProductReview.objects.filter(
            product=product, is_approved=True, is_verified_purchase=True
        ).order_by("-helpful_count","-rating")[:limit]
    )
