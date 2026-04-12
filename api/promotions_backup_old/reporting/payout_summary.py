# api/promotions/reporting/payout_summary.py
import logging
from decimal import Decimal
from django.core.cache import cache
logger = logging.getLogger('reporting.payout')

class PayoutSummaryReport:
    def summary(self, days: int = 7) -> dict:
        ck = f'report:payout:{days}'
        if cache.get(ck): return cache.get(ck)
        try:
            from api.promotions.models import PromotionTransaction
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Sum, Count, Avg
            since = timezone.now() - timedelta(days=days)
            txns  = PromotionTransaction.objects.filter(created_at__gte=since, transaction_type='payout')
            r = {
                'days': days,
                'total_paid_usd':  float(txns.aggregate(t=Sum('amount_usd'))['t'] or 0),
                'total_payouts':   txns.count(),
                'avg_payout_usd':  float(txns.aggregate(a=Avg('amount_usd'))['a'] or 0),
                'by_method':       dict(txns.values('payment_method').annotate(t=Sum('amount_usd')).values_list('payment_method','t')),
                'by_country':      dict(txns.values('user__country').annotate(t=Sum('amount_usd')).order_by('-t').values_list('user__country','t')[:10]),
                'pending_amount':  float(PromotionTransaction.objects.filter(status='pending', transaction_type='payout').aggregate(t=Sum('amount_usd'))['t'] or 0),
            }
            cache.set(ck, r, timeout=1800)
            return r
        except Exception as e:
            return {'days': days, 'error': str(e)}
