# api/djoyalty/logic.py
"""
Djoyalty Logic -- Pure business logic functions।
No DB access, no HTTP -- pure calculation & rules।
Easily testable without Django setup।
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# ─── Points Calculation ───────────────────────────────────────────────────────

def calculate_earn_points(
    transaction_value: Decimal,
    earn_rate: Decimal = Decimal('1'),
    multiplier: Decimal = Decimal('1'),
    bonus_percent: Decimal = Decimal('0'),
    max_points: Optional[Decimal] = None,
) -> Decimal:
    """
    Calculate points earned for a transaction।
    earn_rate = points per 1 unit of currency (e.g. 1 point per 1 BDT)
    multiplier = tier multiplier (e.g. 2x for Gold tier)
    bonus_percent = extra bonus percentage (e.g. 20 = 20% bonus)
    """
    base = (transaction_value * earn_rate * multiplier).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    if bonus_percent > 0:
        bonus = (base * bonus_percent / 100).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        base = base + bonus

    if max_points and base > max_points:
        base = max_points

    return max(base, Decimal('0'))


def calculate_points_cash_value(
    points: Decimal,
    redemption_rate: Decimal = Decimal('0.01'),
) -> Decimal:
    """
    Convert points to cash value।
    redemption_rate = BDT per point (e.g. 0.01 BDT per point)
    """
    return (points * redemption_rate).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def calculate_cashout_amount(
    points: Decimal,
    points_per_unit: Decimal = Decimal('100'),
    processing_fee_pct: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate cash amount for cashout।
    points_per_unit = points needed for 1 BDT (e.g. 100 points = 1 BDT)
    """
    gross = (points / points_per_unit).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if processing_fee_pct > 0:
        fee = (gross * processing_fee_pct / 100).quantize(Decimal('0.01'))
        gross = gross - fee
    return max(gross, Decimal('0'))


def calculate_tier_progress(
    current_points: Decimal,
    current_tier_min: Decimal,
    next_tier_min: Decimal,
) -> dict:
    """
    Calculate tier progression percentage and points needed।
    Returns: {percent: int, points_needed: Decimal, points_in_range: Decimal}
    """
    if next_tier_min <= current_tier_min:
        return {'percent': 100, 'points_needed': Decimal('0'), 'points_in_range': Decimal('0')}

    range_size = next_tier_min - current_tier_min
    progress = current_points - current_tier_min

    if progress <= 0:
        return {
            'percent': 0,
            'points_needed': next_tier_min - current_points,
            'points_in_range': Decimal('0'),
        }

    percent = min(int((progress / range_size) * 100), 100)
    points_needed = max(next_tier_min - current_points, Decimal('0'))

    return {
        'percent': percent,
        'points_needed': points_needed,
        'points_in_range': min(progress, range_size),
    }


# ─── RFM Scoring ─────────────────────────────────────────────────────────────

def compute_rfm_score(
    recency_days: int,
    frequency: int,
    monetary_value: Decimal,
) -> dict:
    """
    Compute RFM score (1-5 each, 5 = best)।
    recency_days: days since last purchase
    frequency: number of purchases
    monetary_value: total spend
    """
    # Recency (lower days = higher score)
    if recency_days <= 7:
        r = 5
    elif recency_days <= 30:
        r = 4
    elif recency_days <= 60:
        r = 3
    elif recency_days <= 120:
        r = 2
    else:
        r = 1

    # Frequency
    if frequency >= 20:
        f = 5
    elif frequency >= 10:
        f = 4
    elif frequency >= 5:
        f = 3
    elif frequency >= 2:
        f = 2
    else:
        f = 1

    # Monetary
    m_val = float(monetary_value)
    if m_val >= 50000:
        m = 5
    elif m_val >= 20000:
        m = 4
    elif m_val >= 5000:
        m = 3
    elif m_val >= 1000:
        m = 2
    else:
        m = 1

    total = r + f + m
    if total >= 13:
        segment = 'champions'
    elif total >= 10:
        segment = 'loyal'
    elif total >= 7:
        segment = 'potential_loyal'
    elif total >= 5:
        segment = 'at_risk'
    else:
        segment = 'lost'

    return {
        'recency_score': r,
        'frequency_score': f,
        'monetary_score': m,
        'total_score': total,
        'rfm_segment': segment,
    }


def compute_churn_probability(
    recency_days: int,
    frequency: int,
    avg_order_value: Decimal,
    account_age_days: int,
) -> dict:
    """
    Estimate churn probability (0.0 - 1.0)।
    Simple heuristic model (replace with ML in production)।
    """
    score = 0.0

    # Recency contribution
    if recency_days > 120:
        score += 0.40
    elif recency_days > 60:
        score += 0.25
    elif recency_days > 30:
        score += 0.10

    # Frequency contribution (low = more likely to churn)
    if frequency <= 1:
        score += 0.25
    elif frequency <= 3:
        score += 0.15
    elif frequency <= 5:
        score += 0.05

    # Low AOV
    if float(avg_order_value) < 500:
        score += 0.10

    # New account with no recent activity
    if account_age_days < 30 and recency_days > 14:
        score += 0.20

    probability = min(score, 1.0)

    if probability >= 0.6:
        risk = 'critical'
    elif probability >= 0.4:
        risk = 'high'
    elif probability >= 0.2:
        risk = 'medium'
    else:
        risk = 'low'

    return {
        'churn_probability': round(probability, 4),
        'risk_level': risk,
    }


# ─── Offerwall Points Calculation ────────────────────────────────────────────

def calculate_offerwall_points(
    payout_usd: Decimal,
    currency_ratio: Decimal = Decimal('100'),
    bonus_pct: Decimal = Decimal('0'),
) -> Decimal:
    """
    Calculate points from offerwall payout।
    currency_ratio = points per $1 USD (e.g. 100 pts per $1)
    """
    points = (payout_usd * currency_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    if bonus_pct > 0:
        bonus = (points * bonus_pct / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        points += bonus
    return max(points, Decimal('0'))


# ─── Voucher Logic ────────────────────────────────────────────────────────────

def calculate_voucher_discount(
    original_price: Decimal,
    discount_value: Decimal,
    discount_type: str = 'percent',
    max_discount: Optional[Decimal] = None,
) -> Decimal:
    """
    Calculate voucher discount amount।
    discount_type: 'percent' | 'fixed'
    """
    if discount_type == 'percent':
        discount = (original_price * discount_value / 100).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    else:
        discount = discount_value

    if max_discount and discount > max_discount:
        discount = max_discount

    return min(discount, original_price)


def apply_voucher(
    original_price: Decimal,
    discount_amount: Decimal,
) -> Decimal:
    """Apply discount and return final price।"""
    return max(original_price - discount_amount, Decimal('0'))
