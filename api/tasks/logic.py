"""
api/tasks/logic.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure business logic functions for the task platform.
No Django models, no HTTP, no Celery — just pure Python.
These functions are easily testable and reusable.
"""

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any


# ══════════════════════════════════════════════════════════════════════════════
# REWARD CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_publisher_share(
    gross_payout: Decimal,
    publisher_tier: str = 'bronze',
    traffic_tier: str = 'tier_3',
    is_vip: bool = False,
    country: str = 'US',
) -> Dict[str, Decimal]:
    """
    Calculate the publisher's share of a gross payout.
    Factors: publisher tier, traffic quality, VIP status, geo tier.

    Returns: {publisher, platform, gross, rate, breakdown}
    """
    # Base rate by publisher tier
    base_rates = {
        'platinum': Decimal('0.85'),
        'gold':     Decimal('0.80'),
        'silver':   Decimal('0.75'),
        'bronze':   Decimal('0.70'),
    }
    rate = base_rates.get(publisher_tier, Decimal('0.70'))

    # Traffic quality bonus
    traffic_bonuses = {'tier_1': Decimal('0.02'), 'tier_2': Decimal('0.01'), 'tier_3': Decimal('0')}
    rate += traffic_bonuses.get(traffic_tier, Decimal('0'))

    # VIP bonus
    if is_vip:
        rate += Decimal('0.02')

    # Cap at 90%
    rate = min(rate, Decimal('0.90'))

    publisher = (gross_payout * rate).quantize(Decimal('0.00000001'), ROUND_HALF_UP)
    platform  = gross_payout - publisher

    return {
        'gross':     gross_payout,
        'publisher': publisher,
        'platform':  platform,
        'rate':      rate,
        'breakdown': {
            'base_rate':       str(base_rates.get(publisher_tier, Decimal('0.70'))),
            'traffic_bonus':   str(traffic_bonuses.get(traffic_tier, Decimal('0'))),
            'vip_bonus':       '0.02' if is_vip else '0',
            'final_rate':      str(rate),
        },
    }


def calculate_xp_for_action(
    action: str,
    streak: int = 0,
    level: int = 1,
    is_vip: bool = False,
) -> int:
    """
    Calculate XP to award for a user action.
    Actions: 'task_completion', 'survey', 'quiz', 'referral', 'streak_bonus'
    """
    base_xp = {
        'task_completion': 5,
        'survey':          20,
        'quiz':            15,
        'referral':        50,
        'streak_bonus':    10,
        'milestone':       100,
        'level_up':        25,
        'badge_unlock':    30,
    }.get(action, 5)

    # Streak multiplier
    if streak >= 30:
        multiplier = 1.5
    elif streak >= 14:
        multiplier = 1.3
    elif streak >= 7:
        multiplier = 1.2
    else:
        multiplier = 1.0

    # VIP bonus
    if is_vip:
        multiplier += 0.1

    return max(1, int(base_xp * multiplier))


def calculate_level_for_xp(xp: int) -> Tuple[int, int, int]:
    """
    Calculate user level and progress given total XP.
    Returns: (current_level, xp_in_level, xp_needed_for_next)
    """
    XP_THRESHOLDS = [
        0, 100, 250, 500, 1000, 2000, 4000, 8000,
        15000, 30000, 60000, 100000, 200000, 500000, 1000000,
    ]

    level = 1
    for i, threshold in enumerate(XP_THRESHOLDS):
        if xp >= threshold:
            level = i + 1
        else:
            break

    level = min(level, 30)  # Max level

    # XP within current level
    current_threshold = XP_THRESHOLDS[level - 1] if level <= len(XP_THRESHOLDS) else XP_THRESHOLDS[-1]
    next_threshold    = XP_THRESHOLDS[level] if level < len(XP_THRESHOLDS) else current_threshold * 2

    xp_in_level     = xp - current_threshold
    xp_for_next     = next_threshold - current_threshold

    return level, xp_in_level, xp_for_next


