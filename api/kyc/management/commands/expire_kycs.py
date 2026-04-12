# kyc/management/commands/expire_kycs.py  ── WORLD #1
"""Management command: python manage.py expire_kycs"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Expire overdue verified KYCs and notify users'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be expired without saving')
        parser.add_argument('--notify', action='store_true', default=True, help='Send expiry notifications')

    def handle(self, *args, **options):
        from api.kyc.models import KYC
        dry_run = options['dry_run']
        notify  = options['notify']

        overdue = KYC.objects.filter(status='verified', expires_at__lt=timezone.now())
        count   = overdue.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] {count} KYC records would be expired'))
            for kyc in overdue[:10]:
                self.stdout.write(f'  - KYC #{kyc.id}: {kyc.user.username} (expired {kyc.expires_at})')
            return

        expired_ids = []
        for kyc in overdue:
            kyc.status = 'expired'
            kyc.save(update_fields=['status', 'updated_at'])
            expired_ids.append(kyc.id)

            if notify:
                try:
                    from api.kyc.services import KYCNotificationService
                    KYCNotificationService.send(user=kyc.user, event_type='kyc_expired', kyc=kyc)
                except Exception as e:
                    self.stderr.write(f'Notification failed for KYC #{kyc.id}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Expired {len(expired_ids)} KYC records: {expired_ids[:10]}'))
