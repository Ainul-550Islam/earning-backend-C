# kyc/tests/test_views.py  ── WORLD #1
"""API endpoint tests for KYC views."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .factories import make_user, make_kyc, make_blacklist_entry


class KYCStatusViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user   = make_user()
        self.client.force_authenticate(user=self.user)

    def test_status_not_submitted(self):
        resp = self.client.get('/api/kyc/status/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'not_submitted')

    def test_status_unauthenticated(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/kyc/status/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_health_check(self):
        resp = self.client.get('/api/kyc/health/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'ok')


class KYCAdminListViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin  = make_user(username='admin', is_staff=True)
        self.user1  = make_user(username='user1')
        self.user2  = make_user(username='user2')
        make_kyc(self.user1, status='pending')
        make_kyc(self.user2, status='verified')
        self.client.force_authenticate(user=self.admin)

    def test_admin_list_returns_all(self):
        resp = self.client.get('/api/kyc/admin/list/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_admin_list_filter_by_status(self):
        resp = self.client.get('/api/kyc/admin/list/?status=pending')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_admin_list_requires_admin(self):
        normal_user = make_user(username='normaluser')
        self.client.force_authenticate(user=normal_user)
        resp = self.client.get('/api/kyc/admin/list/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_stats(self):
        resp = self.client.get('/api/kyc/admin/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total', resp.data)
        self.assertIn('pending', resp.data)
        self.assertEqual(resp.data['total'], 2)


class KYCAdminReviewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin  = make_user(username='admin2', is_staff=True)
        self.user   = make_user()
        self.kyc    = make_kyc(self.user, status='pending')
        self.client.force_authenticate(user=self.admin)

    def test_approve_kyc(self):
        resp = self.client.post(f'/api/kyc/admin/review/{self.kyc.id}/', {'status': 'verified'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'verified')

    def test_reject_kyc_without_reason_fails(self):
        resp = self.client.post(f'/api/kyc/admin/review/{self.kyc.id}/', {'status': 'rejected'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_kyc_with_reason(self):
        resp = self.client.post(f'/api/kyc/admin/review/{self.kyc.id}/',
                                {'status': 'rejected', 'rejection_reason': 'Invalid document'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'rejected')

    def test_reset_kyc(self):
        self.kyc.status = 'rejected'; self.kyc.save()
        resp = self.client.post(f'/api/kyc/admin/reset/{self.kyc.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'pending')


class KYCBlacklistViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin  = make_user(username='bladmin', is_staff=True)
        self.client.force_authenticate(user=self.admin)

    def test_add_blacklist_entry(self):
        resp = self.client.post('/api/kyc/blacklist/',
                                {'type': 'phone', 'value': '01700000000', 'reason': 'Fraud'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_blacklist_check_true(self):
        make_blacklist_entry('phone', '01700000001')
        resp = self.client.post('/api/kyc/blacklist/check/',
                                {'type': 'phone', 'value': '01700000001'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_blacklisted'])

    def test_blacklist_check_false(self):
        resp = self.client.post('/api/kyc/blacklist/check/',
                                {'type': 'phone', 'value': '01800000000'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['is_blacklisted'])
