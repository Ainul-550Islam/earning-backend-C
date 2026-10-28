"""
Tests for SmartLink Payment Gateway Integration
================================================
Covers:
  - PayPalPayoutService  (mocked HTTP)
  - WisePayoutService    (mocked HTTP)
  - PaymentGatewayRouter (routing logic)
  - BillingService.process_payment()
  - BillingService.process_batch_payments()
  - PayoutViewSet process-payment endpoint
  - PayoutViewSet process-batch-payments endpoint
  - Celery tasks (mocked)

No external HTTP calls are made. All gateway calls are mocked with
unittest.mock.patch.
"""
import uuid
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .factories import UserFactory

User = get_user_model()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_payout_record(publisher, payment_method='paypal',
                        payment_address='pub@example.com',
                        net_amount='100.00', status_val='approved'):
    """Create a PayoutRecord without hitting real billing logic."""
    from api.smartlink.models.billing import PayoutRecord
    import datetime
    return PayoutRecord.objects.create(
        publisher=publisher,
        period_from=datetime.date(2024, 3, 1),
        period_to=datetime.date(2024, 3, 31),
        gross_amount=Decimal(net_amount),
        scrub_amount=Decimal('0'),
        net_amount=Decimal(net_amount),
        currency='USD',
        fx_rate=Decimal('1.000000'),
        local_amount=Decimal(net_amount),
        status=status_val,
        payment_method=payment_method,
        payment_address=payment_address,
    )


def _make_batch(admin, label='Test Batch'):
    """Create a minimal PayoutBatch."""
    from api.smartlink.models.billing import PayoutBatch
    import datetime
    return PayoutBatch.objects.create(
        label=label,
        period_from=datetime.date(2024, 3, 1),
        period_to=datetime.date(2024, 3, 31),
        status='review',
        created_by=admin,
    )


# ─── PayPalPayoutService Tests ────────────────────────────────────────────────

