"""
REVIEW_RATING/rating_calculator.py — Rating Statistics & Scoring
"""
from decimal import Decimal
from typing import List


def weighted_average(ratings: List[int], weights: List[float] = None) -> float:
    if not ratings:
        return 0.0
    if weights is None:
        weights = [1.0] * len(ratings)
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    return round(sum(r * w for r, w in zip(ratings, weights)) / total_weight, 2)


def bayesian_average(rating_sum: float, review_count: int,
                     global_avg: float = 4.0, min_votes: int = 10) -> float:
    """
    Bayesian average smooths new products with few reviews toward global average.
    Used to rank products fairly when some have 2 reviews and others have 500.
    Formula: (C * m + R * v) / (C + v)
      C = confidence factor (min_votes)
      m = global average
      R = actual average
      v = vote count
    """
    if review_count == 0:
        return global_avg
    avg = rating_sum / review_count
    return round((min_votes * global_avg + avg * review_count) / (min_votes + review_count), 2)


def trust_score(review_count: int, avg_rating: float,
                is_verified: bool = False, age_days: int = 0) -> float:
    """
    0-100 trust score for a product/seller rating.
    """
    score = 0.0
    score += min(40, review_count * 0.8)    # up to 40 pts for review volume
    score += avg_rating / 5 * 30             # up to 30 pts for rating quality
    if is_verified:
        score += 20                          # 20 pts for verified status
    score += min(10, age_days / 36)          # up to 10 pts for account age
    return round(min(100, score), 1)


def calculate_nps(promoters: int, detractors: int, total: int) -> float:
    """Net Promoter Score: % promoters - % detractors."""
    if total == 0:
        return 0.0
    return round((promoters - detractors) / total * 100, 1)


def rating_trend(ratings_by_month: list) -> str:
    """Detect if rating trend is improving/declining."""
    if len(ratings_by_month) < 2:
        return "stable"
    recent = sum(ratings_by_month[-2:]) / 2
    older  = sum(ratings_by_month[:-2]) / max(1, len(ratings_by_month) - 2)
    diff   = recent - older
    if diff > 0.2:
        return "improving"
    if diff < -0.2:
        return "declining"
    return "stable"
