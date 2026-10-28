# api/djoyalty/selectors.py
"""
Djoyalty Selectors -- Read-only query functions (CQRS read side)।
Pure query functions -- no writes, no side effects।
Pattern: CQRS Selectors (HackSoft Django Styleguide)।
"Do not summarize or skip any logic. Provide the full code."
"""
from decimal import Decimal
from typing import Optional, List
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta


# ─── Customer Selectors ───────────────────────────────────────────────────────

def get_customer_by_code(code: str, tenant=None):
    """Get customer by code।"""
    from .models.core import Customer
    qs = Customer.objects.filter(code=code.upper(), is_active=True)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.first()


def get_customer_by_phone(phone: str, tenant=None):
    """Get customer by phone number (normalized)।"""
    from .models.core import Customer
    from .helpers import normalize_bd_phone
    normalized = normalize_bd_phone(phone)
    if not normalized:
        return None
    qs = Customer.objects.filter(phone=normalized, is_active=True)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.first()


def get_customer_loyalty_summary(customer) -> dict:
    """
    Get full loyalty summary for a customer।
    Returns: balance, tier, streak, unread_notifications, badges_count,
             lifetime_earned, lifetime_redeemed, total_transactions।
    """
    from .models.points import LoyaltyPoints
    from .models.notifications import NotificationCenter
    from .models.engagement import UserBadge, DailyStreak

    # Points
    lp = LoyaltyPoints.objects.filter(customer=customer).first()
    balance = lp.balance if lp else Decimal('0')
    lifetime_earned = lp.lifetime_earned if lp else Decimal('0')
    lifetime_redeemed = lp.lifetime_redeemed if lp else Decimal('0')

    # Tier
    ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()
    tier_name = ut.tier.name if ut else 'Bronze'
    tier_rank = ut.tier.rank if ut else 0

    # Streak
    streak = DailyStreak.objects.filter(customer=customer, is_active=True).first()
    streak_days = streak.current_streak if streak else 0

    # Badges
    badges_count = UserBadge.objects.filter(customer=customer).count()

    # Unread notifications
    unread = NotificationCenter.objects.filter(customer=customer, is_read=False).count()

    # Total transactions
    total_txns = customer.transactions.count()

    return {
        'customer_id': customer.id,
        'code': customer.code,
        'balance': balance,
        'tier': tier_name,
        'tier_rank': tier_rank,
        'lifetime_earned': lifetime_earned,
        'lifetime_redeemed': lifetime_redeemed,
        'streak_days': streak_days,
        'badges_count': badges_count,
        'unread_notifications': unread,
        'total_transactions': total_txns,
    }


# ─── Points Selectors ─────────────────────────────────────────────────────────

def get_points_balance(customer) -> Decimal:
    """Get current points balance for customer।"""
    from .models.points import LoyaltyPoints
    lp = LoyaltyPoints.objects.filter(customer=customer).first()
    return lp.balance if lp else Decimal('0')


def get_points_expiring_soon(customer, days: int = 7) -> Decimal:
    """Get total points expiring within N days।"""
    from .models.points import PointsExpiry
    cutoff = timezone.now() + timedelta(days=days)
    result = PointsExpiry.objects.filter(
        customer=customer,
        is_expired=False,
        expiry_date__lte=cutoff,
        expiry_date__gt=timezone.now(),
    ).aggregate(total=Sum('points_remaining'))
    return result['total'] or Decimal('0')


def get_points_history(customer, limit: int = 20, source: str = '') -> list:
    """Get points ledger history for customer।"""
    from .models.points import PointsLedger
    qs = PointsLedger.objects.filter(customer=customer, is_reversed=False)
    if source:
        qs = qs.filter(source=source)
    return list(qs.order_by('-created_at')[:limit])


def get_points_earned_this_month(customer) -> Decimal:
    """Get total points earned this month।"""
    from .models.points import PointsLedger
    now = timezone.now()
    result = PointsLedger.objects.filter(
        customer=customer,
        txn_type='credit',
        is_reversed=False,
        created_at__year=now.year,
        created_at__month=now.month,
    ).aggregate(total=Sum('points'))
    return result['total'] or Decimal('0')