class PayPalPayoutServiceTest(TestCase):

    def setUp(self):
        from ..services.billing.PayPalPayoutService import PayPalPayoutService
        self.publisher = UserFactory()
        self.svc = PayPalPayoutService()

    def _make_record(self, **kwargs):
        return _make_payout_record(self.publisher, **kwargs)

    # ── _get_access_token ──────────────────────────────────────────────────────

    @patch('api.smartlink.services.billing.PayPalPayoutService.requests.post')
    def test_get_access_token_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'access_token': 'test_token_abc'}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        token = self.svc._get_access_token()
        self.assertEqual(token, 'test_token_abc')
        # Cached — second call should not hit HTTP
        token2 = self.svc._get_access_token()
        self.assertEqual(mock_post.call_count, 1)

    @patch('api.smartlink.services.billing.PayPalPayoutService.requests.post')
    def test_get_access_token_http_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError('refused')
        with self.assertRaises(requests.exceptions.ConnectionError):
            self.svc._get_access_token()

    # ── send_payout success ────────────────────────────────────────────────────

    @patch('api.smartlink.services.billing.PayPalPayoutService.requests.post')
    def test_send_payout_success(self, mock_post):
        # First call: OAuth token; second call: payout
        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'tok123'}
        token_resp.raise_for_status = MagicMock()

        payout_resp = MagicMock()
        payout_resp.status_code = 201
        payout_resp.json.return_value = {
            'batch_header': {
                'payout_batch_id': 'BATCH_XYZ',
                'batch_status':    'PENDING',
            }
        }

        mock_post.side_effect = [token_resp, payout_resp]

        with self.settings(
            SMARTLINK_PAYPAL_CLIENT_ID='cid',
            SMARTLINK_PAYPAL_CLIENT_SECRET='csecret',
        ):
            record = self._make_record()
            result = self.svc.send_payout(record)

        self.assertTrue(result['success'])
        self.assertEqual(result['batch_id'], 'BATCH_XYZ')
        self.assertEqual(result['status'], 'PENDING')
        self.assertEqual(result['error'], '')

    @patch('api.smartlink.services.billing.PayPalPayoutService.requests.post')
    def test_send_payout_api_error(self, mock_post):
        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'tok123'}
        token_resp.raise_for_status = MagicMock()

        err_resp = MagicMock()
        err_resp.status_code = 400
        err_resp.json.return_value = {
            'name':    'VALIDATION_ERROR',
            'message': 'Invalid receiver email',
        }

        mock_post.side_effect = [token_resp, err_resp]

        with self.settings(
            SMARTLINK_PAYPAL_CLIENT_ID='cid',
            SMARTLINK_PAYPAL_CLIENT_SECRET='csecret',
        ):
            record = self._make_record()
            result = self.svc.send_payout(record)

        self.assertFalse(result['success'])
        self.assertIn('VALIDATION_ERROR', result['error'])

    def test_send_payout_no_credentials(self):
        with self.settings(SMARTLINK_PAYPAL_CLIENT_ID='', SMARTLINK_PAYPAL_CLIENT_SECRET=''):
            from ..services.billing.PayPalPayoutService import PayPalPayoutService
            svc = PayPalPayoutService()  # instantiate inside context
            record = self._make_record()
            result = svc.send_payout(record)
        self.assertFalse(result['success'])
        self.assertIn('credentials not configured', result['error'])

    @patch('api.smartlink.services.billing.PayPalPayoutService.requests.post')
    def test_send_payout_timeout(self, mock_post):
        import requests as req_lib
        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'tok'}
        token_resp.raise_for_status = MagicMock()
        mock_post.side_effect = [token_resp, req_lib.exceptions.Timeout()]

        with self.settings(
            SMARTLINK_PAYPAL_CLIENT_ID='cid',
            SMARTLINK_PAYPAL_CLIENT_SECRET='csecret',
        ):
            record = self._make_record()
            result = self.svc.send_payout(record)

        self.assertFalse(result['success'])
        self.assertIn('timeout', result['error'].lower())

    # ── get_batch_status ───────────────────────────────────────────────────────

    @patch('api.smartlink.services.billing.PayPalPayoutService.requests.get')
    @patch('api.smartlink.services.billing.PayPalPayoutService.requests.post')
    def test_get_batch_status_success(self, mock_post, mock_get):
        token_resp = MagicMock()
        token_resp.json.return_value = {'access_token': 'tok'}
        token_resp.raise_for_status = MagicMock()
        mock_post.return_value = token_resp

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {
            'batch_header': {'payout_batch_id': 'BATCH_XYZ', 'batch_status': 'SUCCESS'}
        }
        mock_get.return_value = status_resp

        with self.settings(
            SMARTLINK_PAYPAL_CLIENT_ID='cid',
            SMARTLINK_PAYPAL_CLIENT_SECRET='csecret',
        ):
            result = self.svc.get_batch_status('BATCH_XYZ')

        self.assertEqual(result.get('payout_batch_id'), 'BATCH_XYZ')


# ─── WisePayoutService Tests ──────────────────────────────────────────────────

