# api/djoyalty/management/commands/expire_points.py
"""
Management command: manually run points expiry processing।
Usage: python manage.py expire_points [--dry-run]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Process expired loyalty points and deduct from customer balances.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Show what would be processed without making changes.',
        )
        parser.add_argument(
            '--send-warnings',
            action='store_true',
            dest='send_warnings',
            help='Also send expiry warning notifications.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        send_warnings = options['send_warnings']

        self.stdout.write(self.style.NOTICE('Starting points expiry processing...'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN mode -- no changes will be made.'))
            from djoyalty.models.points import PointsExpiry
            from django.utils import timezone
            due_count = PointsExpiry.objects.filter(
                expires_at__lte=timezone.now(), is_processed=False
            ).count()
            self.stdout.write(f'Would process {due_count} expiry records.')
            return

        from djoyalty.services.points.PointsExpiryService import PointsExpiryService

        try:
            count = PointsExpiryService.process_expired_points()
            self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} expiry records.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error processing expiry: {e}'))
            raise

        if send_warnings:
            try:
                warned = PointsExpiryService.send_expiry_warnings()
                self.stdout.write(self.style.SUCCESS(f'Sent {warned} expiry warning notifications.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error sending warnings: {e}'))
