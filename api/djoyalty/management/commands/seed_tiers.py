# api/djoyalty/management/commands/seed_tiers.py
from django.core.management.base import BaseCommand
from decimal import Decimal

TIER_DEFAULTS = [
    {'name': 'bronze', 'label': 'Bronze', 'min_points': Decimal('0'), 'earn_multiplier': Decimal('1.0'), 'color': '#92400e', 'icon': '🥉', 'rank': 1},
    {'name': 'silver', 'label': 'Silver', 'min_points': Decimal('500'), 'earn_multiplier': Decimal('1.25'), 'color': '#6b7280', 'icon': '🥈', 'rank': 2},
    {'name': 'gold', 'label': 'Gold', 'min_points': Decimal('2000'), 'earn_multiplier': Decimal('1.5'), 'color': '#d97706', 'icon': '🥇', 'rank': 3},
    {'name': 'platinum', 'label': 'Platinum', 'min_points': Decimal('5000'), 'earn_multiplier': Decimal('2.0'), 'color': '#1d4ed8', 'icon': '💎', 'rank': 4},
    {'name': 'diamond', 'label': 'Diamond', 'min_points': Decimal('10000'), 'earn_multiplier': Decimal('3.0'), 'color': '#7c3aed', 'icon': '💠', 'rank': 5},
]

class Command(BaseCommand):
    help = 'Seed default loyalty tiers (Bronze → Diamond)'

    def handle(self, *args, **options):
        from djoyalty.models.tiers import LoyaltyTier
        created = 0
        for tier_data in TIER_DEFAULTS:
            obj, was_created = LoyaltyTier.objects.update_or_create(name=tier_data['name'], defaults=tier_data)
            if was_created:
                created += 1
                self.stdout.write(f'  Created: {obj}')
            else:
                self.stdout.write(f'  Updated: {obj}')
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(TIER_DEFAULTS)} tiers ({created} new).'))
