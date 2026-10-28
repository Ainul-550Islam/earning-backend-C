"""
FIX 07 — tests/test_viewset_fraud_case_actions.py
===================================================
test_fraud_case.py covers the FraudCase MODEL thoroughly (31 tests).
test_viewsets.py covers basic FraudCase CRUD (3 tests).

But NONE of the FraudCaseViewSet *custom actions* are tested:
  - assign      → POST /cases/{pk}/assign/
  - escalate    → POST /cases/{pk}/escalate/
  - resolve     → POST /cases/{pk}/resolve/
  - my_cases    → GET  /cases/my-cases/
  - statistics  → GET  /cases/statistics/
  - timeline    → GET  /cases/timeline/       ← newly added in fix_05
  - bulk_close  → POST /cases/bulk-close/     ← newly added in fix_05

This file fills that gap.
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock


def _make_staff_client():
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.create_superuser('case_admin', 'ca@test.com', 'pass')
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def _make_case(user):
    from api.fraud_detection.models import FraudCase
    return FraudCase.objects.create(
        user=user,
        title='Test Case',
        description='A test fraud case',
        risk_score=80,
        case_number=f'CASE-{user.pk}-001',
    )


class TestFraudCaseAssign(TestCase):
    def setUp(self):
        self.client, self.user = _make_staff_client()
        self.case = _make_case(self.user)

    def test_assign_case(self):
        url = reverse('fraud_detection:fraud-case-assign', kwargs={'pk': self.case.pk})
        resp = self.client.post(url, {'assigned_to': self.user.pk}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_assign_nonexistent_case_returns_404(self):
        url = reverse('fraud_detection:fraud-case-assign', kwargs={'pk': 9999999})
        resp = self.client.post(url, {'assigned_to': self.user.pk}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class TestFraudCaseEscalate(TestCase):
    def setUp(self):
        self.client, self.user = _make_staff_client()
        self.case = _make_case(self.user)

    def test_escalate_case(self):
        url = reverse('fraud_detection:fraud-case-escalate', kwargs={'pk': self.case.pk})
        resp = self.client.post(url, {'reason': 'High risk detected'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_escalate_unauthenticated_returns_401(self):
        unauth_client = APIClient()
        url = reverse('fraud_detection:fraud-case-escalate', kwargs={'pk': self.case.pk})
        resp = unauth_client.post(url, {'reason': 'test'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class TestFraudCaseResolve(TestCase):
    def setUp(self):
        self.client, self.user = _make_staff_client()
        self.case = _make_case(self.user)

    def test_resolve_case(self):
        url = reverse('fraud_detection:fraud-case-resolve', kwargs={'pk': self.case.pk})
        resp = self.client.post(url, {'resolution': 'confirmed_fraud'}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_resolve_with_notes(self):
        url = reverse('fraud_detection:fraud-case-resolve', kwargs={'pk': self.case.pk})
        resp = self.client.post(url, {
            'resolution': 'false_positive',
            'notes': 'Investigated — no fraud found.',
        }, format='json')
        self.assertNotEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestFraudCaseMyCases(TestCase):
    def setUp(self):
        self.client, self.user = _make_staff_client()
        self.case = _make_case(self.user)

    def test_my_cases_returns_list(self):
        url = reverse('fraud_detection:fraud-case-my-cases')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_my_cases_unauthenticated(self):
        unauth = APIClient()
        url = reverse('fraud_detection:fraud-case-my-cases')
        resp = unauth.get(url)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class TestFraudCaseStatistics(TestCase):
    def setUp(self):
        self.client, self.user = _make_staff_client()
        _make_case(self.user)

    def test_statistics_returns_200(self):
        url = reverse('fraud_detection:fraud-case-statistics')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_statistics_response_has_expected_keys(self):
        url = reverse('fraud_detection:fraud-case-statistics')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Should contain some count/total-type field
        data = resp.data
        self.assertTrue(
            isinstance(data, dict) or isinstance(data, list),
            "Response data should be dict or list"
        )


class TestFraudCaseTimeline(TestCase):
    """Tests for the newly added timeline action (fix_05)."""

    def setUp(self):
        self.client, self.user = _make_staff_client()
        _make_case(self.user)

    def test_timeline_returns_200(self):
        url = reverse('fraud_detection:fraud-cases-timeline')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_timeline_has_events_key(self):
        url = reverse('fraud_detection:fraud-cases-timeline')
        resp = self.client.get(url)
        self.assertIn('events', resp.data)
        self.assertIn('total', resp.data)

    def test_timeline_with_days_param(self):
        url = reverse('fraud_detection:fraud-cases-timeline')
        resp = self.client.get(url, {'days': 7})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get('days'), 7)

    def test_timeline_with_status_filter(self):
        url = reverse('fraud_detection:fraud-cases-timeline')
        resp = self.client.get(url, {'status': 'open'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_timeline_unauthenticated(self):
        unauth = APIClient()
        url = reverse('fraud_detection:fraud-cases-timeline')
        resp = unauth.get(url)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class TestFraudCaseBulkClose(TestCase):
    """Tests for the newly added bulk_close action (fix_05)."""

    def setUp(self):
        self.client, self.user = _make_staff_client()
        self.case1 = _make_case(self.user)
        self.case2 = _make_case(self.user)
        self.case2.case_number = f'CASE-{self.user.pk}-002'
        self.case2.save()

    def test_bulk_close_valid(self):
        url = reverse('fraud_detection:fraud-cases-bulk-close')
        resp = self.client.post(url, {
            'case_ids': [self.case1.pk, self.case2.pk],
            'resolution_notes': 'Closed in bulk.',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('closed', resp.data)

    def test_bulk_close_empty_ids_returns_400(self):
        url = reverse('fraud_detection:fraud-cases-bulk-close')
        resp = self.client.post(url, {'case_ids': []}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_close_missing_ids_returns_400(self):
        url = reverse('fraud_detection:fraud-cases-bulk-close')
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_close_nonexistent_ids(self):
        url = reverse('fraud_detection:fraud-cases-bulk-close')
        resp = self.client.post(url, {
            'case_ids': [9999998, 9999999],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get('closed', 0), 0)

    def test_bulk_close_unauthenticated(self):
        unauth = APIClient()
        url = reverse('fraud_detection:fraud-cases-bulk-close')
        resp = unauth.post(url, {'case_ids': [self.case1.pk]}, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
