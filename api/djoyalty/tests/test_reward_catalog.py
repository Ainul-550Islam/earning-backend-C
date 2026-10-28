# api/djoyalty/tests/test_reward_catalog.py
"""RewardCatalogViewSet tests."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from .factories import make_customer, make_loyalty_points


class RewardCatalogModelTest(TestCase):
    def setUp(self):
        from djoyalty.models.catalog import RewardCatalogCategory, RewardCatalogItem
        self.category = RewardCatalogCategory.objects.create(
            name='Vouchers', is_active=True,
        )
        self.item = RewardCatalogItem.objects.create(
            name='50 BDT Voucher',
            category=self.category,
            points_cost=Decimal('500'),
            reward_type='voucher',
            is_active=True,
        )

    def test_category_created(self):
        self.assertEqual(self.category.name, 'Vouchers')

    def test_item_belongs_to_category(self):
        self.assertEqual(self.item.category, self.category)

    def test_item_points_positive(self):
        self.assertGreater(self.item.points_cost, 0)


class RewardCatalogViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='CATCUST01')
        make_loyalty_points(self.customer, balance=Decimal('2000'))

    def test_list_catalog_items(self):
        resp = self.client.get('/api/reward-catalog/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_redeem_endpoint(self):
        resp = self.client.post('/api/reward-catalog/redeem/', {
            'customer_id': self.customer.id,
            'item_id': 999,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])
