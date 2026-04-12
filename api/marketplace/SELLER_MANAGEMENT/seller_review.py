"""
SELLER_MANAGEMENT/seller_review.py — Seller Review Management
"""
from django.db.models import Avg, Count
from api.marketplace.models import ProductReview, SellerProfile


def seller_reviews(seller: SellerProfile, approved_only: bool = True, limit: int = None):
    qs = ProductReview.objects.filter(product__seller=seller).select_related("product","user")
    if approved_only:
        qs = qs.filter(is_approved=True)
    qs = qs.order_by("-created_at")
    return qs[:limit] if limit else qs


def unanswered_reviews(seller: SellerProfile) -> list:
    """Reviews that haven't received a seller reply."""
    return list(
        ProductReview.objects.filter(
            product__seller=seller, is_approved=True, seller_reply=""
        ).select_related("product","user").order_by("-created_at")
    )


def reply_to_review(review_id: int, seller: SellerProfile, reply_text: str) -> dict:
    """Seller replies to a product review."""
    from django.utils import timezone
    try:
        review = ProductReview.objects.get(pk=review_id, product__seller=seller)
        if review.seller_reply:
            return {"success": False, "error": "Already replied to this review"}
        review.seller_reply     = reply_text
        review.seller_replied_at= timezone.now()
        review.save(update_fields=["seller_reply","seller_replied_at"])
        return {"success": True, "review_id": review_id}
    except ProductReview.DoesNotExist:
        return {"success": False, "error": "Review not found"}


def seller_review_stats(seller: SellerProfile) -> dict:
    reviews = ProductReview.objects.filter(product__seller=seller, is_approved=True)
    total   = reviews.count()
    replied = reviews.exclude(seller_reply="").count()
    return {
        "total_reviews":  total,
        "replied":        replied,
        "unanswered":     total - replied,
        "reply_rate":     round(replied / total * 100, 1) if total else 0,
        "avg_rating":     str(round(reviews.aggregate(avg=Avg("rating"))["avg"] or 0, 2)),
        "verified_purchase_count": reviews.filter(is_verified_purchase=True).count(),
    }


def flag_review_for_removal(review_id: int, seller: SellerProfile, reason: str) -> dict:
    """Seller flags a suspicious review for admin moderation."""
    try:
        review = ProductReview.objects.get(pk=review_id, product__seller=seller)
        from api.marketplace.REVIEW_RATING.review_report import report_review
        return report_review(review_id, seller.user, "fake", reason, seller.tenant)
    except ProductReview.DoesNotExist:
        return {"success": False, "error": "Review not found"}
