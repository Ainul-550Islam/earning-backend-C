# api/djoyalty/management/commands/seed_tiers.py
from django.core.management.base import BaseCommand
from decimal import Decimal


TIER_DATA = [
    {'name': 'bronze',   'label': 'Bronze',   'rank': 1, 'min_points': Decimal('0'),     'earn_multiplier': Decimal('1.0'),  'color': '#CD7F32', 'icon': '🥉'},
    {'name': 'silver',   'label': 'Silver',   'rank': 2, 'min_points': Decimal('500'),   'earn_multiplier': Decimal('1.2'),  'color': '#C0C0C0', 'icon': '🥈'},
    {'name': 'gold',     'label': 'Gold',     'rank': 3, 'min_points': Decimal('2000'),  'earn_multiplier': Decimal('1.5'),  'color': '#FFD700', 'icon': '🥇'},
    {'name': 'platinum', 'label': 'Platinum', 'rank': 4, 'min_points': Decimal('10000'), 'earn_multiplier': Decimal('2.0'),  'color': '#E5E4E2', 'icon': '💎'},
    {'name': 'diamond',  'label': 'Diamond',  'rank': 5, 'min_points': Decimal('50000'), 'earn_multiplier': Decimal('3.0'),  'color': '#B9F2FF', 'icon': '💠'},
]

TIER_BENEFITS = {
    'bronze':   ['Welcome Bonus Points', 'Birthday Points'],
    'silver':   ['1.2x Points Multiplier', 'Priority Support', 'Free Shipping on 500+ orders'],
    'gold':     ['1.5x Points Multiplier', 'Dedicated Account Manager', 'Free Shipping on all orders', 'Exclusive Offers'],
    'platinum': ['2x Points Multiplier', 'VIP Events Access', 'Free Shipping Always', 'Personal Shopper', 'Quarterly Gift'],
    'diamond':  ['3x Points Multiplier', 'Concierge Service', 'Annual Gift', 'Invitation-only Events', 'Free Priority Express'],
}


class Command(BaseCommand):
    help = 'Seed default loyalty tiers (bronze/silver/gold/platinum/diamond).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete all existing tiers first.')
        parser.add_argument('--with-benefits', action='store_true', default=True, help='Also seed tier benefits.')

    def handle(self, *args, **options):
        from djoyalty.models.tiers import LoyaltyTier, TierBenefit

        if options['reset']:
            deleted = LoyaltyTier.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing tiers: {deleted}'))

        created_count = 0
        updated_count = 0

        for data in TIER_DATA:
            tier, created = LoyaltyTier.objects.update_or_create(
                name=data['name'],
                defaults={
                    'label': data['label'],
                    'rank': data['rank'],
                    'min_points': data['min_points'],
                    'earn_multiplier': data['earn_multiplier'],
                    'color': data['color'],
                    'icon': data['icon'],
                    'is_active': True,
                    'sort_order': data['rank'],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created tier: {tier.label}'))
            else:
                updated_count += 1
                self.stdout.write(f'  Updated tier: {tier.label}')

            if options['with_benefits']:
                for benefit_title in TIER_BENEFITS.get(data['name'], []):
                    TierBenefit.objects.get_or_create(
                        tier=tier,
                        title=benefit_title,
                        defaults={'benefit_type': 'perk', 'is_active': True},
                    )

        self.stdout.write(self.style.SUCCESS(
            f'\nSeeding complete. Created={created_count}, Updated={updated_count}'
        ))
