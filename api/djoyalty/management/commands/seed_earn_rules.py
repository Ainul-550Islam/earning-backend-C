# api/djoyalty/management/commands/seed_earn_rules.py
from django.core.management.base import BaseCommand
from decimal import Decimal


DEFAULT_EARN_RULES = [
    {
        'name': 'Standard Purchase Earn',
        'rule_type': 'percentage',
        'trigger': 'purchase',
        'points_value': Decimal('1'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'priority': 10,
        'description': 'Earn 1 point per 1 currency unit spent.',
    },
    {
        'name': 'First Purchase Bonus',
        'rule_type': 'fixed',
        'trigger': 'purchase',
        'points_value': Decimal('100'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'max_per_day': Decimal('100'),
        'priority': 20,
        'description': 'Bonus 100 points on first purchase.',
    },
    {
        'name': 'Referral Signup Bonus',
        'rule_type': 'fixed',
        'trigger': 'referral',
        'points_value': Decimal('200'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'priority': 15,
        'description': 'Earn 200 points when a referral signs up.',
    },
    {
        'name': 'Login Bonus',
        'rule_type': 'fixed',
        'trigger': 'login',
        'points_value': Decimal('5'),
        'multiplier': Decimal('1'),
        'max_per_day': Decimal('5'),
        'min_spend': Decimal('0'),
        'priority': 5,
        'description': 'Earn 5 points per daily login.',
    },
    {
        'name': 'Birthday Bonus',
        'rule_type': 'fixed',
        'trigger': 'birthday',
        'points_value': Decimal('500'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'priority': 30,
        'description': 'Birthday bonus: 500 points.',
    },
    {
        'name': 'Signup Welcome Bonus',
        'rule_type': 'fixed',
        'trigger': 'signup',
        'points_value': Decimal('50'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'max_per_day': Decimal('50'),
        'priority': 25,
        'description': '50 welcome points on account creation.',
    },
]


class Command(BaseCommand):
    help = 'Seed default earn rules.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete all existing earn rules first.')

    def handle(self, *args, **options):
        from djoyalty.models.earn_rules import EarnRule

        if options['reset']:
            deleted = EarnRule.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing earn rules: {deleted}'))

        created_count = 0
        for rule_data in DEFAULT_EARN_RULES:
            _, created = EarnRule.objects.get_or_create(
                name=rule_data['name'],
                defaults={k: v for k, v in rule_data.items() if k != 'name'},
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {rule_data["name"]}'))
            else:
                self.stdout.write(f'  Exists: {rule_data["name"]}')

        self.stdout.write(self.style.SUCCESS(f'\nSeeded {created_count} new earn rules.'))
