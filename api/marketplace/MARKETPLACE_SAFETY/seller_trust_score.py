"""MARKETPLACE_SAFETY/seller_trust_score.py — Seller trust scoring"""
from decimal import Decimal
from api.marketplace.models import SellerProfile


def calculate_trust_score(seller: SellerProfile) -> Decimal:
    """
    0–100 trust score based on:
    - Verification status (40 pts)
    - Average rating (30 pts)
    - Response rate (20 pts)
    - Account age (10 pts)
    """
    score = Decimal("0")
    if seller.status == "active":
        score += 40
    score += (seller.average_rating / 5) * 30
    score += (seller.response_rate / 100) * 20
    from django.utils import timezone
    age_days = (timezone.now().date() - seller.created_at.date()).days
    age_score = min(10, age_days / 36)
    score += Decimal(str(age_score))
    return score.quantize(Decimal("0.1"))
