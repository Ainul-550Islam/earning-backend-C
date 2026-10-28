# api/djoyalty/management/commands/reset_streaks.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Reset broken streaks for customers who missed activity days.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be reset without applying.')
        parser.add_argument('--days-grace', type=int, default=1, help='Grace period in days before reset.')

    def handle(self, *args, **options):
        from djoyalty.models.engagement import DailyStreak
        from django.utils import timezone
        from datetime import timedelta

        dry_run = options['dry_run']
        grace_days = options['days_grace']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN -- no changes will be applied.'))

        cutoff = timezone.now().date() - timedelta(days=grace_days)
        broken = DailyStreak.objects.filter(
            is_active=True,
            last_activity_date__lt=cutoff,
        ).exclude(last_activity_date__isnull=True)

        count = broken.count()
        self.stdout.write(f'Found {count} broken streaks (last activity before {cutoff}).')

        if not dry_run and count > 0:
            broken.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'Reset {count} broken streaks.'))
        elif dry_run:
            for streak in broken[:20]:
                self.stdout.write(
                    f'  Would reset: {streak.customer.code} | '
                    f'streak={streak.current_streak} | '
                    f'last_activity={streak.last_activity_date}'
                )
            if count > 20:
                self.stdout.write(f'  ... and {count - 20} more.')

        self.stdout.write(self.style.SUCCESS('Done.'))
