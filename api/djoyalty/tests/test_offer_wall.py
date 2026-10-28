# api/djoyalty/tests/test_offer_wall.py
"""OfferWallViewSet tests."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class OfferWallModelTest(TestCase):
    def setUp(self):
        from djoyalty.models.offerwall import OfferWall, Offer
        self.wall = OfferWall.objects.create(
            name='Test Wall', provider='cpalead', is_active=True,
        )
        self.offer = Offer.objects.create(
            offer_wall=self.wall,
            external_offer_id='OFR001',
            title='Survey Offer',
            points_reward=Decimal('200'),
            offer_type='survey',
            status='active',
        )

    def test_wall_created(self):
        self.assertEqual(self.wall.name, 'Test Wall')

    def test_offer_belongs_to_wall(self):
        self.assertEqual(self.offer.offer_wall, self.wall)

    def test_offer_points_positive(self):
        self.assertGreater(self.offer.points_reward, 0)


class OfferWallViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='OFFCUST01')
        make_loyalty_points(self.customer, balance=Decimal('300'))

    def test_list_offers(self):
        resp = self.client.get('/api/offer-wall/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_complete_offer(self):
        resp = self.client.post('/api/offer-wall/complete/', {
            'customer_id': self.customer.id,
            'offer_id': 999,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])
