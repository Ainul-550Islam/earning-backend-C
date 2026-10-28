# api/support/management/commands/seed_kb_categories.py
"""Seed default KB categories and starter articles."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed KB categories and starter articles'

    def handle(self, *args, **options):
        from api.support.models import KBCategory, KBArticle
        from django.utils.text import slugify
        import time

        categories = [
            {'name': 'Getting Started',     'icon': '🚀', 'sort_order': 1},
            {'name': 'Payments & Earnings', 'icon': '💰', 'sort_order': 2},
            {'name': 'Withdrawal',          'icon': '💸', 'sort_order': 3},
            {'name': 'Account & Profile',   'icon': '👤', 'sort_order': 4},
            {'name': 'Offers & Tasks',      'icon': '🎯', 'sort_order': 5},
            {'name': 'KYC Verification',    'icon': '🪪', 'sort_order': 6},
            {'name': 'Referral Program',    'icon': '👥', 'sort_order': 7},
            {'name': 'Technical Issues',    'icon': '🔧', 'sort_order': 8},
            {'name': 'Security',            'icon': '🔒', 'sort_order': 9},
            {'name': 'Troubleshooting',     'icon': '🛠️', 'sort_order': 10},
        ]

        created = 0
        for cat_data in categories:
            slug = slugify(cat_data['name'])
            obj, c = KBCategory.objects.get_or_create(
                slug=slug,
                defaults={**cat_data, 'is_active': True}
            )
            if c:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {cat_data['icon']} {obj.name}"))
            else:
                self.stdout.write(f"  Exists: {obj.name}")

        self.stdout.write(self.style.SUCCESS(f"Done: {created} KB categories created"))