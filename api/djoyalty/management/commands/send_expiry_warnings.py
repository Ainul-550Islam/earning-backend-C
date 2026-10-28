# api/djoyalty/management/commands/send_expiry_warnings.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Send points expiry warning notifications to customers।'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7,
                            help='Warn customers whose points expire within N days (default: 7)')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from datetime import timedelta
        from django.utils import timezone
        from djoyalty.models.points import PointsExpiry
        from djoyalty.services.NotificationService import NotificationService

        days = options['days']
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING(f'DRY RUN -- {days} days warning'))

        cutoff = timezone.now() + timedelta(days=days)
        expiring = PointsExpiry.objects.filter(
            is_expired=False,
            expiry_date__lte=cutoff,
            expiry_date__gt=timezone.now(),
            points_remaining__gt=0,
        ).select_related('customer').order_by('expiry_date')

        total = expiring.count()
        self.stdout.write(f'Found {total} expiring points records')

        sent = 0
        for exp in expiring.iterator(chunk_size=50):
            days_left = (exp.expiry_date.date() - timezone.now().date()).days
            self.stdout.write(
                f'  {exp.customer.code}: {exp.points_remaining} pts in {days_left} days'
            )
            if not dry:
                NotificationService.notify_points_expiring(
                    exp.customer, exp.points_remaining, days_left
                )
                sent += 1

        if dry:
            self.stdout.write(self.style.WARNING(f'Would send {total} warnings'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Sent {sent} expiry warnings'))
