# api/publisher_tools/publisher_management/publisher_profile.py
"""
Publisher Profile Management — Profile-related utilities & helpers।
"""
from decimal import Decimal
from django.utils import timezone


def get_publisher_profile_completion(publisher) -> dict:
    """
    Publisher profile কতটুকু complete — সেটা calculate করে।
    Returns: {'percentage': int, 'missing_fields': list}
    """
    required_fields = [
        ('display_name', 'Display Name'),
        ('contact_email', 'Contact Email'),
        ('country', 'Country'),
        ('business_type', 'Business Type'),
    ]
    optional_fields = [
        ('contact_phone', 'Phone Number'),
        ('website', 'Website'),
        ('city', 'City'),
        ('address', 'Address'),
        ('is_kyc_verified', 'KYC Verification'),
    ]

    missing = []
    score = 0
    max_score = len(required_fields) * 10 + len(optional_fields) * 4

    for field, label in required_fields:
        val = getattr(publisher, field, None)
        if val:
            score += 10
        else:
            missing.append(label)

    for field, label in optional_fields:
        val = getattr(publisher, field, None)
        if val:
            score += 4

    percentage = min(100, int((score / max_score) * 100))
    return {
        'percentage': percentage,
        'missing_required': missing,
        'score': score,
        'max_score': max_score,
    }


def get_publisher_level(publisher) -> dict:
    """
    Publisher-এর level ও next level requirements।
    Standard → Premium → Enterprise
    """
    tier_requirements = {
        'standard': {
            'min_revenue': Decimal('0'),
            'min_sites': 0,
            'kyc_required': False,
        },
        'premium': {
            'min_revenue': Decimal('500'),
            'min_sites': 1,
            'kyc_required': True,
        },
        'enterprise': {
            'min_revenue': Decimal('5000'),
            'min_sites': 3,
            'kyc_required': True,
        },
    }

    current_tier = publisher.tier
    tier_order = ['standard', 'premium', 'enterprise']
    current_index = tier_order.index(current_tier)

    next_tier = None
    next_requirements = None
    if current_index < len(tier_order) - 1:
        next_tier = tier_order[current_index + 1]
        next_requirements = tier_requirements[next_tier]

    return {
        'current_tier': current_tier,
        'next_tier': next_tier,
        'next_requirements': next_requirements,
        'current_revenue': publisher.total_revenue,
        'active_sites': publisher.active_sites_count,
    }


def calculate_publisher_health_score(publisher) -> int:
    """
    Publisher health score calculate করে (0-100)।
    KYC, active sites, revenue, quality scores-এর composite।
    """
    score = 0

    # KYC (25 points)
    if publisher.is_kyc_verified:
        score += 25

    # Active inventory (25 points)
    sites = publisher.active_sites_count
    apps  = publisher.active_apps_count
    score += min(25, (sites + apps) * 5)

    # Revenue (25 points)
    if publisher.total_revenue > 1000:
        score += 25
    elif publisher.total_revenue > 100:
        score += 15
    elif publisher.total_revenue > 0:
        score += 5

    # Account age (25 points)
    from django.utils import timezone
    days_active = (timezone.now().date() - publisher.created_at.date()).days
    if days_active >= 365:
        score += 25
    elif days_active >= 180:
        score += 15
    elif days_active >= 30:
        score += 10

    return min(100, score)
