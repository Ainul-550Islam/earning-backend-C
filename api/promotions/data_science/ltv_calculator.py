# =============================================================================
# api/promotions/data_science/ltv_calculator.py
# LTV Calculator — User Lifetime Value calculation
# Historical earnings + churn probability + growth projection
# =============================================================================

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('data_science.ltv')
CACHE_PREFIX_LTV = 'ds:ltv:{}'


@dataclass
class LTVResult:
    user_id:           int
    ltv_usd:           float       # Predicted lifetime value
    ltv_3m_usd:        float       # 3-month LTV
    ltv_12m_usd:       float       # 12-month LTV
    monthly_value:     float       # Avg monthly earnings for platform
    tenure_months:     float       # How long user has been active
    predicted_churn_month: int     # Month they'll likely churn
    segment:           str         # 'champion', 'loyal', 'at_risk', 'lost'
    commission_rate:   float       # Platform commission rate
    platform_revenue:  float       # Platform's cut from this user


@dataclass
class LTVSegment:
    segment:    str
    user_count: int
    avg_ltv:    float
    total_ltv:  float
    description: str


class LTVCalculator:
    """
    Customer Lifetime Value (LTV) calculator।

    Formula:
    LTV = (Monthly Revenue × Gross Margin) / Churn Rate

    Where:
    - Monthly Revenue = avg monthly task completions × avg reward
    - Gross Margin = platform commission rate
    - Churn Rate = probability of leaving per month

    Segments (RFM-based):
    - Champion (LTV > $50): Best users, retain at all costs
    - Loyal ($20-$50): Good users, grow them
    - Potential ($5-$20): Developing users
    - At Risk (declining): Intervention needed
    - Lost (churned): Win-back campaigns
    """

    PLATFORM_COMMISSION = 0.15   # 15% platform cut

    def calculate(self, user_id: int) -> LTVResult:
        """User LTV calculate করে।"""
        cache_key = CACHE_PREFIX_LTV.format(f'user:{user_id}')
        cached    = cache.get(cache_key)
        if cached:
            return LTVResult(**cached)

        metrics       = self._get_user_metrics(user_id)
        churn_prob    = self._estimate_churn_probability(metrics)
        monthly_rev   = metrics['monthly_earnings']
        tenure        = metrics['tenure_months']

        # LTV = monthly_value / monthly_churn_rate (geometric series)
        monthly_churn = max(0.01, churn_prob / 12)   # Annual → monthly
        if monthly_churn >= 1:
            ltv = monthly_rev * self.PLATFORM_COMMISSION
        else:
            ltv = (monthly_rev * self.PLATFORM_COMMISSION) / monthly_churn

        # Time-bounded LTV
        ltv_3m  = sum(monthly_rev * self.PLATFORM_COMMISSION * ((1-monthly_churn)**i) for i in range(3))
        ltv_12m = sum(monthly_rev * self.PLATFORM_COMMISSION * ((1-monthly_churn)**i) for i in range(12))

        predicted_churn_month = int(1 / max(monthly_churn, 0.01))
        segment = self._segment_user(ltv, metrics)

        result = LTVResult(
            user_id=user_id, ltv_usd=round(ltv, 2),
            ltv_3m_usd=round(ltv_3m, 2), ltv_12m_usd=round(ltv_12m, 2),
            monthly_value=round(monthly_rev, 2), tenure_months=round(tenure, 1),
            predicted_churn_month=min(predicted_churn_month, 60),
            segment=segment, commission_rate=self.PLATFORM_COMMISSION,
            platform_revenue=round(ltv, 2),
        )
        cache.set(cache_key, result.__dict__, timeout=3600 * 6)
        return result

    def calculate_platform_ltv_stats(self) -> dict:
        """Platform-wide LTV statistics।"""
        cache_key = CACHE_PREFIX_LTV.format('platform_stats')
        cached    = cache.get(cache_key)
        if cached:
            return cached

        try:
            from api.promotions.models import PromotionTransaction
            from django.contrib.auth import get_user_model
            from django.db.models import Sum, Count, Avg

            User     = get_user_model()
            total_users = User.objects.filter(is_active=True).count()

            earnings = PromotionTransaction.objects.aggregate(
                total=Sum('amount_usd'), avg=Avg('amount_usd')
            )
            stats = {
                'total_users': total_users,
                'total_platform_revenue': float(earnings['total'] or 0) * self.PLATFORM_COMMISSION,
                'avg_user_ltv': float(earnings['avg'] or 0) * 12 * self.PLATFORM_COMMISSION,
                'commission_rate': self.PLATFORM_COMMISSION,
            }
            cache.set(cache_key, stats, timeout=3600 * 3)
            return stats
        except Exception:
            return {}

    def segment_all_users(self) -> list:
        """All active users কে LTV segment এ divide করে।"""
        cache_key = CACHE_PREFIX_LTV.format('segments')
        cached    = cache.get(cache_key)
        if cached:
            return [LTVSegment(**s) for s in cached]

        segments = {
            'champion':  {'min': 50,  'count': 0, 'total_ltv': 0.0, 'desc': 'Top earners — VIP treatment'},
            'loyal':     {'min': 20,  'count': 0, 'total_ltv': 0.0, 'desc': 'Regular performers'},
            'potential': {'min': 5,   'count': 0, 'total_ltv': 0.0, 'desc': 'Growing users'},
            'at_risk':   {'min': 1,   'count': 0, 'total_ltv': 0.0, 'desc': 'Declining activity'},
            'lost':      {'min': 0,   'count': 0, 'total_ltv': 0.0, 'desc': 'Churned — win-back needed'},
        }
        # Simplified — in production iterate active users
        result = [
            LTVSegment(seg, d['count'], d['total_ltv']/max(d['count'],1), d['total_ltv'], d['desc'])
            for seg, d in segments.items()
        ]
        cache.set(cache_key, [r.__dict__ for r in result], timeout=3600*3)
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_user_metrics(self, user_id: int) -> dict:
        metrics = {'monthly_earnings': 0.0, 'tenure_months': 0.0, 'tasks_30d': 0, 'tasks_prev_30d': 0}
        try:
            from api.promotions.models import PromotionTransaction, TaskSubmission
            from django.contrib.auth import get_user_model
            from django.db.models import Sum, Count

            User = get_user_model()
            user = User.objects.filter(pk=user_id).values('date_joined').first()
            if user:
                metrics['tenure_months'] = (timezone.now() - user['date_joined']).days / 30

            now   = timezone.now()
            month = now - timedelta(days=30)
            earn  = PromotionTransaction.objects.filter(
                user_id=user_id, created_at__gte=month
            ).aggregate(total=Sum('amount_usd'))['total'] or 0
            metrics['monthly_earnings']  = float(earn)
            metrics['tasks_30d']         = TaskSubmission.objects.filter(worker_id=user_id, submitted_at__gte=month).count()
        except Exception:
            pass
        return metrics

    @staticmethod
    def _estimate_churn_probability(metrics: dict) -> float:
        """Simple churn probability from activity metrics।"""
        if metrics['tasks_30d'] == 0:
            return 0.9
        if metrics['tasks_30d'] >= 20:
            return 0.1
        return max(0.05, 0.9 - metrics['tasks_30d'] * 0.04)

    @staticmethod
    def _segment_user(ltv: float, metrics: dict) -> str:
        if metrics['tasks_30d'] == 0:
            return 'lost'
        if ltv >= 50:
            return 'champion'
        if ltv >= 20:
            return 'loyal'
        if ltv >= 5:
            return 'potential'
        return 'at_risk'
