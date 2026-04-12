# kyc/management/commands/generate_kyc_analytics.py  ── WORLD #1
"""Management command: python manage.py generate_kyc_analytics"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate KYC daily analytics snapshots'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Generate for last N days')
        parser.add_argument('--tenant-id', type=int, default=None, help='Specific tenant ID')

    def handle(self, *args, **options):
        import datetime
        from django.utils import timezone
        from api.kyc.services import KYCAnalyticsService

        days      = options['days']
        tenant_id = options['tenant_id']
        tenant    = None

        if tenant_id:
            try:
                from api.tenants.models import Tenant
                tenant = Tenant.objects.get(id=tenant_id)
            except Exception:
                self.stderr.write(f'Tenant #{tenant_id} not found')
                return

        for i in range(days):
            date = (timezone.now() - datetime.timedelta(days=i)).date()
            try:
                snap = KYCAnalyticsService.generate_daily_snapshot(tenant=tenant, date=date)
                self.stdout.write(self.style.SUCCESS(
                    f'[{date}] verified={snap.total_verified} rejected={snap.total_rejected} '
                    f'pending={snap.total_pending} high_risk={snap.high_risk_count}'
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'[{date}] Failed: {e}'))