def calculate_streak_bonus(streak_days: int) -> Dict[str, Any]:
    """
    Calculate streak bonus for a given streak length.
    Returns: {cash_bonus, xp_bonus, multiplier, is_milestone}
    """
    MILESTONES = {7: True, 14: True, 30: True, 60: True, 90: True}

    # XP bonus
    xp_bonuses = {3: 30, 7: 70, 14: 140, 30: 300, 60: 600, 90: 900}
    xp_bonus   = xp_bonuses.get(streak_days, 5)

    # Cash bonus at milestones
    cash_bonuses = {7: Decimal('0.10'), 30: Decimal('0.50'), 90: Decimal('2.00')}
    cash_bonus   = cash_bonuses.get(streak_days, Decimal('0'))

    # Multiplier
    if streak_days >= 30:
        multiplier = 1.5
    elif streak_days >= 7:
        multiplier = 1.2
    else:
        multiplier = 1.0

    return {
        'xp_bonus':     xp_bonus,
        'cash_bonus':   cash_bonus,
        'multiplier':   multiplier,
        'is_milestone': streak_days in MILESTONES,
    }


def calculate_milestone_bonus(total_earnings: Decimal) -> Optional[Dict[str, Any]]:
    """
    Check if total_earnings crosses a milestone. Returns bonus info or None.
    """
    MILESTONES = {
        Decimal('1'):    Decimal('0.10'),
        Decimal('10'):   Decimal('0.50'),
        Decimal('50'):   Decimal('2.00'),
        Decimal('100'):  Decimal('5.00'),
        Decimal('250'):  Decimal('10.00'),
        Decimal('500'):  Decimal('25.00'),
        Decimal('1000'): Decimal('75.00'),
        Decimal('5000'): Decimal('500.00'),
    }
    for threshold, bonus in sorted(MILESTONES.items()):
        if total_earnings >= threshold:
            return {'threshold': threshold, 'bonus': bonus}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD SCORING LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def compute_fraud_score(
    velocity_1h: int = 0,
    ip_diversity: int = 1,
    account_age_hours: float = 999,
    reward_vs_avg: float = 1.0,
    new_account: bool = False,
    ip_blocked: bool = False,
    device_reuse: bool = False,
    proxy_vpn: bool = False,
    chargeback_history: int = 0,
) -> Tuple[int, str]:
    """
    Compute a fraud risk score (0-100) from signals.
    Returns: (score, risk_level)
    """
    if ip_blocked:
        return 100, 'critical'

    score = 0

    # Velocity
    if velocity_1h > 50:
        score += min(int((velocity_1h - 50) / 5) * 3, 30)
    elif velocity_1h > 20:
        score += 15
    elif velocity_1h > 10:
        score += 5

    # Single IP for many completions
    if ip_diversity == 1 and velocity_1h > 15:
        score += 20

    # Account age
    if account_age_hours < 1:
        score += 25
    elif account_age_hours < 24:
        score += 20
    elif account_age_hours < 72:
        score += 10

    # Reward anomaly
    if reward_vs_avg > 5:
        score += 25
    elif reward_vs_avg > 3:
        score += 15

    # New account with activity
    if new_account and velocity_1h > 5:
        score += 10

    # Device reuse
    if device_reuse:
        score += 20

    # Proxy/VPN
    if proxy_vpn:
        score += 15

    # Chargeback history
    score += min(chargeback_history * 10, 20)

    score = min(score, 100)

    if score >= 80:
        risk = 'critical'
    elif score >= 60:
        risk = 'high'
    elif score >= 40:
        risk = 'medium'
    elif score >= 20:
        risk = 'low'
    else:
        risk = 'clean'

    return score, risk