# ─── Tier Selectors ───────────────────────────────────────────────────────────

def get_current_tier(customer):
    """Get customer's current tier object।"""
    ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()
    return ut.tier if ut else None


def get_next_tier(customer):
    """Get next tier above customer's current tier।"""
    from .models.tiers import LoyaltyTier
    current = get_current_tier(customer)
    if not current:
        return LoyaltyTier.objects.filter(is_active=True).order_by('rank').first()
    return LoyaltyTier.objects.filter(
        is_active=True, rank__gt=current.rank
    ).order_by('rank').first()


def get_tier_progress(customer) -> dict:
    """Get tier progression details for customer।"""
    from .logic import calculate_tier_progress
    current = get_current_tier(customer)
    next_t = get_next_tier(customer)
    balance = get_points_balance(customer)

    current_min = current.min_points if current else Decimal('0')
    next_min = next_t.min_points if next_t else current_min + Decimal('9999')

    return {
        'current_tier': current.name if current else 'Bronze',
        'next_tier': next_t.name if next_t else None,
        'balance': balance,
        **calculate_tier_progress(balance, current_min, next_min),
    }


# ─── Engagement Selectors ─────────────────────────────────────────────────────

def get_customer_badges(customer) -> list:
    """Get all badges earned by customer।"""
    from .models.engagement import UserBadge
    return list(
        UserBadge.objects.filter(customer=customer)
        .select_related('badge')
        .order_by('-earned_at')
    )


def get_active_challenges(customer) -> list:
    """Get challenges the customer is currently participating in।"""
    from .models.engagement import ChallengeParticipant
    return list(
        ChallengeParticipant.objects.filter(
            customer=customer,
            status='in_progress',
        ).select_related('challenge')
    )


def get_current_streak(customer):
    """Get customer's current daily streak。"""
    from .models.engagement import DailyStreak
    return DailyStreak.objects.filter(customer=customer, is_active=True).first()


# ─── Analytics Selectors ──────────────────────────────────────────────────────

def get_top_customers_by_balance(tenant=None, limit: int = 10) -> list:
    """Get top customers by current points balance।"""
    from .models.points import LoyaltyPoints
    qs = LoyaltyPoints.objects.filter(balance__gt=0)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return list(
        qs.select_related('customer')
        .order_by('-balance')[:limit]
    )


def get_dashboard_stats(tenant=None) -> dict:
    """Get summary stats for admin dashboard।"""
    from .models.core import Customer, Txn
    from .models.points import LoyaltyPoints
    from .models.cashout import CashoutRequest
    from .models.offerwall import OfferCompletion

    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def q(qs):
        return qs.filter(tenant=tenant) if tenant else qs

    return {
        'total_customers': q(Customer.objects.filter(is_active=True)).count(),
        'new_customers_this_month': q(Customer.objects.filter(
            created_at__gte=this_month_start
        )).count(),
        'total_points_outstanding': q(LoyaltyPoints.objects.all()).aggregate(
            total=Sum('balance')
        )['total'] or Decimal('0'),
        'total_points_earned_lifetime': q(LoyaltyPoints.objects.all()).aggregate(
            total=Sum('lifetime_earned')
        )['total'] or Decimal('0'),
        'transactions_this_month': q(Txn.objects.filter(
            created_at__gte=this_month_start
        )).count(),
        'pending_cashouts': q(CashoutRequest.objects.filter(status='pending')).count(),
        'offer_completions_this_month': q(OfferCompletion.objects.filter(
            completed_at__gte=this_month_start,
            status='points_awarded',
        )).count(),
    }


def get_referral_stats(customer) -> dict:
    """Get referral statistics for a customer।"""
    from .models.referral import ReferralLink, ReferralConversion

    link = ReferralLink.objects.filter(customer=customer).first()
    if not link:
        return {
            'total_clicks': 0, 'unique_clicks': 0,
            'total_conversions': 0, 'total_points_earned': Decimal('0'),
        }

    return {
        'code': link.code,
        'total_clicks': link.total_clicks,
        'unique_clicks': link.unique_clicks,
        'total_conversions': link.total_conversions,
        'total_points_earned': link.total_points_earned,
        'total_commission': link.total_commission_earned,
    }
