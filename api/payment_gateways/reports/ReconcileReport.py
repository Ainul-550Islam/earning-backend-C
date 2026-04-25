# FILE 114 of 257 — reports/ReconcileReport.py
from django.db.models import Sum, Count

class ReconcileReport:
    def generate(self, date_from, date_to) -> dict:
        from payment_gateways.models import GatewayTransaction
        gateways = ['bkash','nagad','sslcommerz','amarpay','upay','shurjopay','stripe','paypal']
        report   = {'from': str(date_from), 'to': str(date_to), 'gateways': {}}
        for gw in gateways:
            qs = GatewayTransaction.objects.filter(gateway=gw, created_at__date__range=(date_from, date_to))
            completed = qs.filter(status='completed').aggregate(count=Count('id'), total=Sum('amount'))
            failed    = qs.filter(status='failed').aggregate(count=Count('id'))
            pending   = qs.filter(status__in=('pending','processing')).count()
            report['gateways'][gw] = {
                'completed_count': completed['count'] or 0,
                'completed_total': float(completed['total'] or 0),
                'failed_count':    failed['count'] or 0,
                'pending_count':   pending,
            }
        return report
