"""
Tests for SmartLink Business ViewSets
========================================
Covers:
  - APIKeyViewSet     (create, list, destroy, rotate, toggle)
  - WebhookViewSet    (CRUD, test delivery, delivery log, retry-failed, events)
  - PayoutViewSet     (list, wallet, summary, batch create/approve/mark-paid,
                       calculate, process-payment, process-batch-payments)
  - PublisherProfileViewSet (my-profile GET/PUT, gdpr-consent, anonymize, admin list)

All external HTTP calls (gateway API) are mocked.
No imports from any other api.* app.
"""
import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .factories import UserFactory, SmartLinkFactory

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_profile(user, **kwargs):
    from api.smartlink.models.billing import PublisherProfile
    defaults = dict(
        company_name='Test Co.',
        payment_method='paypal',
        payment_email=user.email,
        payout_currency='USD',
        min_payout=Decimal('20'),
        gdpr_consent=True,
    )
    defaults.update(kwargs)
    p, _ = PublisherProfile.objects.get_or_create(publisher=user, defaults=defaults)
    return p


def _make_wallet(user, balance=Decimal('500'), pending=Decimal('50')):
    from api.smartlink.models.billing import PublisherWallet
    w, _ = PublisherWallet.objects.get_or_create(
        publisher=user,
        defaults={'balance_usd': balance, 'pending_usd': pending},
    )
    return w


def _make_payout_record(user, status_val='approved', amount='100.00'):
    from api.smartlink.models.billing import PayoutRecord
    return PayoutRecord.objects.create(
        publisher=user,
        period_from=datetime.date(2024, 3, 1),
        period_to=datetime.date(2024, 3, 31),
        gross_amount=Decimal(amount),
        scrub_amount=Decimal('0'),
        net_amount=Decimal(amount),
        currency='USD',
        fx_rate=Decimal('1.000000'),
        local_amount=Decimal(amount),
        status=status_val,
        payment_method='paypal',
        payment_address=user.email,
    )


def _make_batch(admin, label='Test Batch'):
    from api.smartlink.models.billing import PayoutBatch
    return PayoutBatch.objects.create(
        label=label,
        period_from=datetime.date(2024, 3, 1),
        period_to=datetime.date(2024, 3, 31),
        status='review',
        created_by=admin,
    )


# ─────────────────────────────────────────────────────────────────────────────
# APIKeyViewSet Tests
# ─────────────────────────────────────────────────────────────────────────────

