# FILE 110 of 257 — reports/DailyReport.py
from decimal import Decimal
from django.db.models import Sum, Count, Avg
from django.utils import timezone

class DailyReport:
    def __init__(self, report_date=None):
        self.date = report_date or (timezone.now() - __import__('datetime').timedelta(days=1)).date()

    def generate(self) -> dict:
        from payment_gateways.models import GatewayTransaction, PayoutRequest
        gateways = ['bkash','nagad','sslcommerz','amarpay','upay','shurjopay','stripe','paypal']
        report   = {'date': str(self.date), 'gateways': {}, 'totals': {}}

        total_deposits = Decimal('0'); total_withdrawals = Decimal('0')

        for gw in gateways:
            deps = GatewayTransaction.objects.filter(
                gateway=gw, status='completed', transaction_type='deposit', created_at__date=self.date
            ).aggregate(count=Count('id'), total=Sum('amount'), avg=Avg('amount'))

            wdrs = GatewayTransaction.objects.filter(
                gateway=gw, status='completed', transaction_type='withdrawal', created_at__date=self.date
            ).aggregate(count=Count('id'), total=Sum('amount'))

            fails = GatewayTransaction.objects.filter(
                gateway=gw, status='failed', created_at__date=self.date
            ).count()

            report['gateways'][gw] = {
                'deposits':    {'count': deps['count'] or 0, 'total': float(deps['total'] or 0), 'avg': float(deps['avg'] or 0)},
                'withdrawals': {'count': wdrs['count'] or 0, 'total': float(wdrs['total'] or 0)},
                'failed':      fails,
            }
            total_deposits    += deps['total'] or Decimal('0')
            total_withdrawals += wdrs['total'] or Decimal('0')

        payouts = PayoutRequest.objects.filter(created_at__date=self.date, status='completed')
        report['totals'] = {
            'total_deposits':     float(total_deposits),
            'total_withdrawals':  float(total_withdrawals),
            'net':                float(total_deposits - total_withdrawals),
            'payout_count':       payouts.count(),
        }
        return report