class WisePayoutServiceTest(TestCase):

    def setUp(self):
        from ..services.billing.WisePayoutService import WisePayoutService
        self.publisher = UserFactory(first_name='John', last_name='Doe')
        self.svc = WisePayoutService()

    def _make_record(self, **kwargs):
        return _make_payout_record(self.publisher, payment_method='wise', **kwargs)

    def _mock_wise_success(self):
        """Return a side_effect list for quote → recipient → transfer → fund."""
        quote_resp = MagicMock()
        quote_resp.json.return_value = {'id': 'quote-uuid-001'}
        quote_resp.raise_for_status = MagicMock()

        recipient_resp = MagicMock()
        recipient_resp.json.return_value = {'id': 999}
        recipient_resp.raise_for_status = MagicMock()

        transfer_resp = MagicMock()
        transfer_resp.json.return_value = {'id': 1234, 'status': 'processing'}
        transfer_resp.raise_for_status = MagicMock()

        fund_resp = MagicMock()
        fund_resp.json.return_value = {'status': 'processing'}
        fund_resp.raise_for_status = MagicMock()

        return [quote_resp, recipient_resp, transfer_resp, fund_resp]

    @patch('api.smartlink.services.billing.WisePayoutService.requests.post')
    def test_send_payout_success(self, mock_post):
        mock_post.side_effect = self._mock_wise_success()

        with self.settings(
            SMARTLINK_WISE_API_KEY='wise_key_test',
            SMARTLINK_WISE_PROFILE_ID=42,
        ):
            record = self._make_record()
            result = self.svc.send_payout(record)

        self.assertTrue(result['success'])
        self.assertEqual(result['transfer_id'], 1234)
        self.assertEqual(result['transaction_id'], '1234')
        self.assertEqual(result['error'], '')

    def test_send_payout_no_credentials(self):
        with self.settings(SMARTLINK_WISE_API_KEY='', SMARTLINK_WISE_PROFILE_ID=None):
            from ..services.billing.WisePayoutService import WisePayoutService
            svc = WisePayoutService()  # instantiate inside context
            record = self._make_record()
            result = svc.send_payout(record)
        self.assertFalse(result['success'])
        self.assertIn('credentials not configured', result['error'])

    @patch('api.smartlink.services.billing.WisePayoutService.requests.post')
    def test_send_payout_http_error(self, mock_post):
        import requests as req_lib
        quote_resp = MagicMock()
        quote_resp.json.return_value = {'id': 'quote-001'}
        quote_resp.raise_for_status = MagicMock()

        err_resp = MagicMock()
        err_resp.status_code = 422
        err_resp.json.return_value = {
            'errors': [{'message': 'Invalid email address'}]
        }
        http_err = req_lib.exceptions.HTTPError(response=err_resp)
        err_resp.raise_for_status.side_effect = http_err

        mock_post.side_effect = [quote_resp, err_resp]

        with self.settings(
            SMARTLINK_WISE_API_KEY='key',
            SMARTLINK_WISE_PROFILE_ID=42,
        ):
            record = self._make_record()
            result = self.svc.send_payout(record)

        self.assertFalse(result['success'])
        self.assertIn('422', result['error'])

    @patch('api.smartlink.services.billing.WisePayoutService.requests.post')
    def test_send_payout_timeout(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.exceptions.Timeout()

        with self.settings(
            SMARTLINK_WISE_API_KEY='key',
            SMARTLINK_WISE_PROFILE_ID=42,
        ):
            record = self._make_record()
            result = self.svc.send_payout(record)

        self.assertFalse(result['success'])
        self.assertIn('timeout', result['error'].lower())

    @patch('api.smartlink.services.billing.WisePayoutService.requests.get')
    def test_get_transfer_status(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {'id': 1234, 'status': 'outgoing_payment_sent'}
        )
        with self.settings(SMARTLINK_WISE_API_KEY='key', SMARTLINK_WISE_PROFILE_ID=42):
            result = self.svc.get_transfer_status(1234)

        self.assertEqual(result['transfer_id'], 1234)
        self.assertEqual(result['status'], 'OUTGOING_PAYMENT_SENT')


# ─── PaymentGatewayRouter Tests ───────────────────────────────────────────────

class PaymentGatewayRouterTest(TestCase):

    def setUp(self):
        from ..services.billing.PaymentGatewayRouter import PaymentGatewayRouter
        self.router  = PaymentGatewayRouter()
        self.publisher = UserFactory()

    def _make_record(self, method):
        return _make_payout_record(self.publisher, payment_method=method)

    @patch('api.smartlink.services.billing.PayPalPayoutService.PayPalPayoutService.send_payout')
    def test_routes_paypal(self, mock_send):
        mock_send.return_value = {
            'success': True, 'batch_id': 'B1', 'transaction_id': 'B1',
            'status': 'PENDING', 'error': '',
        }
        record = self._make_record('paypal')
        result = self.router.process(record)

        self.assertTrue(result['success'])
        self.assertEqual(result['gateway'], 'paypal')
        mock_send.assert_called_once_with(record)

    @patch('api.smartlink.services.billing.WisePayoutService.WisePayoutService.send_payout')
    def test_routes_wise(self, mock_send):
        mock_send.return_value = {
            'success': True, 'transfer_id': 99, 'transaction_id': '99',
            'status': 'PROCESSING', 'error': '',
        }
        record = self._make_record('wise')
        result = self.router.process(record)

        self.assertTrue(result['success'])
        self.assertEqual(result['gateway'], 'wise')
        mock_send.assert_called_once_with(record)

    def test_routes_wire_as_manual(self):
        record = self._make_record('wire')
        result = self.router.process(record)

        self.assertFalse(result['success'])
        self.assertTrue(result['requires_manual'])
        self.assertEqual(result['gateway'], 'manual')

    def test_routes_crypto_as_manual(self):
        record = self._make_record('crypto')
        result = self.router.process(record)
        self.assertTrue(result['requires_manual'])

    def test_routes_payoneer_as_manual(self):
        record = self._make_record('payoneer')
        result = self.router.process(record)
        self.assertTrue(result['requires_manual'])

    def test_routes_unknown_as_manual(self):
        record = self._make_record('unknown_method')
        result = self.router.process(record)
        self.assertTrue(result['requires_manual'])

    @patch('api.smartlink.services.billing.PayPalPayoutService.PayPalPayoutService.send_payout')
    def test_paypal_failure_propagated(self, mock_send):
        mock_send.return_value = {
            'success': False, 'batch_id': '', 'transaction_id': '',
            'status': 'FAILED', 'error': 'VALIDATION_ERROR: bad email',
        }
        record = self._make_record('paypal')
        result = self.router.process(record)

        self.assertFalse(result['success'])
        self.assertEqual(result['gateway'], 'paypal')
        self.assertIn('VALIDATION_ERROR', result['error'])


# ─── BillingService.process_payment Tests ────────────────────────────────────

class BillingServiceProcessPaymentTest(TestCase):

    def setUp(self):
        from ..services.billing.BillingService import BillingService
        self.svc       = BillingService()
        self.publisher = UserFactory()

    def _make_record(self, method='paypal', status_val='approved'):
        return _make_payout_record(
            self.publisher, payment_method=method, status_val=status_val
        )

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_process_paypal_success(self, mock_route):
        mock_route.return_value = {
            'success': True, 'gateway': 'paypal',
            'transaction_id': 'TXN001', 'status': 'PENDING',
            'error': '', 'requires_manual': False,
        }
        record = self._make_record()
        result = self.svc.process_payment(record)

        self.assertTrue(result['success'])
        record.refresh_from_db()
        self.assertEqual(record.status, 'paid')
        self.assertEqual(record.transaction_ref, 'TXN001')

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_process_wise_success(self, mock_route):
        mock_route.return_value = {
            'success': True, 'gateway': 'wise',
            'transaction_id': '7777', 'status': 'PROCESSING',
            'error': '', 'requires_manual': False,
        }
        record = self._make_record(method='wise')
        result = self.svc.process_payment(record)

        self.assertTrue(result['success'])
        record.refresh_from_db()
        self.assertEqual(record.status, 'paid')
        self.assertEqual(record.transaction_ref, '7777')

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_process_gateway_failure_marks_failed(self, mock_route):
        mock_route.return_value = {
            'success': False, 'gateway': 'paypal',
            'transaction_id': '', 'status': 'FAILED',
            'error': 'VALIDATION_ERROR', 'requires_manual': False,
        }
        record = self._make_record()
        result = self.svc.process_payment(record)

        self.assertFalse(result['success'])
        record.refresh_from_db()
        self.assertEqual(record.status, 'failed')
        self.assertIn('VALIDATION_ERROR', record.failure_reason)

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_manual_method_reverts_to_approved(self, mock_route):
        mock_route.return_value = {
            'success': False, 'gateway': 'manual',
            'transaction_id': '', 'status': 'MANUAL',
            'error': "Payment method 'wire' requires manual processing.",
            'requires_manual': True,
        }
        record = self._make_record(method='wire')
        result = self.svc.process_payment(record)

        self.assertTrue(result['requires_manual'])
        record.refresh_from_db()
        # Should revert back to approved (not failed) for manual methods
        self.assertEqual(record.status, 'approved')

    def test_process_non_approved_record_returns_error(self):
        record = self._make_record(status_val='calculated')
        result = self.svc.process_payment(record)

        self.assertFalse(result['success'])
        self.assertIn('not APPROVED', result['error'])
        # Status should NOT change
        record.refresh_from_db()
        self.assertEqual(record.status, 'calculated')

    def test_process_paid_record_returns_error(self):
        record = self._make_record(status_val='paid')
        result = self.svc.process_payment(record)
        self.assertFalse(result['success'])
        self.assertIn('not APPROVED', result['error'])


# ─── BillingService.process_batch_payments Tests ─────────────────────────────

class BillingServiceBatchPaymentTest(TestCase):

    def setUp(self):
        from ..services.billing.BillingService import BillingService
        self.svc   = BillingService()
        self.admin = UserFactory(is_staff=True)

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_batch_all_success(self, mock_route):
        mock_route.return_value = {
            'success': True, 'gateway': 'paypal',
            'transaction_id': 'TXN_X', 'status': 'PENDING',
            'error': '', 'requires_manual': False,
        }
        batch = _make_batch(self.admin)
        for _ in range(3):
            pub = UserFactory()
            r = _make_payout_record(pub, status_val='approved')
            r.batch = batch
            r.save()

        summary = self.svc.process_batch_payments(batch)

        self.assertEqual(summary['processed'], 3)
        self.assertEqual(summary['paid'], 3)
        self.assertEqual(summary['failed'], 0)
        self.assertEqual(summary['manual'], 0)

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_batch_mixed_results(self, mock_route):
        results = [
            {'success': True,  'gateway': 'paypal', 'transaction_id': 'T1',
             'status': 'PENDING', 'error': '', 'requires_manual': False},
            {'success': False, 'gateway': 'paypal', 'transaction_id': '',
             'status': 'FAILED', 'error': 'Bad email', 'requires_manual': False},
            {'success': False, 'gateway': 'manual', 'transaction_id': '',
             'status': 'MANUAL', 'error': 'wire manual', 'requires_manual': True},
        ]
        mock_route.side_effect = results
        batch = _make_batch(self.admin)
        methods = ['paypal', 'paypal', 'wire']
        for m in methods:
            pub = UserFactory()
            r = _make_payout_record(pub, payment_method=m, status_val='approved')
            r.batch = batch
            r.save()

        summary = self.svc.process_batch_payments(batch)

        self.assertEqual(summary['processed'], 3)
        self.assertEqual(summary['paid'], 1)
        self.assertEqual(summary['failed'], 1)
        self.assertEqual(summary['manual'], 1)
        self.assertEqual(len(summary['results']), 3)

    def test_batch_skips_non_approved(self):
        batch = _make_batch(self.admin)
        pub = UserFactory()
        r = _make_payout_record(pub, status_val='calculated')  # not approved
        r.batch = batch
        r.save()

        summary = self.svc.process_batch_payments(batch)
        # Nothing in APPROVED status → 0 processed
        self.assertEqual(summary['processed'], 0)


# ─── API Endpoint Tests ───────────────────────────────────────────────────────

class PayoutProcessPaymentViewTest(TestCase):
    """
    Tests for POST /api/smartlink/payouts/{id}/process-payment/
    """

    def setUp(self):
        self.client = APIClient()
        self.admin  = UserFactory(is_staff=True, is_superuser=True)
        self.pub    = UserFactory()
        self.client.force_authenticate(user=self.admin)

    def _make_record(self, **kwargs):
        return _make_payout_record(self.pub, **kwargs)

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_process_approved_record_success(self, mock_route):
        mock_route.return_value = {
            'success': True, 'gateway': 'paypal',
            'transaction_id': 'TXN123', 'status': 'PENDING',
            'error': '', 'requires_manual': False,
        }
        record = self._make_record(status_val='approved')
        url = f'/api/smartlink/payouts/{record.pk}/process-payment/'
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['gateway'], 'paypal')

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_process_approved_record_gateway_failure(self, mock_route):
        mock_route.return_value = {
            'success': False, 'gateway': 'paypal',
            'transaction_id': '', 'status': 'FAILED',
            'error': 'VALIDATION_ERROR', 'requires_manual': False,
        }
        record = self._make_record(status_val='approved')
        url = f'/api/smartlink/payouts/{record.pk}/process-payment/'
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(resp.data['success'])

    def test_process_non_approved_record_returns_400(self):
        record = self._make_record(status_val='calculated')
        url = f'/api/smartlink/payouts/{record.pk}/process-payment/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.pub)
        record = self._make_record(status_val='approved')
        url = f'/api/smartlink/payouts/{record.pk}/process-payment/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_record_returns_404(self):
        url = '/api/smartlink/payouts/99999/process-payment/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_manual_method_returns_200_with_requires_manual_flag(self, mock_route):
        mock_route.return_value = {
            'success': False, 'gateway': 'manual',
            'transaction_id': '', 'status': 'MANUAL',
            'error': 'wire requires manual processing.', 'requires_manual': True,
        }
        record = self._make_record(payment_method='wire', status_val='approved')
        url = f'/api/smartlink/payouts/{record.pk}/process-payment/'
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['requires_manual'])


