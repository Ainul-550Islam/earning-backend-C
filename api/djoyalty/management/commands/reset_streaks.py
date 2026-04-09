# api/djoyalty/management/commands/reset_streaks.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Reset broken streaks'

    def handle(self, *args, **options):
        from django.utils import timezone
        from datetime import timedelta
        from djoyalty.models.engagement import DailyStreak
        yesterday = timezone.now().date() - timedelta(days=1)
        count = DailyStreak.objects.filter(is_active=True, last_activity_date__lt=yesterday).exclude(last_activity_date__isnull=True).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'Reset {count} broken streaks.'))
