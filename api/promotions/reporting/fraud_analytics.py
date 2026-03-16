# api/promotions/reporting/fraud_analytics.py
import logging
from django.core.cache import cache
logger = logging.getLogger('reporting.fraud')

class FraudAnalyticsReport:
    def summary(self, days: int = 7) -> dict:
        ck = f'report:fraud:{days}'
        if cache.get(ck): return cache.get(ck)
        try:
            from api.promotions.models import FraudReport, TaskSubmission
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count, Avg
            since = timezone.now() - timedelta(days=days)
            fraud = FraudReport.objects.filter(created_at__gte=since)
            total_subs = TaskSubmission.objects.filter(submitted_at__gte=since).count()
            r = {
                'days': days,
                'total_fraud_reports': fraud.count(),
                'fraud_rate':          round(fraud.count()/max(total_subs,1)*100, 3),
                'by_type':             dict(fraud.values('fraud_type').annotate(c=Count('id')).values_list('fraud_type','c')),
                'by_country':          dict(fraud.values('user__country').annotate(c=Count('id')).order_by('-c').values_list('user__country','c')[:10]),
                'avg_fraud_score':     float(fraud.aggregate(a=Avg('fraud_score'))['a'] or 0),
                'top_fraudulent_campaigns': list(fraud.values('submission__campaign__title').annotate(c=Count('id')).order_by('-c')[:5]),
            }
            cache.set(ck, r, timeout=1800)
            return r
        except Exception as e:
            return {'days': days, 'error': str(e)}

    def by_ip_range(self, days: int = 7) -> list:
        """Suspicious IP ranges।"""
        try:
            from api.promotions.models import FraudReport
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count
            since = timezone.now() - timedelta(days=days)
            return list(
                FraudReport.objects.filter(created_at__gte=since)
                .values('ip_address').annotate(c=Count('id'))
                .order_by('-c').filter(c__gte=3)[:20]
            )
        except Exception:
            return []
