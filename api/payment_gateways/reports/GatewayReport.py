# FILE 112 of 257 — reports/GatewayReport.py
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta

class GatewayReport:
    def __init__(self, gateway: str, days: int = 30):
        self.gateway = gateway
        self.since   = timezone.now() - timedelta(days=days)
        self.days    = days

    def generate(self) -> dict:
        from payment_gateways.models import GatewayTransaction

        qs = GatewayTransaction.objects.filter(gateway=self.gateway, created_at__gte=self.since)

        by_status = {}
        for status in ('pending','processing','completed','failed','cancelled'):
            agg = qs.filter(status=status).aggregate(count=Count('id'), total=Sum('amount'))
            by_status[status] = {'count': agg['count'] or 0, 'total': float(agg['total'] or 0)}

        success_rate = 0
        total = by_status['completed']['count'] + by_status['failed']['count']
        if total > 0:
            success_rate = round(by_status['completed']['count'] / total * 100, 2)

        avg_result = qs.filter(status='completed').aggregate(avg=Avg('amount'))

        return {
            'gateway':      self.gateway,
            'period_days':  self.days,
            'by_status':    by_status,
            'success_rate': success_rate,
            'avg_deposit':  float(avg_result['avg'] or 0),
        }
