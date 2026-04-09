# api/djoyalty/management/commands/seed_earn_rules.py
"""Seed default earn rules।"""
from django.core.management.base import BaseCommand
from decimal import Decimal

EARN_RULE_DEFAULTS = [
    {
        'name': 'Standard Purchase Rule',
        'rule_type': 'percentage',
        'trigger': 'purchase',
        'points_value': Decimal('1'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'is_active': True,
        'priority': 10,
        'description': 'Earn 1 point per 1 unit spent on all purchases.',
    },
    {
        'name': 'Sign Up Bonus',
        'rule_type': 'fixed',
        'trigger': 'signup',
        'points_value': Decimal('100'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'is_active': True,
        'priority': 100,
        'description': 'One-time sign up bonus of 100 points.',
    },
    {
        'name': 'Birthday Bonus',
        'rule_type': 'fixed',
        'trigger': 'birthday',
        'points_value': Decimal('200'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'is_active': True,
        'priority': 90,
        'description': 'Birthday bonus of 200 points.',
    },
    {
        'name': 'Referral Bonus (Referrer)',
        'rule_type': 'fixed',
        'trigger': 'referral',
        'points_value': Decimal('150'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'is_active': True,
        'priority': 80,
        'description': 'Earn 150 points for each successful referral.',
    },
    {
        'name': 'Review Reward',
        'rule_type': 'fixed',
        'trigger': 'review',
        'points_value': Decimal('25'),
        'multiplier': Decimal('1'),
        'min_spend': Decimal('0'),
        'is_active': True,
        'priority': 50,
        'description': 'Earn 25 points for writing a review.',
    },
]


class Command(BaseCommand):
    help = 'Seed default earn rules'

    def handle(self, *args, **options):
        from djoyalty.models.earn_rules import EarnRule
        created = 0
        updated = 0
        for rule_data in EARN_RULE_DEFAULTS:
            obj, was_created = EarnRule.objects.update_or_create(
                name=rule_data['name'],
                defaults=rule_data,
            )
            if was_created:
                created += 1
                self.stdout.write(f'  ✅ Created: {obj.name}')
            else:
                updated += 1
                self.stdout.write(f'  🔄 Updated: {obj.name}')
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(EARN_RULE_DEFAULTS)} earn rules ({created} new, {updated} updated).'
        ))