def is_completion_suspicious(
    user_id: int,
    ip_address: str,
    completions_in_last_hour: int,
    time_taken_seconds: float,
    expected_min_seconds: float = 10.0,
) -> Tuple[bool, List[str]]:
    """
    Check if a single task completion is suspicious.
    Returns: (is_suspicious, reasons)
    """
    reasons = []

    # Too fast
    if time_taken_seconds < expected_min_seconds * 0.3:
        reasons.append(f'too_fast:{time_taken_seconds:.1f}s<{expected_min_seconds*0.3:.1f}s')

    # High velocity
    if completions_in_last_hour > 20:
        reasons.append(f'high_velocity:{completions_in_last_hour}/hour')

    return bool(reasons), reasons


# ══════════════════════════════════════════════════════════════════════════════
# OFFER RANKING LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def compute_offer_quality_score(
    epc: float = 0.0,
    cvr: float = 0.0,
    payout: float = 0.0,
    platform_avg_epc: float = 0.01,
    platform_avg_payout: float = 1.0,
    days_old: int = 30,
) -> float:
    """
    Compute offer quality score (0-100).
    Components: EPC (40%) + CVR (30%) + Payout competitiveness (20%) + Freshness (10%)
    """
    # EPC score (0-40)
    epc_score = min((epc / max(platform_avg_epc, 0.001)) * 40, 40)

    # CVR score (0-30): 10% CVR = max
    cvr_score = min(cvr / 10 * 30, 30)

    # Payout competitiveness (0-20)
    pay_score = min((payout / max(platform_avg_payout, 0.01)) * 20, 20)

    # Freshness (0-10)
    fresh_score = max(10 - days_old, 0)

    return round(epc_score + cvr_score + pay_score + fresh_score, 1)


def rank_offers(
    offers: List[Dict],
    user_segment: str = 'casual_user',
    country: str = 'US',
) -> List[Dict]:
    """
    Rank a list of offer dicts by quality score, adjusted for user segment.
    Each offer dict should have: payout, epc, cvr, quality_score, category.
    Returns offers sorted by adjusted score (descending).
    """
    SEGMENT_WEIGHTS = {
        'new_user':    {'payout': 0.4, 'cvr': 0.3, 'epc': 0.2, 'quality': 0.1},
        'casual_user': {'payout': 0.3, 'cvr': 0.3, 'epc': 0.3, 'quality': 0.1},
        'power_user':  {'payout': 0.2, 'cvr': 0.2, 'epc': 0.4, 'quality': 0.2},
        'vip_user':    {'payout': 0.2, 'cvr': 0.1, 'epc': 0.5, 'quality': 0.2},
    }
    weights = SEGMENT_WEIGHTS.get(user_segment, SEGMENT_WEIGHTS['casual_user'])

    def score_offer(offer: Dict) -> float:
        payout  = float(offer.get('payout') or 0)
        epc     = float(offer.get('epc') or 0)
        cvr     = float(offer.get('cvr') or offer.get('conversion_rate') or 0)
        quality = float(offer.get('quality_score') or 50)

        # Normalize each to 0-1 (rough)
        return (
            weights['payout']  * min(payout / 5.0, 1.0) +
            weights['epc']     * min(epc / 0.5, 1.0) +
            weights['cvr']     * min(cvr / 10.0, 1.0) +
            weights['quality'] * quality / 100.0
        )

    return sorted(offers, key=score_offer, reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# RTB AUCTION LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def run_second_price_auction(
    bids: List[Dict],
    floor_price: Decimal,
    num_winners: int = 5,
) -> List[Dict]:
    """
    Run a second-price (Vickrey) auction.
    Winner pays second-highest bid + $0.001.
    Returns winning bids with clearing_price set.

    Each bid dict: {campaign_id, bid_price, quality_score, ...}
    """
    # Filter by floor
    eligible = [b for b in bids if Decimal(str(b.get('bid_price', 0))) >= floor_price]

    if not eligible:
        return []

    # Sort by effective score: 70% bid + 30% quality
    eligible.sort(
        key=lambda x: (
            float(x.get('bid_price', 0)) * 0.7 +
            float(x.get('quality_score', 50)) / 100 * 0.3
        ),
        reverse=True,
    )

    winners = eligible[:num_winners]

    # Assign clearing prices (second-price)
    for i, winner in enumerate(winners):
        if i + 1 < len(eligible):
            second_price = Decimal(str(eligible[i + 1]['bid_price']))
            clearing     = second_price + Decimal('0.001')
        else:
            clearing = floor_price
        winner = dict(winner)
        winner['clearing_price'] = str(clearing)
        winners[i] = winner

    return winners


