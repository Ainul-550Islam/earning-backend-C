# api/referral/logic.py
# Pure business logic functions — no DB queries, no HTTP, no side effects
# These are the core calculation functions used by services
# Fully testable in isolation (no Django required)
# ============================================================

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple


# ── Commission Calculations ───────────────────────────────────────────────────

def calculate_commission(
    earned_amount: Decimal,
    commission_rate: Decimal,
    multiplier: Decimal = Decimal('1'),
    min_amount: Decimal = Decimal('0.01'),
) -> Decimal:
    """
    Calculate commission amount.

    Args:
        earned_amount:   Base earning amount
        commission_rate: Percentage (e.g. Decimal('10') for 10%)
        multiplier:      Campaign/surge multiplier (default 1x)
        min_amount:      Minimum commission to be valid

    Returns:
        Commission amount, rounded to 4 decimal places.
        Returns Decimal('0') if below min_amount.

    Examples:
        >>> calculate_commission(Decimal('100'), Decimal('10'))
        Decimal('10.0000')
        >>> calculate_commission(Decimal('100'), Decimal('10'), Decimal('2'))
        Decimal('20.0000')
    """
    if earned_amount <= 0 or commission_rate <= 0:
        return Decimal('0')

    rate_fraction = commission_rate / Decimal('100')
    commission = (earned_amount * rate_fraction * multiplier).quantize(
        Decimal('0.0001'), rounding=ROUND_HALF_UP
    )

    if commission < min_amount:
        return Decimal('0')

    return commission


def calculate_multilevel_commissions(
    earned_amount: Decimal,
    levels: List[Dict],
    multiplier: Decimal = Decimal('1'),
) -> List[Dict]:
    """
    Calculate commissions for all levels in a referral chain.

    Args:
        earned_amount: Base earning amount
        levels: List of {'user_id': int, 'level': int, 'rate': Decimal}
        multiplier: Campaign multiplier

    Returns:
        List of {'user_id': int, 'level': int, 'rate': Decimal, 'commission': Decimal}

    Example:
        levels = [
            {'user_id': 1, 'level': 1, 'rate': Decimal('10')},
            {'user_id': 2, 'level': 2, 'rate': Decimal('5')},
            {'user_id': 3, 'level': 3, 'rate': Decimal('2')},
        ]
        >>> calculate_multilevel_commissions(Decimal('100'), levels)
        [
            {'user_id': 1, 'level': 1, 'rate': Decimal('10'), 'commission': Decimal('10')},
            {'user_id': 2, 'level': 2, 'rate': Decimal('5'),  'commission': Decimal('5')},
            {'user_id': 3, 'level': 3, 'rate': Decimal('2'),  'commission': Decimal('2')},
        ]
    """
    results = []
    for level_info in levels:
        commission = calculate_commission(
            earned_amount=earned_amount,
            commission_rate=level_info['rate'],
            multiplier=multiplier,
        )
        results.append({
            **level_info,
            'commission': commission,
            'is_paid': commission > 0,
        })
    return results


def calculate_signup_bonuses(
    referrer_bonus: Decimal,
    referred_bonus: Decimal,
    multiplier: Decimal = Decimal('1'),
) -> Dict:
    """
    Calculate double-sided signup bonuses.

    Args:
        referrer_bonus: Amount for the referring user
        referred_bonus: Amount for the new referred user
        multiplier:     Campaign multiplier

    Returns:
        {'referrer': Decimal, 'referred': Decimal, 'total': Decimal}
    """
    r1 = (referrer_bonus * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    r2 = (referred_bonus * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'referrer': r1,
        'referred': r2,
        'total': r1 + r2,
    }


# ── Fraud Scoring ─────────────────────────────────────────────────────────────

def calculate_fraud_score(flags: Dict[str, bool], rule_weights: Dict[str, int]) -> int:
    """
    Calculate fraud score from detected flags.

    Args:
        flags:        {'same_ip': True, 'same_device': False, ...}
        rule_weights: {'same_ip': 30, 'same_device': 20, 'vpn': 15, ...}

    Returns:
        Fraud score 0-100.

    Example:
        >>> calculate_fraud_score(
        ...     {'same_ip': True, 'vpn': True},
        ...     {'same_ip': 30, 'vpn': 15, 'same_device': 25}
        ... )
        45
    """
    score = 0
    for flag, is_triggered in flags.items():
        if is_triggered:
            weight = rule_weights.get(flag, 0)
            score += weight
    return min(score, 100)


def determine_fraud_action(
    score: int,
    block_threshold: int = 80,
    hold_threshold: int = 50,
    flag_threshold: int = 30,
) -> str:
    """
    Determine action based on fraud score.

    Returns:
        'block' | 'hold_commission' | 'flag' | 'allow'
    """
    if score >= block_threshold:
        return 'block'
    if score >= hold_threshold:
        return 'hold_commission'
    if score >= flag_threshold:
        return 'flag'
    return 'allow'


def is_same_ip_fraud(referrer_ip: str, referred_ip: str) -> bool:
    """Check if both IPs are the same (basic fraud signal)."""
    if not referrer_ip or not referred_ip:
        return False
    return referrer_ip.strip() == referred_ip.strip()


def is_suspicious_email(email: str) -> bool:
    """
    Check if email looks like a throwaway/spam email.
    Basic heuristics only — not a full spam-detection system.
    """
    import re
    if not email:
        return False
    suspicious_patterns = [
        r'\+\w+@',          # Plus alias (user+spam@gmail)
        r'@mailinator\.com',
        r'@10minutemail\.com',
        r'@guerrillamail\.com',
        r'@tempmail\.com',
        r'@throwam\.com',
        r'\d{6,}@',         # Many digits in local part
    ]
    email_lower = email.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, email_lower):
            return True
    return False


