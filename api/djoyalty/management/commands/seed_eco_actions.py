# api/djoyalty/management/commands/seed_eco_actions.py
from django.core.management.base import BaseCommand
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed default eco/green loyalty actions।'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing and re-seed')

    def handle(self, *args, **options):
        from djoyalty.models.family_eco import EcoAction

        if options['reset']:
            EcoAction.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing eco actions'))

        eco_defaults = [
            {
                'name': 'Used Reusable Bag',
                'action_type': 'reusable_bag',
                'points_reward': Decimal('5'),
                'co2_saved_kg': Decimal('0.05'),
                'icon': '🛍️',
                'max_per_customer_per_day': 3,
            },
            {
                'name': 'Chose Carbon-Neutral Delivery',
                'action_type': 'carbon_neutral_delivery',
                'points_reward': Decimal('20'),
                'co2_saved_kg': Decimal('2.3'),
                'icon': '🌿',
                'max_per_customer_per_day': 1,
            },
            {
                'name': 'Paperless Receipt',
                'action_type': 'paperless_receipt',
                'points_reward': Decimal('3'),
                'co2_saved_kg': Decimal('0.01'),
                'icon': '📱',
                'max_per_customer_per_day': 5,
            },
            {
                'name': 'Recycled Product Packaging',
                'action_type': 'recycle',
                'points_reward': Decimal('15'),
                'co2_saved_kg': Decimal('0.8'),
                'icon': '♻️',
                'max_per_customer_per_day': 2,
            },
            {
                'name': 'Purchased Eco-Friendly Product',
                'action_type': 'eco_product',
                'points_reward': Decimal('25'),
                'co2_saved_kg': Decimal('1.5'),
                'icon': '🌱',
                'max_per_customer_per_day': 5,
            },
            {
                'name': 'Plant a Tree Contribution',
                'action_type': 'plant_tree',
                'points_reward': Decimal('100'),
                'co2_saved_kg': Decimal('21.77'),
                'icon': '🌳',
                'max_per_customer_per_day': 1,
            },
        ]

        created = 0
        for data in eco_defaults:
            _, was_created = EcoAction.objects.get_or_create(
                action_type=data['action_type'],
                defaults=data,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  ✅ {data["icon"]} {data["name"]}: +{data["points_reward"]} pts'
                ))
            else:
                self.stdout.write(f'  ⏭️  {data["name"]}: already exists')

        self.stdout.write(self.style.SUCCESS(f'\nSeeded {created} new eco actions'))
