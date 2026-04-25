# FILE 111 of 257 — reports/MonthlyReport.py
import calendar
from decimal import Decimal
from datetime import date
from django.db.models import Sum, Count
from django.utils import timezone

class MonthlyReport:
    def __init__(self, year: int = None, month: int = None):
        now        = timezone.now()
        self.year  = year  or now.year
        self.month = month or now.month
        _, last_day = calendar.monthrange(self.year, self.month)
        self.start = date(self.year, self.month, 1)
        self.end   = date(self.year, self.month, last_day)

    def generate(self) -> dict:
        from payment_gateways.models import GatewayTransaction, PayoutRequest
        from payment_gateways.refunds.models import RefundRequest

        deps = GatewayTransaction.objects.filter(
            status='completed', transaction_type='deposit',
            created_at__date__range=(self.start, self.end)
        ).aggregate(count=Count('id'), total=Sum('amount'))

        wdrs = GatewayTransaction.objects.filter(
            status='completed', transaction_type='withdrawal',
            created_at__date__range=(self.start, self.end)
        ).aggregate(count=Count('id'), total=Sum('amount'))

        refs = RefundRequest.objects.filter(
            status='completed',
            created_at__date__range=(self.start, self.end)
        ).aggregate(count=Count('id'), total=Sum('amount'))

        return {
            'year': self.year, 'month': self.month,
            'period': f'{self.start} to {self.end}',
            'deposits':    {'count': deps['count'] or 0, 'total': float(deps['total'] or 0)},
            'withdrawals': {'count': wdrs['count'] or 0, 'total': float(wdrs['total'] or 0)},
            'refunds':     {'count': refs['count'] or 0, 'total': float(refs['total'] or 0)},
            'net_revenue': float((deps['total'] or Decimal('0')) - (refs['total'] or Decimal('0'))),
        }
