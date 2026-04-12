"""
SELLER_MANAGEMENT/seller_performance.py — Seller Performance Metrics & Scoring
"""
from decimal import Decimal
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from api.marketplace.models import OrderItem, SellerProfile, ProductReview, Order
from api.marketplace.enums import OrderStatus


def get_performance_metrics(seller: SellerProfile, days: int = 30) -> dict:
    since = timezone.now() - timezone.timedelta(days=days)
    items = OrderItem.objects.filter(seller=seller, created_at__gte=since)
    agg   = items.aggregate(
        revenue=Sum("seller_net"),
        orders=Count("order",distinct=True),
        units=Sum("quantity"),
        avg_order_value=Avg("subtotal"),
    )
    return {
        "period_days":     days,
        "total_orders":    agg["orders"] or 0,
        "total_items_sold":agg["units"] or 0,
        "total_revenue":   str(agg["revenue"] or 0),
        "avg_order_value": str(round(agg["avg_order_value"] or 0, 2)),
    }


def seller_scorecard(seller: SellerProfile) -> dict:
    """
    Comprehensive seller performance score (0-100).
    Used for seller tier badges and priority support.
    """
    score = 0
    breakdown = {}

    # Rating score (0-30 pts)
    if seller.average_rating >= 4.5:
        rating_score = 30
    elif seller.average_rating >= 4.0:
        rating_score = 22
    elif seller.average_rating >= 3.5:
        rating_score = 15
    else:
        rating_score = 5
    score += rating_score
    breakdown["rating"] = rating_score

    # Sales volume (0-25 pts)
    sales_score = min(25, seller.total_sales // 20)
    score += sales_score
    breakdown["sales_volume"] = sales_score

    # KYC verified (0-20 pts)
    kyc_score = 0
    try:
        if seller.verification.status == "verified":
            kyc_score = 20
        elif seller.verification.status == "pending":
            kyc_score = 5
    except Exception:
        pass
    score += kyc_score
    breakdown["kyc"] = kyc_score

    # Response rate (0-15 pts)
    response_score = int(seller.response_rate / 100 * 15)
    score += response_score
    breakdown["response_rate"] = response_score

    # Fulfilment rate — orders delivered on time (0-10 pts)
    total_orders = OrderItem.objects.filter(seller=seller).values("order").distinct().count()
    delivered = Order.objects.filter(
        items__seller=seller, status=OrderStatus.DELIVERED
    ).count()
    fulfilment_rate = delivered / total_orders * 100 if total_orders else 0
    fulfilment_score = int(fulfilment_rate / 100 * 10)
    score += fulfilment_score
    breakdown["fulfilment"] = fulfilment_score

    # Badge tier
    if score >= 85:
        badge = "platinum"
    elif score >= 70:
        badge = "gold"
    elif score >= 50:
        badge = "silver"
    else:
        badge = "bronze"

    return {
        "total_score":    score,
        "badge":          badge,
        "breakdown":      breakdown,
        "rating":         str(seller.average_rating),
        "total_reviews":  seller.total_reviews,
        "total_sales":    seller.total_sales,
        "response_rate":  str(seller.response_rate),
        "fulfilment_rate":round(fulfilment_rate, 1),
    }


def get_improvement_tips(seller: SellerProfile) -> list:
    """Generate actionable tips based on seller performance."""
    tips = []
    scorecard = seller_scorecard(seller)

    if seller.average_rating < 4.0:
        tips.append("Improve product quality and accurate descriptions to boost ratings")
    if seller.response_rate < 80:
        tips.append("Reply to customer disputes and questions faster to improve response rate")
    if scorecard["breakdown"].get("kyc", 0) < 20:
        tips.append("Complete KYC verification to unlock higher payouts and trust badge")
    if seller.total_reviews < 10:
        tips.append("Encourage customers to leave reviews after purchase")

    unanswered = ProductReview.objects.filter(product__seller=seller, seller_reply="", is_approved=True).count()
    if unanswered > 0:
        tips.append(f"Reply to {unanswered} unanswered review(s) to improve engagement")

    if not tips:
        tips.append("Great job! Keep maintaining high performance standards.")
    return tips
