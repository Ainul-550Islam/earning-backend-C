# api/promotions/reporting/revenue_report.py
import logging
from decimal import Decimal
from django.core.cache import cache
logger = logging.getLogger('reporting.revenue')

class RevenueReport:
    """Platform revenue breakdowns — daily, weekly, monthly, by platform/category."""

    def daily(self, date=None) -> dict:
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg
        d = date or (timezone.now().date() - timedelta(days=1))
        ck = f'report:rev:daily:{d}'
        if cache.get(ck): return cache.get(ck)
        try:
            from api.promotions.models import AdminCommissionLog, TaskSubmission
            from api.promotions.choices import SubmissionStatus
            rev  = AdminCommissionLog.objects.filter(created_at__date=d)
            subs = TaskSubmission.objects.filter(submitted_at__date=d)
            r = {
                'date': str(d),
                'gross_revenue_usd':    float(rev.aggregate(t=Sum('total_amount_usd'))['t'] or 0),
                'platform_commission':  float(rev.aggregate(t=Sum('commission_usd'))['t'] or 0),
                'advertiser_spend':     float(rev.aggregate(t=Sum('advertiser_deducted_usd'))['t'] or 0),
                'worker_earnings':      float(rev.aggregate(t=Sum('worker_reward_usd'))['t'] or 0),
                'total_submissions':    subs.count(),
                'approved_submissions': subs.filter(status=SubmissionStatus.APPROVED).count(),
                'by_platform': dict(
                    rev.values('campaign__platform__name')
                    .annotate(rev=Sum('total_amount_usd'))
                    .values_list('campaign__platform__name', 'rev')
                ),
            }
            cache.set(ck, r, timeout=3600*6)
            return r
        except Exception as e:
            return {'date': str(d), 'error': str(e)}

    def monthly(self, year: int, month: int) -> dict:
        from django.db.models import Sum, Count
        ck = f'report:rev:monthly:{year}-{month}'
        if cache.get(ck): return cache.get(ck)
        try:
            from api.promotions.models import AdminCommissionLog
            qs = AdminCommissionLog.objects.filter(created_at__year=year, created_at__month=month)
            r  = {
                'year': year, 'month': month,
                'gross_usd':    float(qs.aggregate(t=Sum('total_amount_usd'))['t'] or 0),
                'commission':   float(qs.aggregate(t=Sum('commission_usd'))['t'] or 0),
                'transactions': qs.count(),
                'by_platform':  dict(qs.values('campaign__platform__name').annotate(r=Sum('total_amount_usd')).values_list('campaign__platform__name','r')),
                'by_category':  dict(qs.values('campaign__category__name').annotate(r=Sum('total_amount_usd')).values_list('campaign__category__name','r')),
            }
            cache.set(ck, r, timeout=3600*12)
            return r
        except Exception as e:
            return {'year': year, 'month': month, 'error': str(e)}

    def trend(self, days: int = 30) -> list:
        """Daily revenue trend for chart。"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum
        from api.promotions.models import AdminCommissionLog
        result = []
        for i in range(days-1, -1, -1):
            d   = timezone.now().date() - timedelta(days=i)
            rev = AdminCommissionLog.objects.filter(created_at__date=d).aggregate(t=Sum('total_amount_usd'))['t'] or 0
            result.append({'date': str(d), 'revenue': float(rev)})
        return result
