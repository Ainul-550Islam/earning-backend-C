# api/djoyalty/management/commands/expire_points.py
"""Management command: Process expired loyalty points।"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Process expired loyalty points and deduct them from customer balances'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be expired without making any changes',
        )
        parser.add_argument(
            '--send-warnings',
            action='store_true',
            help='Also send expiry warning notifications for soon-to-expire points',
        )

    def handle(self, *args, **options):
        from djoyalty.services.points.PointsExpiryService import PointsExpiryService
        from djoyalty.models.points import PointsExpiry
        from django.utils import timezone

        dry_run = options.get('dry_run', False)
        send_warnings = options.get('send_warnings', False)

        if dry_run:
            due = PointsExpiry.objects.filter(
                expires_at__lte=timezone.now(), is_processed=False
            )
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would process {due.count()} expiry records.'
            ))
            for record in due[:20]:
                self.stdout.write(
                    f'  → Customer: {record.customer} | Points: {record.points} | Expired: {record.expires_at}'
                )
            return

        self.stdout.write('Processing expired points...')
        try:
            count = PointsExpiryService.process_expired_points()
            self.stdout.write(self.style.SUCCESS(f'✅ Processed {count} expiry records.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error processing expiries: {e}'))
            raise

        if send_warnings:
            self.stdout.write('Sending expiry warning notifications...')
            try:
                warned = PointsExpiryService.send_expiry_warnings()
                self.stdout.write(self.style.SUCCESS(f'✅ Sent {warned} expiry warnings.'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error sending warnings: {e}'))
