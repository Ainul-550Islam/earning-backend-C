"""
REVIEW_RATING/review_helpfulness.py — Review Helpfulness Voting
"""
from django.db import models, transaction
from django.conf import settings
from api.marketplace.models import ProductReview


class ReviewHelpfulVote(models.Model):
    review     = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="helpful_votes")
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_review_helpful_vote"
        unique_together = [("review","user")]


@transaction.atomic
def vote_helpful(review_id: int, user, is_helpful: bool) -> dict:
    try:
        review = ProductReview.objects.get(pk=review_id)
    except ProductReview.DoesNotExist:
        return {"success": False, "error": "Review not found"}

    if review.user == user:
        return {"success": False, "error": "Cannot vote on your own review"}

    vote, created = ReviewHelpfulVote.objects.update_or_create(
        review=review, user=user,
        defaults={"is_helpful": is_helpful},
    )

    # Recalculate counts
    helpful     = ReviewHelpfulVote.objects.filter(review=review, is_helpful=True).count()
    not_helpful = ReviewHelpfulVote.objects.filter(review=review, is_helpful=False).count()
    ProductReview.objects.filter(pk=review_id).update(
        helpful_count=helpful, not_helpful_count=not_helpful
    )
    return {"success": True, "helpful": helpful, "not_helpful": not_helpful}


def get_most_helpful(product, limit: int = 5) -> list:
    return list(
        ProductReview.objects.filter(product=product, is_approved=True)
        .order_by("-helpful_count", "-created_at")[:limit]
    )