class PayoutProcessBatchPaymentsViewTest(TestCase):
    """
    Tests for POST /api/smartlink/payouts/batches/{id}/process-payments/
    """

    def setUp(self):
        self.client = APIClient()
        self.admin  = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.admin)

    @patch('api.smartlink.services.billing.PaymentGatewayRouter.PaymentGatewayRouter.process')
    def test_process_batch_success(self, mock_route):
        mock_route.return_value = {
            'success': True, 'gateway': 'paypal',
            'transaction_id': 'T1', 'status': 'PENDING',
            'error': '', 'requires_manual': False,
        }
        batch = _make_batch(self.admin)
        pub = UserFactory()
        r = _make_payout_record(pub, status_val='approved')
        r.batch = batch
        r.save()

        url = f'/api/smartlink/payouts/batches/{batch.pk}/process-payments/'
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['processed'], 1)
        self.assertEqual(resp.data['paid'], 1)

    def test_non_admin_forbidden(self):
        pub = UserFactory()
        self.client.force_authenticate(user=pub)
        batch = _make_batch(self.admin)
        url = f'/api/smartlink/payouts/batches/{batch.pk}/process-payments/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_batch_returns_404(self):
        url = '/api/smartlink/payouts/batches/99999/process-payments/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ─── Celery Task Tests ────────────────────────────────────────────────────────

