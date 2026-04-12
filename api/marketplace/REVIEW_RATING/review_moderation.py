"""
REVIEW_RATING/review_moderation.py — AI-assisted Review Moderation
"""
import logging
from django.db.models import Q
from api.marketplace.models import ProductReview

logger = logging.getLogger(__name__)

BANNED_WORDS = [
    "scam","fraud","fake","spam","cheat","stolen","worst","terrible",
    "never buy","waste of money","rubbish","garbage","useless","broken on arrival",
]
MIN_BODY_LENGTH = 10
MAX_BODY_LENGTH = 2000


def auto_moderate(review: ProductReview) -> dict:
    """
    Auto-approve or flag a review.
    Returns {"approved": bool, "flags": list, "action": str}
    """
    flags = []

    # Length checks
    if len(review.body) < MIN_BODY_LENGTH:
        flags.append("too_short")
    if len(review.body) > MAX_BODY_LENGTH:
        flags.append("too_long")

    # Spam detection
    body_lower = review.body.lower()
    spam_words = [w for w in BANNED_WORDS if w in body_lower]
    if spam_words:
        flags.append(f"contains_flagged_words:{','.join(spam_words)}")

    # Duplicate review check
    similar = ProductReview.objects.filter(
        product=review.product,
        body__icontains=review.body[:50],
    ).exclude(pk=review.pk).exists()
    if similar:
        flags.append("possible_duplicate")

    # Rating vs content sentiment mismatch (simple heuristic)
    if review.rating >= 4 and any(w in body_lower for w in ["bad","poor","awful","terrible"]):
        flags.append("rating_content_mismatch")
    if review.rating <= 2 and any(w in body_lower for w in ["great","excellent","perfect","love"]):
        flags.append("rating_content_mismatch")

    approved = len(flags) == 0
    if not approved:
        review.is_approved = False
        review.save(update_fields=["is_approved"])

    logger.info("[ReviewMod] Review#%s: approved=%s flags=%s", review.pk, approved, flags)
    return {"approved": approved, "flags": flags, "action": "auto_approved" if approved else "flagged"}


def get_flagged_reviews(tenant) -> list:
    return list(
        ProductReview.objects.filter(
            product__tenant=tenant, is_approved=False
        ).select_related("product","user").order_by("-created_at")
    )


def bulk_approve(review_ids: list):
    ProductReview.objects.filter(pk__in=review_ids).update(is_approved=True)


def bulk_reject(review_ids: list):
    ProductReview.objects.filter(pk__in=review_ids).delete()
