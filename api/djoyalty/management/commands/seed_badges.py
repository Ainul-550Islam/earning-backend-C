# api/djoyalty/management/commands/seed_badges.py
from django.core.management.base import BaseCommand
from decimal import Decimal


DEFAULT_BADGES = [
    {'name': 'First Step',      'icon': '👣', 'rarity': 'common',    'trigger': 'transaction_count', 'threshold': Decimal('1'),    'points_reward': Decimal('50'),   'description': 'Complete your first transaction.'},
    {'name': 'Regular Buyer',   'icon': '🛒', 'rarity': 'common',    'trigger': 'transaction_count', 'threshold': Decimal('10'),   'points_reward': Decimal('100'),  'description': 'Complete 10 transactions.'},
    {'name': 'Power Shopper',   'icon': '💪', 'rarity': 'rare',      'trigger': 'transaction_count', 'threshold': Decimal('50'),   'points_reward': Decimal('250'),  'description': 'Complete 50 transactions.'},
    {'name': 'Century Club',    'icon': '💯', 'rarity': 'epic',      'trigger': 'transaction_count', 'threshold': Decimal('100'),  'points_reward': Decimal('500'),  'description': 'Complete 100 transactions.'},
    {'name': 'Big Spender',     'icon': '💰', 'rarity': 'rare',      'trigger': 'total_spend',       'threshold': Decimal('10000'),'points_reward': Decimal('300'),  'description': 'Spend 10,000 in total.'},
    {'name': 'High Roller',     'icon': '🎰', 'rarity': 'epic',      'trigger': 'total_spend',       'threshold': Decimal('50000'),'points_reward': Decimal('1000'), 'description': 'Spend 50,000 in total.'},
    {'name': 'Week Warrior',    'icon': '🔥', 'rarity': 'common',    'trigger': 'streak_days',       'threshold': Decimal('7'),    'points_reward': Decimal('50'),   'description': 'Maintain a 7-day streak.'},
    {'name': 'Monthly Master',  'icon': '📅', 'rarity': 'rare',      'trigger': 'streak_days',       'threshold': Decimal('30'),   'points_reward': Decimal('200'),  'description': 'Maintain a 30-day streak.'},
    {'name': 'Century Streak',  'icon': '🏆', 'rarity': 'legendary', 'trigger': 'streak_days',       'threshold': Decimal('100'),  'points_reward': Decimal('1000'), 'description': 'Maintain a 100-day streak.'},
    {'name': 'Points Pro',      'icon': '⭐', 'rarity': 'common',    'trigger': 'total_points',      'threshold': Decimal('1000'), 'points_reward': Decimal('100'),  'description': 'Earn 1,000 total points.'},
    {'name': 'Points Elite',    'icon': '🌟', 'rarity': 'rare',      'trigger': 'total_points',      'threshold': Decimal('10000'),'points_reward': Decimal('500'),  'description': 'Earn 10,000 total points.'},
    {'name': 'Points Legend',   'icon': '💎', 'rarity': 'legendary', 'trigger': 'total_points',      'threshold': Decimal('100000'),'points_reward': Decimal('5000'), 'description': 'Earn 100,000 total points.'},
    {'name': 'Connector',       'icon': '🤝', 'rarity': 'rare',      'trigger': 'referral_count',    'threshold': Decimal('3'),    'points_reward': Decimal('300'),  'description': 'Refer 3 friends.'},
    {'name': 'Super Referrer',  'icon': '📣', 'rarity': 'epic',      'trigger': 'referral_count',    'threshold': Decimal('10'),   'points_reward': Decimal('1000'), 'description': 'Refer 10 friends.'},
    {'name': 'Silver Achiever', 'icon': '🥈', 'rarity': 'common',    'trigger': 'tier_achieved',     'threshold': Decimal('2'),    'points_reward': Decimal('100'),  'description': 'Reach Silver tier.'},
    {'name': 'Gold Star',       'icon': '🌠', 'rarity': 'rare',      'trigger': 'tier_achieved',     'threshold': Decimal('3'),    'points_reward': Decimal('300'),  'description': 'Reach Gold tier.'},
    {'name': 'Platinum Player', 'icon': '🎖️', 'rarity': 'epic',      'trigger': 'tier_achieved',     'threshold': Decimal('4'),    'points_reward': Decimal('1000'), 'description': 'Reach Platinum tier.'},
    {'name': 'Diamond King',    'icon': '👑', 'rarity': 'legendary', 'trigger': 'tier_achieved',     'threshold': Decimal('5'),    'points_reward': Decimal('5000'), 'description': 'Reach Diamond tier.'},
]


class Command(BaseCommand):
    help = 'Seed default badge set.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete all existing badges first.')

    def handle(self, *args, **options):
        from djoyalty.models.engagement import Badge

        if options['reset']:
            deleted = Badge.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing badges: {deleted}'))

        created_count = 0
        for i, data in enumerate(DEFAULT_BADGES):
            _, created = Badge.objects.get_or_create(
                name=data['name'],
                defaults={
                    'icon': data['icon'],
                    'rarity': data['rarity'],
                    'trigger': data['trigger'],
                    'threshold': data['threshold'],
                    'points_reward': data['points_reward'],
                    'description': data['description'],
                    'is_active': True,
                    'is_unique': True,
                    'sort_order': i,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {data["name"]} [{data["rarity"]}]'))
            else:
                self.stdout.write(f'  Exists: {data["name"]}')

        self.stdout.write(self.style.SUCCESS(f'\nSeeded {created_count} new badges. Total={len(DEFAULT_BADGES)}'))
