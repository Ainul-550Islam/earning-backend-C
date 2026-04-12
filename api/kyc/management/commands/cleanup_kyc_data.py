# kyc/management/commands/cleanup_kyc_data.py  ── WORLD #1
"""Management command: python manage.py cleanup_kyc_data"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Clean up old KYC export jobs, OTP logs, webhook delivery logs'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7,  help='Delete records older than N days')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        import datetime
        from django.utils import timezone
        from api.kyc.models import KYCExportJob, KYCOTPLog, KYCWebhookDeliveryLog

        days    = options['days']
        dry_run = options['dry_run']
        cutoff  = timezone.now() - datetime.timedelta(days=days)

        targets = [
            (KYCExportJob,         {'status__in': ['done','failed'], 'created_at__lt': cutoff}, 'Export Jobs'),
            (KYCOTPLog,            {'expires_at__lt': cutoff},                                  'OTP Logs'),
            (KYCWebhookDeliveryLog,{'sent_at__lt': cutoff},                                     'Webhook Delivery Logs'),
        ]

        for Model, filters, label in targets:
            qs    = Model.objects.filter(**filters)
            count = qs.count()
            if dry_run:
                self.stdout.write(self.style.WARNING(f'[DRY RUN] Would delete {count} {label}'))
            else:
                deleted, _ = qs.delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} {label}'))
