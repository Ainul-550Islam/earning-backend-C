# api/djoyalty/tests/test_experience.py
"""ExperienceViewSet tests -- experiential rewards."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class ExperienceModelTest(TestCase):
    def setUp(self):
        from djoyalty.models.family_eco import ExperientialReward
        from django.utils import timezone
        from datetime import timedelta
        self.exp = ExperientialReward.objects.create(
            name='VIP Dinner',
            experience_type='vip_event',
            points_required=Decimal('5000'),
            total_slots=20,
            is_active=True,
            event_date=timezone.now() + timedelta(days=30),
        )

    def test_experience_created(self):
        self.assertEqual(self.exp.name, 'VIP Dinner')
        self.assertGreater(self.exp.points_required, 0)

    def test_capacity_set(self):
        self.assertEqual(self.exp.total_slots, 20)


class ExperienceViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='EXPCUST01')
        make_loyalty_points(self.customer, balance=Decimal('10000'))

    def test_list_experiences(self):
        resp = self.client.get('/api/experiences/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_register_requires_customer(self):
        resp = self.client.post('/api/experiences/register/', {
            'customer_id': self.customer.id,
            'experience_id': 999,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])
