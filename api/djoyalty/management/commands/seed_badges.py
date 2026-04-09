# api/djoyalty/management/commands/seed_badges.py
from django.core.management.base import BaseCommand
from decimal import Decimal

BADGE_DEFAULTS = [
    {'name': 'First Purchase', 'icon': '🎉', 'trigger': 'transaction_count', 'threshold': Decimal('1'), 'points_reward': Decimal('50')},
    {'name': 'Loyal Shopper', 'icon': '💪', 'trigger': 'transaction_count', 'threshold': Decimal('10'), 'points_reward': Decimal('100')},
    {'name': 'Century Club', 'icon': '💯', 'trigger': 'transaction_count', 'threshold': Decimal('100'), 'points_reward': Decimal('500')},
    {'name': 'Big Spender', 'icon': '💸', 'trigger': 'total_spend', 'threshold': Decimal('1000'), 'points_reward': Decimal('200')},
    {'name': 'Week Warrior', 'icon': '🔥', 'trigger': 'streak_days', 'threshold': Decimal('7'), 'points_reward': Decimal('50')},
    {'name': 'Month Master', 'icon': '🏆', 'trigger': 'streak_days', 'threshold': Decimal('30'), 'points_reward': Decimal('200')},
]

class Command(BaseCommand):
    help = 'Seed default badges'

    def handle(self, *args, **options):
        from djoyalty.models.engagement import Badge
        created = 0
        for data in BADGE_DEFAULTS:
            obj, was_created = Badge.objects.update_or_create(name=data['name'], defaults=data)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(BADGE_DEFAULTS)} badges ({created} new).'))
