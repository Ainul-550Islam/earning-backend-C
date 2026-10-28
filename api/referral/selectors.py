# api/referral/selectors.py
# Selectors — read-only query functions (CQRS pattern read side)
# These functions ONLY read data. No writes, no side effects.
# Views and serializers call selectors; never query ORM directly in views.
# ============================================================

import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ── User Referral Summary ─────────────────────────────────────────────────────

def get_user_referral_summary(user) -> Dict:
    """
    Complete referral summary for a user's profile/dashboard.
    Returns all stats needed for the frontend in one call.
    """
    from api.referral.models import (
        Referral, ReferralEarning, CommissionLog, ReferralCode
    )
    from api.referral.caching import ReferralUserStatsCache

    # Try cache first
    cached = ReferralUserStatsCache.get(user.id)
    if cached:
        return cached

    # DB queries
    referral_count = Referral.objects.filter(referrer=user).count()
    active_count   = Referral.objects.filter(referrer=user, is_suspicious=False).count()

    earnings = ReferralEarning.objects.filter(referrer=user, status='released')
    total_commission = earnings.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    now = timezone.now()
    this_month = earnings.filter(
        created_at__year=now.year, created_at__month=now.month
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    held = CommissionLog.objects.filter(
        user=user, status='held'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # Level breakdown
    level_breakdown = {}
    for level in [1, 2, 3]:
        level_earnings = earnings.filter(level=level)
        level_breakdown[f'level{level}'] = {
            'count': Referral.objects.filter(
                referral_chain_beneficiary__beneficiary=user,
                referral_chain_beneficiary__level=level,
            ).count() if level > 1 else referral_count,
            'commission': float(
                level_earnings.aggregate(t=Sum('amount'))['t'] or 0
            ),
        }

    # Primary code
    code_obj = ReferralCode.objects.filter(
        user=user, is_primary=True, is_active=True
    ).first()
    code = code_obj.code if code_obj else (getattr(user, 'referral_code', '') or '')

    from django.conf import settings as django_settings
    base = getattr(django_settings, 'FRONTEND_URL', '')

    stats = {
        'referral_code':        code,
        'referral_link':        f'{base}/go/{code}/' if code else '',
        'total_referrals':      referral_count,
        'active_referrals':     active_count,
        'total_commission':     float(total_commission),
        'this_month_commission':float(this_month),
        'held_commission':      float(held),
        'level1_count':         level_breakdown['level1']['count'],
        'level1_commission':    level_breakdown['level1']['commission'],
        'level2_count':         level_breakdown['level2']['count'],
        'level2_commission':    level_breakdown['level2']['commission'],
        'level3_count':         level_breakdown['level3']['count'],
        'level3_commission':    level_breakdown['level3']['commission'],
    }

    ReferralUserStatsCache.set(user.id, stats)
    return stats


# ── Referral List ─────────────────────────────────────────────────────────────

def get_user_referral_list(user, limit: int = 20, offset: int = 0) -> List[Dict]:
    """
    Paginated list of referred users for profile page.
    """
    from api.referral.models import Referral
    referrals = Referral.objects.filter(
        referrer=user
    ).select_related(
        'referred_user'
    ).order_by('-created_at')[offset:offset + limit]

    return [
        {
            'id':            r.id,
            'username':      r.referred_user.username,
            'joined_at':     r.created_at.isoformat(),
            'is_suspicious': r.is_suspicious,
            'total_commission': float(r.total_commission_earned),
        }
        for r in referrals
    ]


# ── Commission History ────────────────────────────────────────────────────────

def get_commission_history(
    user,
    status: str = None,
    level: int = None,
    source_type: str = None,
    from_date=None,
    to_date=None,
    limit: int = 25,
    offset: int = 0,
) -> Dict:
    """
    Filtered, paginated commission history for a user.
    """
    from api.referral.models import CommissionLog

    qs = CommissionLog.objects.filter(user=user).select_related(
        'referred_user', 'campaign'
    ).order_by('-created_at')

    if status:
        qs = qs.filter(status=status)
    if level:
        qs = qs.filter(level=level)
    if source_type:
        qs = qs.filter(action_type=source_type)
    if from_date:
        qs = qs.filter(created_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__date__lte=to_date)

    total = qs.count()
    items = qs[offset:offset + limit]

    return {
        'total': total,
        'limit': limit,
        'offset': offset,
        'results': [
            {
                'id':            c.id,
                'amount':        float(c.amount),
                'level':         c.level,
                'status':        c.status,
                'action_type':   c.action_type,
                'referred_user': c.referred_user.username,
                'campaign':      c.campaign.name if c.campaign else None,
                'created_at':    c.created_at.isoformat(),
            }
            for c in items
        ],
    }


# ── Leaderboard ───────────────────────────────────────────────────────────────

def get_leaderboard(period: str = 'weekly', limit: int = 50, tenant=None) -> List[Dict]:
    """
    Leaderboard of top referrers for a period.
    """
    from api.referral.models import TopReferrer
    from api.referral.caching import ReferralLeaderboardCache

    # Try cache
    cached = ReferralLeaderboardCache.get(period)
    if cached:
        return cached[:limit]

    today = timezone.now().date()
    qs = TopReferrer.objects.filter(
        period=period, date=today
    ).select_related('user').order_by('rank')

    if tenant:
        qs = qs.filter(tenant=tenant)

    data = [
        {
            'rank':             entry.rank,
            'username':         entry.user.username,
            'referral_count':   entry.referral_count,
            'commission_earned':float(entry.commission_earned),
            'rank_change':      entry.rank_change,
        }
        for entry in qs[:50]
    ]

    ReferralLeaderboardCache.set(period, data)
    return data[:limit]


# ── Active Campaign ───────────────────────────────────────────────────────────

def get_active_campaign() -> Optional[Dict]:
    """
    Get current active referral campaign for display on frontend.
    Returns None if no active campaign.
    """
    from api.referral.caching import ReferralCache, KEY_ACTIVE_CAMPAIGN, TTL_CAMPAIGN

    cached = ReferralCache.get(KEY_ACTIVE_CAMPAIGN)
    if cached is not None:
        return cached if cached != '__none__' else None

    from api.referral.models import ReferralCampaign
    now = timezone.now()
    campaign = ReferralCampaign.objects.filter(
        is_active=True, start_date__lte=now, end_date__gte=now
    ).filter(
        Q(max_budget__isnull=True) | Q(current_spend__lt=F('max_budget'))
    ).order_by('-is_featured', '-bonus_multiplier').first()

    if campaign:
        data = {
            'id':             campaign.id,
            'name':           campaign.name,
            'description':    campaign.description,
            'multiplier':     float(campaign.bonus_multiplier),
            'extra_bonus':    float(campaign.extra_signup_bonus),
            'end_date':       campaign.end_date.isoformat(),
            'terms':          campaign.terms,
            'is_featured':    campaign.is_featured,
        }
        ReferralCache.set(KEY_ACTIVE_CAMPAIGN, data, TTL_CAMPAIGN)
        return data

    ReferralCache.set(KEY_ACTIVE_CAMPAIGN, '__none__', TTL_CAMPAIGN)
    return None


# ── Admin Insights ────────────────────────────────────────────────────────────

def get_admin_overview(days: int = 30, tenant=None) -> Dict:
    """
    Admin dashboard overview stats.
    """
    from api.referral.models import (
        Referral, CommissionLog, SuspiciousReferral,
        ReferralEarning, ReferralInsight,
    )

    cutoff = timezone.now() - timedelta(days=days)
    qs_filter = Q(created_at__gte=cutoff)
    if tenant:
        qs_filter &= Q(tenant=tenant)

    new_referrals  = Referral.objects.filter(qs_filter).count()
    suspicious     = SuspiciousReferral.objects.filter(
        status='pending'
    ).count()
    commission_paid = CommissionLog.objects.filter(
        status='released', **({'tenant': tenant} if tenant else {})
    ).filter(created_at__gte=cutoff).aggregate(t=Sum('amount'))['t'] or 0
    total_held     = CommissionLog.objects.filter(
        status='held', **({'tenant': tenant} if tenant else {})
    ).aggregate(t=Sum('amount'))['t'] or 0

    # Daily trend (last 7 days)
    daily_trend = []
    for i in range(7, 0, -1):
        day = timezone.now().date() - timedelta(days=i)
        count = Referral.objects.filter(created_at__date=day).count()
        daily_trend.append({'date': str(day), 'referrals': count})

    return {
        'period_days':       days,
        'new_referrals':     new_referrals,
        'pending_fraud':     suspicious,
        'commission_paid':   float(commission_paid),
        'commission_held':   float(total_held),
        'daily_trend':       daily_trend,
    }


# ── LTV Insights ──────────────────────────────────────────────────────────────

def get_ltv_overview(user, limit: int = 10) -> Dict:
    """
    LTV breakdown for a referrer's referred users.
    """
    from api.referral.models import ReferralLTV

    referred_ltv = ReferralLTV.objects.filter(
        referred_by=user
    ).select_related('user').order_by('-lifetime_value')[:limit]

    categories = ReferralLTV.objects.filter(
        referred_by=user
    ).values('value_category').annotate(count=Count('id'))

    return {
        'top_referred': [
            {
                'username':       r.user.username,
                'ltv':            float(r.lifetime_value),
                'churn_risk':     r.churn_risk,
                'value_category': r.value_category,
                'days_active':    r.days_active,
            }
            for r in referred_ltv
        ],
        'by_category': {
            row['value_category']: row['count'] for row in categories
        },
        'total_ltv': float(
            ReferralLTV.objects.filter(
                referred_by=user
            ).aggregate(t=Sum('lifetime_value'))['t'] or 0
        ),
    }


# ── Fraud Queue ───────────────────────────────────────────────────────────────

def get_fraud_review_queue(min_score: int = 30, status: str = 'pending',
                           limit: int = 50) -> List[Dict]:
    """
    Admin fraud review queue.
    """
    from api.referral.models import SuspiciousReferral

    qs = SuspiciousReferral.objects.filter(
        status=status, fraud_score__gte=min_score
    ).select_related(
        'referral__referrer', 'referral__referred_user', 'reviewed_by'
    ).order_by('-fraud_score', '-detected_at')[:limit]

    return [
        {
            'id':             sr.id,
            'referral_id':    sr.referral_id,
            'referrer':       sr.referral.referrer.username,
            'referred_user':  sr.referral.referred_user.username,
            'fraud_score':    sr.fraud_score,
            'flags':          sr.flags,
            'status':         sr.status,
            'detected_at':    sr.detected_at.isoformat(),
        }
        for sr in qs
    ]


# ── Referral Code Analytics ───────────────────────────────────────────────────

def get_code_analytics(code_obj) -> Dict:
    """
    Analytics for a specific referral code.
    """
    from api.referral.models import ReferralSubID, ReferralSocialShare

    conversion_rate = 0.0
    if code_obj.clicks > 0:
        conversion_rate = round(code_obj.conversions / code_obj.clicks * 100, 2)

    # Top sub1 sources
    sub_ids = list(
        ReferralSubID.objects.filter(code=code_obj)
        .values('sub1')
        .annotate(clicks=Count('id'), conversions=Sum('converted'))
        .order_by('-conversions')[:5]
    )

    # Social share breakdown
    shares = list(
        ReferralSocialShare.objects.filter(referral_code=code_obj)
        .values('platform')
        .annotate(shares=F('share_count'), clicks=F('click_count'))
        .order_by('-shares')
    )

    return {
        'code':             code_obj.code,
        'total_clicks':     code_obj.clicks,
        'unique_clicks':    code_obj.unique_clicks,
        'conversions':      code_obj.conversions,
        'conversion_rate':  conversion_rate,
        'top_sub_ids':      sub_ids,
        'social_shares':    shares,
    }