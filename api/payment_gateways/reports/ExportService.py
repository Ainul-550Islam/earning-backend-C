# FILE 113 of 257 — reports/ExportService.py
import csv, os
from django.conf import settings
from django.utils import timezone

class ExportService:
    def export_user_transactions_csv(self, user_id: int, filters: dict = None) -> str:
        from payment_gateways.models import GatewayTransaction
        qs = GatewayTransaction.objects.filter(user_id=user_id).order_by('-created_at')
        if filters:
            if filters.get('gateway'):   qs = qs.filter(gateway=filters['gateway'])
            if filters.get('status'):    qs = qs.filter(status=filters['status'])
            if filters.get('date_from'): qs = qs.filter(created_at__date__gte=filters['date_from'])
            if filters.get('date_to'):   qs = qs.filter(created_at__date__lte=filters['date_to'])

        filename  = f'txns_user{user_id}_{timezone.now().strftime("%Y%m%d%H%M%S")}.csv'
        media_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(media_dir, exist_ok=True)
        filepath  = os.path.join(media_dir, filename)

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['reference_id','gateway','type','amount','fee','net_amount','status','created_at'])
            for t in qs:
                writer.writerow([t.reference_id, t.gateway, t.transaction_type,
                                  t.amount, t.fee, t.net_amount, t.status, t.created_at.strftime('%Y-%m-%d %H:%M:%S')])
        return filepath

    def export_all_transactions_csv(self, date_from=None, date_to=None) -> str:
        from payment_gateways.models import GatewayTransaction
        qs = GatewayTransaction.objects.all().order_by('-created_at')
        if date_from: qs = qs.filter(created_at__date__gte=date_from)
        if date_to:   qs = qs.filter(created_at__date__lte=date_to)
        filename = f'all_txns_{timezone.now().strftime("%Y%m%d")}.csv'
        filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id','user_email','gateway','type','amount','status','created_at'])
            for t in qs:
                writer.writerow([t.id, t.user.email, t.gateway, t.transaction_type, t.amount, t.status, t.created_at])
        return filepath