# ══════════════════════════════════════════════════════════════════════════════
# PAYOUT ELIGIBILITY LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def check_payout_eligibility(
    wallet_balance: Decimal,
    payment_method: str,
    fraud_score: int = 0,
    kyc_tier: str = 'none',
    is_suspended: bool = False,
    payout_method_valid: bool = True,
    already_paid_today: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Check whether a user is eligible for a payout.
    Returns: (is_eligible, list_of_reasons_if_not)
    """
    from api.tasks.constants import MIN_PAYOUT

    reasons = []

    if is_suspended:
        reasons.append('account_suspended')

    if already_paid_today:
        reasons.append('already_paid_today')

    if fraud_score >= 60:
        reasons.append(f'fraud_score_too_high:{fraud_score}')

    if not payout_method_valid:
        reasons.append('invalid_payout_method')

    min_payout = MIN_PAYOUT.get(payment_method, MIN_PAYOUT['default'])
    if wallet_balance < min_payout:
        reasons.append(f'balance_below_minimum:{wallet_balance}<{min_payout}')

    # KYC check for large payouts
    if wallet_balance >= Decimal('100') and kyc_tier == 'none':
        reasons.append('kyc_required_for_large_payout')

    return len(reasons) == 0, reasons


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY POINTS LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def get_prize_tier(monthly_points: int) -> Optional[Dict]:
    """Return the prize tier for a given monthly point total."""
    from api.tasks.constants import PRIZE_TIERS
    current_tier = None
    for threshold in sorted(PRIZE_TIERS.keys()):
        if monthly_points >= threshold:
            current_tier = {'threshold': threshold, **PRIZE_TIERS[threshold]}
    return current_tier


def get_next_prize_tier(monthly_points: int) -> Optional[Dict]:
    """Return the next prize tier above current points."""
    from api.tasks.constants import PRIZE_TIERS
    for threshold in sorted(PRIZE_TIERS.keys()):
        if monthly_points < threshold:
            pts_needed = threshold - monthly_points
            return {
                'threshold':  threshold,
                'pts_needed': pts_needed,
                **PRIZE_TIERS[threshold],
            }
    return None


# ══════════════════════════════════════════════════════════════════════════════
# PUBLISHER TIER LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def calculate_publisher_tier(monthly_earnings: Decimal) -> str:
    """Return the publisher tier based on monthly earnings."""
    if monthly_earnings >= Decimal('1000'):
        return 'platinum'
    if monthly_earnings >= Decimal('500'):
        return 'gold'
    if monthly_earnings >= Decimal('100'):
        return 'silver'
    return 'bronze'


def get_traffic_tier_from_score(quality_score: float) -> str:
    """Return traffic tier string from a quality score."""
    if quality_score >= 80:
        return 'tier_1'
    if quality_score >= 50:
        return 'tier_2'
    if quality_score >= 20:
        return 'tier_3'
    return 'low_quality'


__all__ = [
    'calculate_publisher_share', 'calculate_xp_for_action',
    'calculate_level_for_xp', 'calculate_streak_bonus', 'calculate_milestone_bonus',
    'compute_fraud_score', 'is_completion_suspicious',
    'compute_offer_quality_score', 'rank_offers',
    'run_second_price_auction',
    'check_payout_eligibility',
    'get_prize_tier', 'get_next_prize_tier',
    'calculate_publisher_tier', 'get_traffic_tier_from_score',
]
