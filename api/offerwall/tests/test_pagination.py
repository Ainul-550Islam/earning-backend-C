"""
tests/test_pagination.py

Tests for offerwall pagination classes:
  - StandardPagination
  - LargePagination
  - SmallPagination

Run: python manage.py test api.offerwall.tests.test_pagination
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.request import Request

User = get_user_model()


def make_user():
    return User.objects.create_user('pagtest', password='pass')


def make_provider():
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name='PagProv', provider_type='tapjoy', status='active',
        api_key='k', revenue_share=Decimal('70'))


def make_offers(provider, n=30):
    from api.offerwall.models import Offer
    offers = []
    for i in range(n):
        offers.append(Offer(
            provider=provider,
            external_offer_id=f'PAG{i:03d}',
            title=f'Offer {i}',
            payout=Decimal('1.00'),
            reward_amount=Decimal('0.70'),
            status='active',
        ))
    Offer.objects.bulk_create(offers)


# ─────────────────────────────────────────────────────────────────────────────
# StandardPagination
# ─────────────────────────────────────────────────────────────────────────────

class StandardPaginationUnitTest(TestCase):
    def setUp(self):
        from api.offerwall.pagination import StandardPagination
        self.pag = StandardPagination()

    def test_default_page_size(self):
        self.assertEqual(self.pag.page_size, 20)

    def test_max_page_size(self):
        self.assertEqual(self.pag.max_page_size, 100)

    def test_page_size_query_param(self):
        self.assertEqual(self.pag.page_size_query_param, 'page_size')


class StandardPaginationAPITest(TestCase):
    def setUp(self):
        self.factory  = APIRequestFactory()
        self.user     = make_user()
        self.provider = make_provider()
        make_offers(self.provider, 30)

    def test_list_returns_paginated_response(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get('/api/offerwall/offers/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('results', resp.data)
        self.assertIn('count', resp.data)
        self.assertIn('next', resp.data)
        self.assertIn('previous', resp.data)
        self.assertIn('total_pages', resp.data)
        self.assertIn('current_page', resp.data)

    def test_default_page_size_20(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get('/api/offerwall/offers/')
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.data['results']), 20)

    def test_custom_page_size_respected(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get('/api/offerwall/offers/?page_size=5')
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.data['results']), 5)

    def test_page_size_cannot_exceed_max(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get('/api/offerwall/offers/?page_size=999')
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.data['results']), 100)

    def test_page_2_different_from_page_1(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        r1 = client.get('/api/offerwall/offers/?page=1&page_size=5')
        r2 = client.get('/api/offerwall/offers/?page=2&page_size=5')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        ids1 = {o['id'] for o in r1.data['results']}
        ids2 = {o['id'] for o in r2.data['results']}
        self.assertEqual(ids1 & ids2, set())  # no overlap

    def test_invalid_page_returns_404(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get('/api/offerwall/offers/?page=9999')
        self.assertEqual(resp.status_code, 404)

    def test_count_reflects_total_records(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get('/api/offerwall/offers/')
        self.assertEqual(resp.data['count'], 30)


# ─────────────────────────────────────────────────────────────────────────────
# LargePagination
# ─────────────────────────────────────────────────────────────────────────────

class LargePaginationUnitTest(TestCase):
    def setUp(self):
        from api.offerwall.pagination import LargePagination
        self.pag = LargePagination()

    def test_default_page_size_50(self):
        self.assertEqual(self.pag.page_size, 50)

    def test_max_page_size_200(self):
        self.assertEqual(self.pag.max_page_size, 200)

    def test_page_size_query_param(self):
        self.assertEqual(self.pag.page_size_query_param, 'page_size')


# ─────────────────────────────────────────────────────────────────────────────
# SmallPagination
# ─────────────────────────────────────────────────────────────────────────────

class SmallPaginationUnitTest(TestCase):
    def setUp(self):
        from api.offerwall.pagination import SmallPagination
        self.pag = SmallPagination()

    def test_default_page_size_10(self):
        self.assertEqual(self.pag.page_size, 10)

    def test_max_page_size_50(self):
        self.assertEqual(self.pag.max_page_size, 50)

    def test_categories_use_small_pagination(self):
        from rest_framework.test import APIClient
        user = User.objects.create_user('catpag', password='p')
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get('/api/offerwall/categories/')
        self.assertEqual(resp.status_code, 200)
        # Categories endpoint uses SmallPagination
        self.assertIn('results', resp.data)
