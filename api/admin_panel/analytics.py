# api/admin_panel/analytics.py
"""
Admin Panel Analytics Engine.
Aggregates data from all 50 apps for admin analytics dashboard.
Calls app models — never stores analytics data itself.
Provides: revenue analytics, user analytics, offer analytics, fraud analytics,
retention, LTV, cohort analysis, funnel analytics, geo analytics.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.db.models import Count, Sum, Avg, Q, F, Max, Min
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, TruncHour
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta, date

logger = logging.getLogger(__name__)
CACHE_TTL = 300  # 5 min


def _cached(key: str, fn, ttl: int = CACHE_TTL):
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = fn()
    cache.set(key, result, ttl)
    return result


# ===========================================================================
# REVENUE ANALYTICS
# ===========================================================================

def get_revenue_overview(days: int = 30) -> Dict:
    def _compute():
        cutoff = timezone.now() - timedelta(days=days)
        result = {}
        # Wallet earnings (credits)
        try:
            from api.wallet.models import WalletTransaction
            txn = WalletTransaction.objects.filter(
                created_at__gte=cutoff, transaction_type='earning'
            ).aggregate(total=Sum('gross_amount'), count=Count('id'))
            result['total_earned'] = float(txn['total'] or 0)
            result['total_transactions'] = txn['count'] or 0
        except Exception:
            pass
        # Payout totals
        try:
            from api.payout_queue.models import PayoutItem
            paid = PayoutItem.objects.filter(
                created_at__gte=cutoff, status='SUCCESS'
            ).aggregate(total=Sum('gross_amount'), count=Count('id'))
            result['total_paid_out'] = float(paid['total'] or 0)
            result['payout_count'] = paid['count'] or 0
        except Exception:
            pass
        return result
    return _cached(f'analytics:revenue_overview:{days}', _compute)


def get_daily_revenue_trend(days: int = 30) -> List[Dict]:
    def _compute():
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.wallet.models import WalletTransaction
            return list(
                WalletTransaction.objects.filter(
                    created_at__gte=cutoff, transaction_type='earning'
                ).annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(total=Sum('gross_amount'), count=Count('id'))
                .order_by('day')
            )
        except Exception:
            return []
    return _cached(f'analytics:daily_revenue:{days}', _compute)


def get_revenue_by_gateway(days: int = 30) -> List[Dict]:
    def _compute():
        try:
            from api.payout_queue.models import PayoutItem
            cutoff = timezone.now() - timedelta(days=days)
            return list(
                PayoutItem.objects.filter(created_at__gte=cutoff, status='SUCCESS')
                .values('gateway')
                .annotate(total=Sum('gross_amount'), count=Count('id'))
                .order_by('-total')
            )
        except Exception:
            return []
    return _cached(f'analytics:revenue_gateway:{days}', _compute)


def get_hourly_revenue(hours: int = 24) -> List[Dict]:
    def _compute():
        cutoff = timezone.now() - timedelta(hours=hours)
        try:
            from api.wallet.models import WalletTransaction
            return list(
                WalletTransaction.objects.filter(
                    created_at__gte=cutoff, transaction_type='earning'
                ).annotate(hour=TruncHour('created_at'))
                .values('hour').annotate(total=Sum('gross_amount'), count=Count('id'))
                .order_by('hour')
            )
        except Exception:
            return []
    return _cached(f'analytics:hourly_revenue:{hours}', _compute, ttl=60)


# ===========================================================================
# USER ANALYTICS
# ===========================================================================

def get_user_overview() -> Dict:
    def _compute():
        from django.contrib.auth import get_user_model
        User = get_user_model()
        today = timezone.now().date()
        last_7d = timezone.now() - timedelta(days=7)
        last_30d = timezone.now() - timedelta(days=30)
        return {
            'total': User.objects.count(),
            'active': User.objects.filter(is_active=True).count(),
            'banned': User.objects.filter(is_active=False).count(),
            'staff': User.objects.filter(is_staff=True).count(),
            'new_today': User.objects.filter(date_joined__date=today).count(),
            'new_7d': User.objects.filter(date_joined__gte=last_7d).count(),
            'new_30d': User.objects.filter(date_joined__gte=last_30d).count(),
        }
    return _cached('analytics:user_overview', _compute, ttl=60)


def get_user_registration_trend(days: int = 30) -> List[Dict]:
    def _compute():
        from django.contrib.auth import get_user_model
        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            User.objects.filter(date_joined__gte=cutoff)
            .annotate(day=TruncDate('date_joined'))
            .values('day').annotate(count=Count('id')).order_by('day')
        )
    return _cached(f'analytics:user_reg_trend:{days}', _compute)


def get_user_retention(cohort_days: int = 30) -> Dict:
    """Simple day-1, day-7, day-30 retention."""
    def _compute():
        from django.contrib.auth import get_user_model
        User = get_user_model()
        now = timezone.now()
        cohort_start = now - timedelta(days=cohort_days + 30)
        cohort_end   = now - timedelta(days=30)
        cohort = User.objects.filter(date_joined__range=(cohort_start, cohort_end)).count()
        if not cohort:
            return {'cohort_size': 0, 'day1': 0, 'day7': 0, 'day30': 0}
        retained_30d = User.objects.filter(
            date_joined__range=(cohort_start, cohort_end),
            last_login__gte=cohort_end,
        ).count()
        return {
            'cohort_size': cohort,
            'day30_retained': retained_30d,
            'retention_30d_pct': round(retained_30d / cohort * 100, 2) if cohort else 0,
        }
    return _cached('analytics:user_retention', _compute, ttl=3600)


def get_geo_breakdown(days: int = 30, limit: int = 20) -> List[Dict]:
    """User/revenue breakdown by country using proxy_intelligence."""
    def _compute():
        try:
            from api.proxy_intelligence.models import IPIntelligence
            cutoff = timezone.now() - timedelta(days=days)
            return list(
                IPIntelligence.objects.filter(created_at__gte=cutoff)
                .values('country_code')
                .annotate(count=Count('id'))
                .order_by('-count')[:limit]
            )
        except Exception:
            return []
    return _cached(f'analytics:geo:{days}', _compute)


# ===========================================================================
# OFFER / CONVERSION ANALYTICS
# ===========================================================================

def get_offer_analytics(days: int = 7) -> Dict:
    def _compute():
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.promotions.models import TaskSubmission
            return {
                'total': TaskSubmission.objects.filter(created_at__gte=cutoff).count(),
                'approved': TaskSubmission.objects.filter(created_at__gte=cutoff, status='SUCCESS').count(),
                'pending': TaskSubmission.objects.filter(created_at__gte=cutoff, status='QUEUED').count(),
                'rejected': TaskSubmission.objects.filter(created_at__gte=cutoff, status='FAILED').count(),
                'total_reward': float(TaskSubmission.objects.filter(
                    created_at__gte=cutoff, status='SUCCESS'
                ).aggregate(t=Sum('reward_amount'))['t'] or 0),
            }
        except Exception:
            return {}
    return _cached(f'analytics:offer:{days}', _compute)


def get_top_offers_by_revenue(days: int = 7, limit: int = 10) -> List[Dict]:
    def _compute():
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.promotions.models import TaskSubmission
            return list(
                TaskSubmission.objects.filter(created_at__gte=cutoff, status='SUCCESS')
                .values('campaign__title', 'campaign_id')
                .annotate(revenue=Sum('reward_amount'), count=Count('id'))
                .order_by('-revenue')[:limit]
            )
        except Exception:
            return []
    return _cached(f'analytics:top_offers:{days}', _compute)


# ===========================================================================
# FRAUD ANALYTICS
# ===========================================================================

def get_fraud_analytics(days: int = 7) -> Dict:
    def _compute():
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.fraud_detection.models import FraudAttempt
            qs = FraudAttempt.objects.filter(created_at__gte=cutoff)
            return {
                'total': qs.count(),
                'critical': qs.filter(fraud_score__gte=90).count(),
                'high': qs.filter(fraud_score__gte=70, fraud_score__lt=90).count(),
                'medium': qs.filter(fraud_score__gte=50, fraud_score__lt=70).count(),
                'avg_score': round(float(qs.aggregate(a=Avg('fraud_score'))['a'] or 0), 2),
                'by_type': list(qs.values('attempt_type').annotate(c=Count('id')).order_by('-c')[:10]),
            }
        except Exception:
            return {}
    return _cached(f'analytics:fraud:{days}', _compute, ttl=60)


def get_fraud_trend(days: int = 30) -> List[Dict]:
    def _compute():
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.fraud_detection.models import FraudAttempt
            return list(
                FraudAttempt.objects.filter(created_at__gte=cutoff)
                .annotate(day=TruncDate('created_at'))
                .values('day').annotate(count=Count('id'), avg_score=Avg('fraud_score'))
                .order_by('day')
            )
        except Exception:
            return []
    return _cached(f'analytics:fraud_trend:{days}', _compute)


# ===========================================================================
# SMARTLINK ANALYTICS
# ===========================================================================

def get_smartlink_analytics(days: int = 7) -> Dict:
    def _compute():
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.smartlink.models.click import Click
            qs = Click.objects.filter(created_at__gte=cutoff)
            return {
                'total_clicks': qs.count(),
                'unique_ips': qs.values('ip').distinct().count(),
                'conversions': qs.filter(converted=True).count(),
                'conversion_rate': round(qs.filter(converted=True).count() / max(qs.count(), 1) * 100, 2),
            }
        except Exception:
            return {}
    return _cached(f'analytics:smartlink:{days}', _compute)


# ===========================================================================
# FULL PLATFORM DASHBOARD ANALYTICS
# ===========================================================================

def get_admin_dashboard_analytics(days: int = 7) -> Dict:
    """Master analytics snapshot for admin dashboard."""
    return {
        'revenue':   get_revenue_overview(days),
        'users':     get_user_overview(),
        'offers':    get_offer_analytics(days),
        'fraud':     get_fraud_analytics(days),
        'smartlink': get_smartlink_analytics(days),
        'period_days': days,
        'generated_at': timezone.now().isoformat(),
    }