# ── LTV Calculations ──────────────────────────────────────────────────────────

def calculate_ltv(
    total_earnings: Decimal,
    days_active: int,
    task_count: int,
    offer_count: int,
) -> Decimal:
    """
    Calculate Lifetime Value (LTV) of a referred user.

    Simple formula:
    LTV = total_earnings + (days_active * daily_rate) + (task_count * task_value)

    Args:
        total_earnings: Total earnings made by the user
        days_active:    Days the user has been active
        task_count:     Number of tasks completed
        offer_count:    Number of offers completed

    Returns:
        LTV score as Decimal
    """
    if total_earnings <= 0 and days_active == 0:
        return Decimal('0')

    # Basic LTV = earnings + activity bonus
    activity_bonus = Decimal(str(days_active)) * Decimal('0.5')
    task_bonus     = Decimal(str(task_count))  * Decimal('2')
    offer_bonus    = Decimal(str(offer_count)) * Decimal('5')

    ltv = total_earnings + activity_bonus + task_bonus + offer_bonus
    return ltv.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def categorize_ltv_value(ltv: Decimal) -> str:
    """
    Categorize LTV into value tiers.

    Returns:
        'high_value' | 'mid_value' | 'low_value' | 'inactive'
    """
    if ltv <= 0:
        return 'inactive'
    if ltv >= Decimal('1000'):
        return 'high_value'
    if ltv >= Decimal('200'):
        return 'mid_value'
    return 'low_value'


def estimate_churn_risk(days_since_last_activity: int) -> str:
    """
    Estimate churn risk based on inactivity.

    Returns:
        'low' | 'medium' | 'high' | 'churned'
    """
    if days_since_last_activity <= 7:
        return 'low'
    if days_since_last_activity <= 30:
        return 'medium'
    if days_since_last_activity <= 90:
        return 'high'
    return 'churned'


# ── Viral Coefficient ─────────────────────────────────────────────────────────

def calculate_k_factor(
    total_invites_sent: int,
    total_users: int,
    total_conversions: int,
) -> Decimal:
    """
    Calculate K-factor (viral coefficient).

    Formula: K = (invites_per_user) × (conversion_rate)
    K > 1 = viral growth.

    Args:
        total_invites_sent: Total invite emails/shares sent
        total_users:        Total users who sent invites
        total_conversions:  How many invites converted to signups

    Returns:
        K-factor as Decimal. K >= 1.0 means viral.
    """
    if total_users <= 0:
        return Decimal('0')

    avg_invites = Decimal(str(total_invites_sent)) / Decimal(str(total_users))
    if total_invites_sent <= 0:
        return Decimal('0')

    conversion_rate = Decimal(str(total_conversions)) / Decimal(str(total_invites_sent))
    k = avg_invites * conversion_rate

    return k.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


# ── Commission Hold Logic ─────────────────────────────────────────────────────

def should_hold_commission(
    is_new_user: bool,
    user_age_days: int,
    fraud_score: int,
    hold_threshold_days: int = 7,
    fraud_hold_score: int = 30,
) -> Tuple[bool, str]:
    """
    Determine if a commission should be held.

    Returns:
        (should_hold: bool, reason: str)
    """
    if fraud_score >= fraud_hold_score:
        return True, f'fraud_risk_score_{fraud_score}'
    if is_new_user and user_age_days < hold_threshold_days:
        return True, f'new_user_hold_{hold_threshold_days}d'
    return False, ''


# ── Attribution Logic ─────────────────────────────────────────────────────────

def get_attribution_source(
    utm_source: str = '',
    utm_medium: str = '',
    referral_code: str = '',
    cookie_code: str = '',
    last_click_wins: bool = True,
) -> Optional[str]:
    """
    Determine referral attribution source using last-click model.

    Priority (last click wins):
    1. URL parameter ref code
    2. Cookie-stored ref code
    3. UTM source (for analytics only, no commission)

    Returns:
        Referral code string or None.
    """
    if last_click_wins:
        # URL param takes priority (most recent click)
        if referral_code:
            return referral_code
        if cookie_code:
            return cookie_code
    else:
        # First-click model
        if cookie_code:
            return cookie_code
        if referral_code:
            return referral_code
    return None