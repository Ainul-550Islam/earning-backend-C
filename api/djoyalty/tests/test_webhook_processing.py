# api/djoyalty/tests/test_webhook_processing.py
"""
Tests for WebhookProcessingService -- Audit Fix verification।
Ensures all 8 handler methods work correctly in isolation
(no HTTP context needed -- pure service unit tests)।
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock, call
from django.test import TestCase


class TestWebhookProcessingServiceHandlePayment(TestCase):
    """Tests for handle_payment() -- payment.completed event."""

    def test_handle_payment_success(self):
        """payment.completed -> PointsEngine.process_earn() called with correct args."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        mock_customer = MagicMock()
        mock_customer.code = 'CUST001'

        with patch('djoyalty.services.WebhookProcessingService.Customer') as MC, \
             patch('djoyalty.services.WebhookProcessingService.PointsEngine') as MPE:
            MC.objects.filter.return_value.first.return_value = mock_customer
            result = WebhookProcessingService.handle_payment({
                'customer_id': 1,
                'amount': 500,
                'reference_id': 'REF-001',
            })

        self.assertEqual(result['status'], 'points_processed')
        MPE.process_earn.assert_called_once_with(
            customer=mock_customer,
            transaction_value=500,
            source='webhook_payment',
            source_id='REF-001',
        )

    def test_handle_payment_missing_customer_id(self):
        """Skips gracefully when customer_id missing from payload."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService
        result = WebhookProcessingService.handle_payment({'amount': 500})
        self.assertEqual(result['status'], 'skipped')
        self.assertIn('missing', result['reason'])

    def test_handle_payment_customer_not_found(self):
        """Skips when customer_id not in DB."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        with patch('djoyalty.services.WebhookProcessingService.Customer') as MC:
            MC.objects.filter.return_value.first.return_value = None
            result = WebhookProcessingService.handle_payment({
                'customer_id': 9999,
                'amount': 100,
            })

        self.assertEqual(result['status'], 'skipped')
        self.assertIn('not found', result['reason'])

    def test_handle_payment_engine_error_returns_error_dict(self):
        """Returns error dict (not exception) when PointsEngine raises."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        mock_customer = MagicMock()
        with patch('djoyalty.services.WebhookProcessingService.Customer') as MC, \
             patch('djoyalty.services.WebhookProcessingService.PointsEngine') as MPE:
            MC.objects.filter.return_value.first.return_value = mock_customer
            MPE.process_earn.side_effect = Exception('DB unavailable')
            result = WebhookProcessingService.handle_payment({
                'customer_id': 1, 'amount': 100,
            })

        self.assertEqual(result['status'], 'error')
        self.assertIn('DB unavailable', result['error'])


class TestWebhookProcessingServiceHandlePaymentFailed(TestCase):
    """Tests for handle_payment_failed() -- payment.failed event."""

    def test_handle_payment_failed_releases_reservation(self):
        """Calls PointsReservationService.release_by_reference()."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        with patch('djoyalty.services.WebhookProcessingService.PointsReservationService') as MR:
            result = WebhookProcessingService.handle_payment_failed({
                'reference_id': 'TXN-123',
            })

        self.assertEqual(result['status'], 'reservation_released')
        MR.release_by_reference.assert_called_once_with(reference='TXN-123')

    def test_handle_payment_failed_no_reference(self):
        """Skips when no reference_id in payload."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService
        result = WebhookProcessingService.handle_payment_failed({})
        self.assertEqual(result['status'], 'skipped')


class TestWebhookProcessingServiceHandlePartnerEarn(TestCase):
    """Tests for handle_partner_earn() -- partner.points.earn event."""

    def test_handle_partner_earn_success(self):
        """Calls EarnRuleEngine.process_partner_earn() with correct args."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        mock_customer = MagicMock()
        mock_customer.code = 'CUST002'

        with patch('djoyalty.services.WebhookProcessingService.Customer') as MC, \
             patch('djoyalty.services.WebhookProcessingService.EarnRuleEngine') as ME:
            MC.objects.filter.return_value.first.return_value = mock_customer
            result = WebhookProcessingService.handle_partner_earn({
                'customer_code': 'CUST002',
                'partner_id': 7,
                'amount': 1500,
            })

        self.assertEqual(result['status'], 'partner_earn_processed')
        ME.process_partner_earn.assert_called_once()

    def test_handle_partner_earn_missing_fields(self):
        """Skips when customer_code or partner_id missing."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService
        result = WebhookProcessingService.handle_partner_earn({'amount': 100})
        self.assertEqual(result['status'], 'skipped')

    def test_handle_partner_earn_customer_not_found(self):
        """Skips when customer_code not found in DB."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        with patch('djoyalty.services.WebhookProcessingService.Customer') as MC:
            MC.objects.filter.return_value.first.return_value = None
            result = WebhookProcessingService.handle_partner_earn({
                'customer_code': 'GHOST', 'partner_id': 1, 'amount': 100,
            })

        self.assertEqual(result['status'], 'skipped')


