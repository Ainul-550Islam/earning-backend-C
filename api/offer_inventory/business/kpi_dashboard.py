# api/offer_inventory/business/kpi_dashboard.py
"""
KPI Dashboard — Business Intelligence Engine.
Platform-wide KPIs, revenue forecasting, cohort analysis,
user LTV, network ROI, and executive summary reports.
All monetary values use Decimal.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta, date
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, Q
from django.core.cache import cache

logger = logging.getLogger(__name__)

P2 = Decimal('0.01')
P4 = Decimal('0.0001')


def _d(v, default='0') -> Decimal:
    try:
        return Decimal(str(v or default))
    except Exception:
        return Decimal(default)


class KPIDashboard:
    """
    Real-time and historical KPI computation.
    All metrics cached for performance.
    """

    CACHE_TTL = 300   # 5 min

    # ── Core Platform KPIs ────────────────────────────────────────

    @classmethod
    def get_platform_kpis(cls, days: int = 30, tenant=None) -> dict:
        """
        Executive KPI summary — top-level platform health.
        """
        cache_key = f'kpi_platform:{tenant}:{days}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        since = timezone.now() - timedelta(days=days)
        from api.offer_inventory.models import (
            Click, Conversion, WithdrawalRequest,
            DailyStat, UserProfile
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # ── User metrics ──────────────────────────────────────────
        total_users  = User.objects.filter(is_active=True).count()
        new_users    = User.objects.filter(date_joined__gte=since).count()
        active_users = User.objects.filter(last_login__gte=since).count()
        retention    = round(active_users / max(total_users, 1) * 100, 1)

        # ── Click metrics ─────────────────────────────────────────
        clicks_qs   = Click.objects.filter(created_at__gte=since, is_fraud=False)
        total_clicks= clicks_qs.count()
        fraud_clicks= Click.objects.filter(created_at__gte=since, is_fraud=True).count()
        fraud_rate  = round(fraud_clicks / max(total_clicks + fraud_clicks, 1) * 100, 2)

        # ── Conversion metrics ────────────────────────────────────
        conv_qs     = Conversion.objects.filter(created_at__gte=since)
        approved    = conv_qs.filter(status__name='approved')
        conv_agg    = approved.aggregate(
            count  =Count('id'),
            revenue=Sum('payout_amount'),
            rewards=Sum('reward_amount'),
        )
        total_conv  = conv_agg['count']   or 0
        gross_rev   = _d(conv_agg['revenue'])
        user_rewards= _d(conv_agg['rewards'])
        platform_rev= (gross_rev - user_rewards).quantize(P2)
        cvr         = round(total_conv / max(total_clicks, 1) * 100, 2)
        epc         = (gross_rev / _d(max(total_clicks, 1))).quantize(P4)

        # ── Withdrawal metrics ────────────────────────────────────
        wd_qs = WithdrawalRequest.objects.filter(created_at__gte=since)
        wd_agg = wd_qs.aggregate(
            total_requested=Sum('amount'),
            total_paid     =Sum('amount', filter=Q(status='completed')),
            count_pending  =Count('id', filter=Q(status='pending')),
        )

        # ── DAU/MAU ───────────────────────────────────────────────
        dau = User.objects.filter(last_login__date=timezone.now().date()).count()
        mau = User.objects.filter(last_login__gte=timezone.now() - timedelta(days=30)).count()

        kpis = {
            # User
            'total_users'      : total_users,
            'new_users'        : new_users,
            'active_users'     : active_users,
            'dau'              : dau,
            'mau'              : mau,
            'retention_rate'   : retention,
            # Click
            'total_clicks'     : total_clicks,
            'fraud_clicks'     : fraud_clicks,
            'fraud_rate_pct'   : fraud_rate,
            # Conversion
            'total_conversions': total_conv,
            'cvr_pct'          : cvr,
            'gross_revenue'    : float(gross_rev),
            'user_rewards'     : float(user_rewards),
            'platform_revenue' : float(platform_rev),
            'epc'              : float(epc),
            # Withdrawal
            'wd_requested'     : float(_d(wd_agg['total_requested'])),
            'wd_paid'          : float(_d(wd_agg['total_paid'])),
            'wd_pending_count' : wd_agg['count_pending'] or 0,
            # Meta
            'period_days'      : days,
            'computed_at'      : timezone.now().isoformat(),
        }

        cache.set(cache_key, kpis, cls.CACHE_TTL)
        return kpis

    # ── Revenue Forecast ──────────────────────────────────────────

    @classmethod
    def forecast_revenue(cls, days_ahead: int = 30,
                          tenant=None) -> dict:
        """
        Simple linear revenue forecast based on last 30-day trend.
        """
        from api.offer_inventory.models import DailyStat

        # Get last 30 days of actual data
        since = timezone.now().date() - timedelta(days=30)
        stats = list(
            DailyStat.objects.filter(date__gte=since)
            .order_by('date')
            .values('date', 'total_revenue', 'approved_conversions', 'total_clicks')
        )

        if len(stats) < 7:
            return {'error': 'Insufficient data for forecast'}

        # Simple moving average
        revenues = [float(_d(s['total_revenue'])) for s in stats]
        avg_daily = sum(revenues) / len(revenues)
        trend_pct = 0.0

        if len(revenues) >= 14:
            first_half  = sum(revenues[:len(revenues)//2]) / (len(revenues)//2)
            second_half = sum(revenues[len(revenues)//2:]) / (len(revenues)//2)
            if first_half > 0:
                trend_pct = (second_half - first_half) / first_half

        # Project forward
        projected_daily  = avg_daily * (1 + trend_pct)
        projected_total  = projected_daily * days_ahead
        projected_low    = projected_total * 0.80
        projected_high   = projected_total * 1.20

        return {
            'avg_daily_revenue'  : round(avg_daily, 2),
            'trend_pct'          : round(trend_pct * 100, 1),
            'projected_daily'    : round(projected_daily, 2),
            'projected_total'    : round(projected_total, 2),
            'projected_low'      : round(projected_low, 2),
            'projected_high'     : round(projected_high, 2),
            'forecast_days'      : days_ahead,
            'based_on_days'      : len(stats),
        }

    # ── Cohort Analysis ───────────────────────────────────────────

    @classmethod
    def cohort_retention(cls, cohort_months: int = 6) -> list:
        """
        Monthly cohort retention analysis.
        Returns list of cohorts with retention rates per month.
        """
        from django.contrib.auth import get_user_model
        from api.offer_inventory.models import Conversion
        User = get_user_model()

        cohorts  = []
        now      = timezone.now()

        for i in range(cohort_months):
            cohort_month = now - timedelta(days=30 * (cohort_months - i))
            cohort_start = cohort_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            cohort_end   = (cohort_start + timedelta(days=32)).replace(day=1)

            # Users who joined in this month
            cohort_users = User.objects.filter(
                date_joined__gte=cohort_start,
                date_joined__lt =cohort_end,
            ).values_list('id', flat=True)

            cohort_size  = len(cohort_users)
            if cohort_size == 0:
                continue

            retention_by_month = []
            for m in range(min(i + 1, 6)):
                check_start = cohort_start + timedelta(days=30 * m)
                check_end   = check_start + timedelta(days=30)
                active = Conversion.objects.filter(
                    user_id__in =cohort_users,
                    created_at__gte=check_start,
                    created_at__lt =check_end,
                    status__name='approved',
                ).values('user_id').distinct().count()
                retention_by_month.append(round(active / cohort_size * 100, 1))

            cohorts.append({
                'cohort'          : cohort_start.strftime('%Y-%m'),
                'size'            : cohort_size,
                'retention_by_month': retention_by_month,
            })

        return cohorts

    # ── User LTV ──────────────────────────────────────────────────

    @classmethod
    def calculate_ltv(cls, segment: str = 'all') -> dict:
        """
        Calculate average Lifetime Value (LTV) per user.
        LTV = avg revenue per user over their lifetime.
        """
        from api.offer_inventory.models import Conversion
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user_ltv = (
            Conversion.objects.filter(status__name='approved')
            .values('user_id')
            .annotate(total=Sum('payout_amount'))
        )

        if not user_ltv:
            return {'avg_ltv': 0, 'median_ltv': 0, 'total_users': 0}

        values = sorted([float(_d(u['total'])) for u in user_ltv])
        avg    = sum(values) / len(values)
        median = values[len(values) // 2] if values else 0

        # Segment LTV tiers
        tiers = {
            'low'   : len([v for v in values if v < 100]),
            'mid'   : len([v for v in values if 100 <= v < 1000]),
            'high'  : len([v for v in values if v >= 1000]),
        }

        return {
            'avg_ltv'   : round(avg, 2),
            'median_ltv': round(median, 2),
            'max_ltv'   : round(max(values), 2) if values else 0,
            'total_users': len(values),
            'tiers'     : tiers,
        }

    # ── Network ROI ───────────────────────────────────────────────

    @classmethod
    def network_roi_report(cls, days: int = 30) -> list:
        """
        ROI analysis per affiliate network.
        ROI = (platform_cut / total_payout) × 100
        """
        from api.offer_inventory.models import OfferNetwork, Conversion, Click
        from datetime import timedelta

        since    = timezone.now() - timedelta(days=days)
        networks = OfferNetwork.objects.filter(status='active')
        report   = []

        for network in networks:
            conv_agg = Conversion.objects.filter(
                offer__network=network,
                created_at__gte=since,
                status__name='approved',
            ).aggregate(
                count  =Count('id'),
                revenue=Sum('payout_amount'),
                rewards=Sum('reward_amount'),
            )

            clicks    = Click.objects.filter(
                offer__network=network, created_at__gte=since, is_fraud=False
            ).count()
            revenue   = _d(conv_agg['revenue'])
            rewards   = _d(conv_agg['rewards'])
            platform  = revenue - rewards
            roi       = (platform / revenue * 100).quantize(P2) if revenue > 0 else Decimal('0')

            report.append({
                'network'       : network.name,
                'clicks'        : clicks,
                'conversions'   : conv_agg['count'] or 0,
                'gross_revenue' : float(revenue),
                'user_rewards'  : float(rewards),
                'platform_profit': float(platform),
                'roi_pct'       : float(roi),
                'epc'           : float((revenue / _d(max(clicks, 1))).quantize(P4)),
                'cvr_pct'       : round((conv_agg['count'] or 0) / max(clicks, 1) * 100, 2),
            })

        return sorted(report, key=lambda x: x['platform_profit'], reverse=True)

    # ── Executive Summary ─────────────────────────────────────────

    @classmethod
    def executive_summary(cls, tenant=None) -> dict:
        """Full executive summary — combines all KPIs."""
        return {
            'today'           : cls.get_platform_kpis(days=1,  tenant=tenant),
            'last_7_days'     : cls.get_platform_kpis(days=7,  tenant=tenant),
            'last_30_days'    : cls.get_platform_kpis(days=30, tenant=tenant),
            'revenue_forecast': cls.forecast_revenue(days_ahead=30),
            'network_roi'     : cls.network_roi_report(days=30),
            'user_ltv'        : cls.calculate_ltv(),
            'generated_at'    : timezone.now().isoformat(),
        }
