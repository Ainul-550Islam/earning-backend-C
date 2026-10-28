# api/admin_panel/test_data_seeder.py
"""Seed realistic test data for staging environment."""
from __future__ import annotations
import logging, random
from django.utils import timezone

logger = logging.getLogger(__name__)

class TestDataSeeder:
    @classmethod
    def seed_all(cls, user_count: int = 100) -> dict:
        results = {}
        results['users']  = cls.seed_users(user_count)
        results['offers'] = cls.seed_offers(20)
        results['config'] = cls.seed_config()
        return results

    @classmethod
    def seed_users(cls, count: int = 100) -> int:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        created = 0
        for i in range(count):
            u, c = User.objects.get_or_create(
                username=f'test_user_{i:04d}',
                defaults={'email': f'test{i:04d}@example.com', 'is_active': True}
            )
            if c:
                u.set_password('testpass123')
                u.save()
                created += 1
        return created

    @classmethod
    def seed_offers(cls, count: int = 20) -> int:
        try:
            from api.offer_inventory.models import Offer
            created = 0
            for i in range(count):
                _, c = Offer.objects.get_or_create(
                    title=f'Test Offer {i:03d}',
                    defaults={'payout': round(random.uniform(0.1, 5.0), 2),
                               'offer_type': 'cpa', 'is_active': True}
                )
                if c: created += 1
            return created
        except Exception: return 0

    @classmethod
    def seed_config(cls) -> bool:
        from api.admin_panel.system_initializer import system_initializer
        system_initializer._seed_system_config()
        system_initializer._seed_feature_flags()
        return True

test_seeder = TestDataSeeder()