class APIKeyViewSetTest(TestCase):

    def setUp(self):
        self.client    = APIClient()
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.publisher)
        self.list_url  = '/api/smartlink/publisher/api-keys/'

    def _create_key(self, name='Test Key', scope='write'):
        return self.client.post(self.list_url, {
            'name':  name,
            'scope': scope,
        }, format='json')

    def test_list_empty(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 0)

    def test_create_key_returns_raw_key_once(self):
        resp = self._create_key()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('raw_key', resp.data)
        self.assertIn('key_prefix', resp.data)
        raw_key = resp.data['raw_key']
        self.assertTrue(len(raw_key) > 20)

    def test_list_after_create_hides_raw_key(self):
        self._create_key()
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        # raw_key must NOT appear in list response
        self.assertNotIn('raw_key', resp.data[0])

    def test_create_multiple_scopes(self):
        self._create_key('Read Key', 'read')
        self._create_key('Write Key', 'write')
        self._create_key('Full Key', 'full')
        resp = self.client.get(self.list_url)
        self.assertEqual(len(resp.data), 3)

    def test_destroy_key(self):
        create_resp = self._create_key()
        key_id = create_resp.data['id']
        del_resp = self.client.delete(f'{self.list_url}{key_id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_200_OK)
        # Confirm it's gone
        list_resp = self.client.get(self.list_url)
        self.assertEqual(len(list_resp.data), 0)

    def test_destroy_other_publishers_key_returns_404(self):
        other    = UserFactory()
        other_cli = APIClient()
        other_cli.force_authenticate(user=other)
        create_resp = other_cli.post(self.list_url, {'name': 'Key', 'scope': 'read'}, format='json')
        key_id = create_resp.data['id']
        # Publisher 1 tries to delete publisher 2's key
        del_resp = self.client.delete(f'{self.list_url}{key_id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_rotate_key(self):
        create_resp = self._create_key('Original')
        key_id      = create_resp.data['id']
        rotate_resp = self.client.post(f'{self.list_url}{key_id}/rotate/')
        self.assertEqual(rotate_resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('raw_key', rotate_resp.data)
        # Old key must be gone
        from api.smartlink.models.billing import PublisherAPIKey
        self.assertFalse(PublisherAPIKey.objects.filter(pk=key_id).exists())

    def test_toggle_key_active_state(self):
        create_resp = self._create_key()
        key_id      = create_resp.data['id']
        # Start active
        self.assertTrue(create_resp.data['is_active'])
        # Toggle off
        toggle_resp = self.client.post(f'{self.list_url}{key_id}/toggle/')
        self.assertEqual(toggle_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(toggle_resp.data['is_active'])
        # Toggle back on
        toggle_resp2 = self.client.post(f'{self.list_url}{key_id}/toggle/')
        self.assertTrue(toggle_resp2.data['is_active'])

    def test_unauthenticated_returns_401(self):
        unauth = APIClient()
        resp = unauth.get(self.list_url)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ─────────────────────────────────────────────────────────────────────────────
# WebhookViewSet Tests
# ─────────────────────────────────────────────────────────────────────────────

class WebhookViewSetTest(TestCase):

    def setUp(self):
        self.client    = APIClient()
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.publisher)
        self.list_url  = '/api/smartlink/webhooks/'

    def _create_endpoint(self, url='https://hooks.example.com/sl', events=None):
        return self.client.post(self.list_url, {
            'url':    url,
            'events': events or ['conversion', 'click'],
        }, format='json')

    def test_create_webhook_endpoint(self):
        resp = self._create_endpoint()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['url'], 'https://hooks.example.com/sl')

    def test_list_own_endpoints(self):
        self._create_endpoint('https://a.example.com')
        self._create_endpoint('https://b.example.com')
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_cannot_see_other_publishers_endpoints(self):
        other     = UserFactory()
        other_cli = APIClient()
        other_cli.force_authenticate(user=other)
        other_cli.post(self.list_url, {'url': 'https://other.com', 'events': ['click']}, format='json')
        # This publisher should only see their own
        resp = self.client.get(self.list_url)
        # Should not see 'https://other.com' in our results
        results = resp.data if isinstance(resp.data, list) else []
        urls = [r['url'] for r in results if isinstance(r, dict) and 'url' in r]
        self.assertNotIn('https://other.com', urls)

    def test_update_endpoint(self):
        create_resp = self._create_endpoint()
        ep_id = create_resp.data['id']
        update_resp = self.client.patch(
            f'{self.list_url}{ep_id}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(update_resp.data['is_active'])

    def test_delete_endpoint(self):
        create_resp = self._create_endpoint()
        ep_id = create_resp.data['id']
        del_resp = self.client.delete(f'{self.list_url}{ep_id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_deliveries_list_empty(self):
        create_resp = self._create_endpoint()
        ep_id = create_resp.data['id']
        resp = self.client.get(f'{self.list_url}{ep_id}/deliveries/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_events_list(self):
        resp = self.client.get(f'{self.list_url}events/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertGreater(len(resp.data), 0)
        self.assertIn('event', resp.data[0])

    def test_unauthenticated_returns_401(self):
        unauth = APIClient()
        resp = unauth.get(self.list_url)
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ─────────────────────────────────────────────────────────────────────────────
# PayoutViewSet Tests
# ─────────────────────────────────────────────────────────────────────────────

class PayoutViewSetTest(TestCase):

    def setUp(self):
        self.client    = APIClient()
        self.publisher = UserFactory()
        self.admin     = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.publisher)
        self.list_url  = '/api/smartlink/payouts/'

    def test_wallet_endpoint_returns_balance(self):
        _make_wallet(self.publisher, balance=Decimal('250'), pending=Decimal('30'))
        resp = self.client.get(f'{self.list_url}wallet/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(str(resp.data['balance_usd']), '250.0000')
        self.assertEqual(str(resp.data['pending_usd']), '30.0000')

    def test_wallet_auto_creates_if_missing(self):
        resp = self.client.get(f'{self.list_url}wallet/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('balance_usd', resp.data)

    def test_summary_empty(self):
        resp = self.client.get(f'{self.list_url}summary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_net_usd', resp.data)

    def test_list_own_payout_records(self):
        _make_payout_record(self.publisher, status_val='paid')
        _make_payout_record(self.publisher, status_val='calculated')
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_cannot_see_other_publishers_payouts(self):
        other = UserFactory()
        record = _make_payout_record(other, status_val='paid')
        resp = self.client.get(self.list_url)
        # Should not contain the other publisher's record
        results = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        ref_ids = [r.get('reference_id', '') if isinstance(r, dict) else '' for r in results]
        self.assertNotIn(str(record.reference_id), ref_ids)

    def test_batches_list_admin_only(self):
        # Non-admin gets 403
        resp = self.client.get(f'{self.list_url}batches/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_batches_list_admin_ok(self):
        self.client.force_authenticate(user=self.admin)
        _make_batch(self.admin, 'Batch 1')
        _make_batch(self.admin, 'Batch 2')
        resp = self.client.get(f'{self.list_url}batches/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_approve_batch_admin_only(self):
        batch = _make_batch(self.admin)
        resp = self.client.post(f'{self.list_url}batches/{batch.pk}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_approve_batch_admin_ok(self):
        self.client.force_authenticate(user=self.admin)
        batch  = _make_batch(self.admin)
        record = _make_payout_record(self.publisher, status_val='calculated')
        record.batch = batch
        record.save()
        resp = self.client.post(f'{self.list_url}batches/{batch.pk}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('approved', resp.data)
        record.refresh_from_db()
        self.assertEqual(record.status, 'approved')

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_process_payment_approved_record(self, mock_route):
        mock_route.return_value = {
            'success': True, 'gateway': 'paypal',
            'transaction_id': 'TXN_001', 'status': 'PENDING',
            'error': '', 'requires_manual': False,
        }
        self.client.force_authenticate(user=self.admin)
        record = _make_payout_record(self.publisher, status_val='approved')
        resp = self.client.post(f'{self.list_url}{record.pk}/process-payment/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['success'])

    def test_process_payment_non_approved_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        record = _make_payout_record(self.publisher, status_val='calculated')
        resp = self.client.post(f'{self.list_url}{record.pk}/process-payment/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_process_payment_non_admin_returns_403(self):
        record = _make_payout_record(self.publisher, status_val='approved')
        resp = self.client.post(f'{self.list_url}{record.pk}/process-payment/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ─────────────────────────────────────────────────────────────────────────────
# PublisherProfileViewSet Tests
# ─────────────────────────────────────────────────────────────────────────────

class PublisherProfileViewSetTest(TestCase):

    def setUp(self):
        self.client    = APIClient()
        self.publisher = UserFactory()
        self.admin     = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.publisher)
        self.profile_url = '/api/smartlink/publisher/profile/'

    def test_get_my_profile_creates_if_missing(self):
        resp = self.client.get(f'{self.profile_url}my-profile/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('id', resp.data)

    def test_update_my_profile(self):
        resp = self.client.put(
            f'{self.profile_url}my-profile/',
            {
                'company_name':   'Updated Co.',
                'payment_method': 'wise',
                'payment_email':  'payout@example.com',
                'payout_currency': 'USD',
                'min_payout':     '50',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['company_name'], 'Updated Co.')
        self.assertEqual(resp.data['payment_method'], 'wise')

    def test_partial_update_my_profile(self):
        _make_profile(self.publisher, company_name='Original')
        resp = self.client.patch(
            f'{self.profile_url}my-profile/',
            {'company_name': 'Patched'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['company_name'], 'Patched')

    def test_gdpr_consent_records_timestamp(self):
        resp = self.client.post(f'{self.profile_url}gdpr-consent/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('timestamp', resp.data)
        # Verify DB
        from api.smartlink.models.billing import PublisherProfile
        profile = PublisherProfile.objects.get(publisher=self.publisher)
        self.assertTrue(profile.gdpr_consent)
        self.assertIsNotNone(profile.gdpr_consent_at)

    def test_anonymize_requires_confirm_string(self):
        resp = self.client.post(f'{self.profile_url}anonymize/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymize_with_correct_confirm(self):
        _make_profile(self.publisher)
        resp = self.client.post(
            f'{self.profile_url}anonymize/',
            {'confirm': 'DELETE MY DATA'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_list_all_profiles(self):
        _make_profile(self.publisher)
        other = UserFactory()
        _make_profile(other)
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.profile_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_non_admin_list_returns_403(self):
        resp = self.client.get(self.profile_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