class TestWebhookProcessingServiceHandleCashout(TestCase):
    """Tests for handle_cashout_completed() and handle_cashout_failed()."""

    def test_handle_cashout_completed_calls_bridge(self):
        """Calls WalletBridgeService.confirm_cashout()."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        with patch('djoyalty.services.WebhookProcessingService.WalletBridgeService') as MW:
            result = WebhookProcessingService.handle_cashout_completed({
                'reference': 'CO-ABC123',
                'payment_reference': 'PAY-XYZ',
            })

        self.assertEqual(result['status'], 'cashout_confirmed')
        MW.confirm_cashout.assert_called_once_with(
            reference='CO-ABC123', payment_reference='PAY-XYZ',
        )

    def test_handle_cashout_completed_no_reference_skips(self):
        """Skips when reference missing."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService
        result = WebhookProcessingService.handle_cashout_completed({})
        self.assertEqual(result['status'], 'skipped')

    def test_handle_cashout_failed_refunds_points(self):
        """Calls WalletBridgeService.fail_cashout() to refund points."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService

        with patch('djoyalty.services.WebhookProcessingService.WalletBridgeService') as MW:
            result = WebhookProcessingService.handle_cashout_failed({
                'reference': 'CO-FAIL999',
                'reason': 'bank_declined',
            })

        self.assertEqual(result['status'], 'cashout_refunded')
        MW.fail_cashout.assert_called_once_with(
            reference='CO-FAIL999', reason='bank_declined',
        )

    def test_handle_cashout_failed_no_reference(self):
        """Skips when no reference in payload."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService
        result = WebhookProcessingService.handle_cashout_failed({})
        self.assertEqual(result['status'], 'skipped')


class TestWebhookProcessingServiceHandleStatus(TestCase):
    """Tests for handle_sms_status() and handle_push_status()."""

    def test_handle_sms_status_logs_and_returns(self):
        """Returns logged status for SMS delivery events."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService
        result = WebhookProcessingService.handle_sms_status({
            'status': 'delivered', 'message_id': 'MSG-001',
        })
        self.assertEqual(result['status'], 'logged')
        self.assertEqual(result['sms_status'], 'delivered')

    def test_handle_push_status_logs_and_returns(self):
        """Returns logged status for push notification delivery events."""
        from djoyalty.services.WebhookProcessingService import WebhookProcessingService
        result = WebhookProcessingService.handle_push_status({
            'status': 'failed', 'device_id': 'DEV-XYZ',
        })
        self.assertEqual(result['status'], 'logged')
        self.assertEqual(result['push_status'], 'failed')


class TestWebhookReceiverViewDelegation(TestCase):
    """
    Verify views.py WebhookReceiverView delegates to WebhookProcessingService।
    AUDIT FIX: views.py must NOT contain business logic directly।
    """

    def test_handle_payment_delegates_to_service(self):
        """_handle_payment() in view calls WebhookProcessingService, not PointsEngine directly."""
        from djoyalty.views import WebhookReceiverView

        view    = WebhookReceiverView()
        payload = {'customer_id': 1, 'amount': 100}

        with patch('djoyalty.views.WebhookProcessingService') as MockService:
            MockService.handle_payment.return_value = {'status': 'points_processed'}
            result = view._handle_payment(payload)

        MockService.handle_payment.assert_called_once_with(payload)
        self.assertEqual(result['status'], 'points_processed')

    def test_handle_cashout_completed_delegates_to_service(self):
        """_handle_cashout_completed() delegates, does not call WalletBridgeService directly."""
        from djoyalty.views import WebhookReceiverView

        view    = WebhookReceiverView()
        payload = {'reference': 'CO-123'}

        with patch('djoyalty.views.WebhookProcessingService') as MockService:
            MockService.handle_cashout_completed.return_value = {'status': 'cashout_confirmed'}
            result = view._handle_cashout_completed(payload)

        MockService.handle_cashout_completed.assert_called_once_with(payload)
