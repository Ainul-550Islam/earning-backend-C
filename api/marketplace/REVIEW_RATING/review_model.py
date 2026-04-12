"""
REVIEW_RATING/review_model.py — Review Domain Models & Core Logic
"""
from api.marketplace.models import ProductReview
from api.marketplace.REVIEW_RATING.product_rating_aggregator import (
    recalculate_product_rating, rating_distribution, get_top_rated
)
from api.marketplace.REVIEW_RATING.seller_rating_aggregator import (
    recalculate_seller_rating, seller_rating_breakdown, get_top_rated_sellers
)
from api.marketplace.REVIEW_RATING.review_verification import (
    can_user_review, mark_verified_purchase, verify_all_reviews
)
from api.marketplace.REVIEW_RATING.review_moderation import (
    auto_moderate, get_flagged_reviews, bulk_approve, bulk_reject
)
from api.marketplace.REVIEW_RATING.review_helpfulness import (
    vote_helpful, get_most_helpful
)
from api.marketplace.REVIEW_RATING.rating_calculator import (
    weighted_average, bayesian_average, trust_score, calculate_nps, rating_trend
)


def get_review_with_all_data(review_id: int) -> dict:
    """Get a complete review object with all related data."""
    try:
        review = ProductReview.objects.select_related(
            "product","user","order_item"
        ).prefetch_related("review_images","helpful_votes").get(pk=review_id)
        return {
            "id":               review.pk,
            "product_name":     review.product.name,
            "reviewer":         review.user.username,
            "rating":           review.rating,
            "title":            review.title,
            "body":             review.body,
            "is_verified":      review.is_verified_purchase,
            "is_approved":      review.is_approved,
            "helpful_count":    review.helpful_count,
            "not_helpful_count":review.not_helpful_count,
            "seller_reply":     review.seller_reply,
            "created_at":       review.created_at.strftime("%Y-%m-%d"),
        }
    except ProductReview.DoesNotExist:
        return {}


def review_analytics_for_product(product) -> dict:
    """Complete review analytics dashboard for a product."""
    dist = rating_distribution(product)
    bayes = bayesian_average(
        sum(i * dist["dist"].get(i,0) for i in range(1,6)),
        dist["total"],
    )
    return {
        "average":        dist["average"],
        "total":          dist["total"],
        "distribution":   dist["dist"],
        "percentages":    dist["pct"],
        "bayesian_score": bayes,
        "trust_score":    trust_score(dist["total"], float(dist["average"])),
    }


__all__ = [
    "ProductReview",
    "recalculate_product_rating","rating_distribution","get_top_rated",
    "recalculate_seller_rating","seller_rating_breakdown","get_top_rated_sellers",
    "can_user_review","mark_verified_purchase","verify_all_reviews",
    "auto_moderate","get_flagged_reviews","bulk_approve","bulk_reject",
    "vote_helpful","get_most_helpful",
    "weighted_average","bayesian_average","trust_score","calculate_nps","rating_trend",
    "get_review_with_all_data","review_analytics_for_product",
]