class BillingCeleryTaskTest(TestCase):

    def setUp(self):
        self.publisher = UserFactory()
        self.admin     = UserFactory(is_staff=True)

    @patch('api.smartlink.services.billing.BillingService.BillingService.process_payment')
    def test_process_payout_payment_task_success(self, mock_process):
        from ..tasks.billing_tasks import process_payout_payment
        mock_process.return_value = {
            'success': True, 'gateway': 'paypal',
            'transaction_id': 'T1', 'requires_manual': False, 'error': '',
        }
        record = _make_payout_record(self.publisher, status_val='approved')
        result = process_payout_payment(record.pk)

        self.assertTrue(result['success'])
        mock_process.assert_called_once()

    @patch('api.smartlink.services.billing.BillingService.BillingService.process_payment')
    def test_process_payout_payment_task_not_found(self, mock_process):
        from ..tasks.billing_tasks import process_payout_payment
        result = process_payout_payment(99999)

        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
        mock_process.assert_not_called()

    @patch('api.smartlink.tasks.billing_tasks.process_payout_payment.apply_async')
    def test_process_batch_payments_async_dispatches_tasks(self, mock_apply):
        from ..tasks.billing_tasks import process_batch_payments_async
        batch = _make_batch(self.admin)
        for _ in range(4):
            pub = UserFactory()
            r = _make_payout_record(pub, status_val='approved')
            r.batch = batch
            r.save()

        result = process_batch_payments_async(batch.pk)

        self.assertEqual(result['dispatched'], 4)
        self.assertEqual(mock_apply.call_count, 4)

    @patch('api.smartlink.tasks.billing_tasks.process_payout_payment.apply_async')
    def test_process_batch_payments_async_skips_non_approved(self, mock_apply):
        from ..tasks.billing_tasks import process_batch_payments_async
        batch = _make_batch(self.admin)
        pub = UserFactory()
        r = _make_payout_record(pub, status_val='calculated')  # not approved
        r.batch = batch
        r.save()

        result = process_batch_payments_async(batch.pk)
        self.assertEqual(result['dispatched'], 0)
        mock_apply.assert_not_called()
