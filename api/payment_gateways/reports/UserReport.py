# FILE 115 of 257 — reports/UserReport.py
from django.db.models import Sum, Count, Max

class UserReport:
    def generate(self, user_id: int) -> dict:
        from payment_gateways.models import GatewayTransaction, PayoutRequest
        from payment_gateways.refunds.models import RefundRequest

        deps = GatewayTransaction.objects.filter(user_id=user_id, status='completed', transaction_type='deposit')
        wdrs = GatewayTransaction.objects.filter(user_id=user_id, status='completed', transaction_type='withdrawal')
        refs = RefundRequest.objects.filter(user_id=user_id, status='completed')

        dep_agg  = deps.aggregate(count=Count('id'), total=Sum('amount'), last=Max('created_at'))
        wdr_agg  = wdrs.aggregate(count=Count('id'), total=Sum('amount'))
        ref_agg  = refs.aggregate(count=Count('id'), total=Sum('amount'))

        gw_breakdown = {}
        for gw in deps.values_list('gateway', flat=True).distinct():
            gw_deps = deps.filter(gateway=gw).aggregate(count=Count('id'), total=Sum('amount'))
            gw_breakdown[gw] = {'count': gw_deps['count'], 'total': float(gw_deps['total'] or 0)}

        return {
            'user_id':     user_id,
            'deposits':    {'count': dep_agg['count'] or 0, 'total': float(dep_agg['total'] or 0), 'last': str(dep_agg['last'] or '')},
            'withdrawals': {'count': wdr_agg['count'] or 0, 'total': float(wdr_agg['total'] or 0)},
            'refunds':     {'count': ref_agg['count'] or 0, 'total': float(ref_agg['total'] or 0)},
            'by_gateway':  gw_breakdown,
        }
