"""
Payout Queue Tests — Processors, FeeCalculator, models, and services.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.core.exceptions import ValidationError

from ..choices import PayoutBatchStatus, PayoutItemStatus, PaymentGateway, PriorityLevel
from ..constants import MAX_RETRY_ATTEMPTS
from ..exceptions import (
    GatewayError, PayoutBatchStateError, PayoutItemStateError,
    InvalidPayoutAmountError, FeeCalculationError,
)
from ..models import PayoutBatch, PayoutItem, BulkProcessLog
from ..utils.fee_calculator import FeeCalculator, FeeConfig
from ..utils.payment_gateway import PaymentGatewayRegistry, BasePaymentProcessor, PayoutResult
from ..processors.bkash import BkashProcessor
from ..processors.nagad import NagadProcessor
from ..processors.rocket import RocketProcessor
from .factories import (
    UserFactory, StaffUserFactory, PayoutBatchFactory, PayoutItemFactory,
)


# ---------------------------------------------------------------------------
# FeeCalculator Tests
# ---------------------------------------------------------------------------

class FeeCalculatorTest(TestCase):

    def setUp(self):
        self.calc = FeeCalculator()

    def test_bkash_percentage_fee(self):
        result = self.calc.calculate(
            gateway=PaymentGateway.BKASH, gross_amount=Decimal("1000.00")
        )
        self.assertIn("fee", result)
        self.assertIn("net", result)
        self.assertEqual(result["gross"], Decimal("1000.00"))
        self.assertEqual(result["fee"] + result["net"], result["gross"])

    def test_nagad_percentage_fee(self):
        result = self.calc.calculate(
            gateway=PaymentGateway.NAGAD, gross_amount=Decimal("2000.00")
        )
        self.assertGreater(result["fee"], Decimal("0"))

    def test_bank_flat_fee(self):
        result = self.calc.calculate(
            gateway=PaymentGateway.BANK, gross_amount=Decimal("5000.00")
        )
        from ..constants import DEFAULT_BANK_FLAT_FEE
        self.assertEqual(result["fee"], DEFAULT_BANK_FLAT_FEE)

    def test_manual_zero_fee(self):
        result = self.calc.calculate(
            gateway=PaymentGateway.MANUAL, gross_amount=Decimal("100.00")
        )
        self.assertEqual(result["fee"], Decimal("0.00"))
        self.assertEqual(result["net"], Decimal("100.00"))

    def test_amount_below_minimum_raises(self):
        with self.assertRaises(FeeCalculationError):
            self.calc.calculate(
                gateway=PaymentGateway.BKASH, gross_amount=Decimal("5.00")
            )

    def test_amount_above_maximum_raises(self):
        with self.assertRaises(FeeCalculationError):
            self.calc.calculate(
                gateway=PaymentGateway.BKASH, gross_amount=Decimal("1000000.00")
            )

    def test_invalid_gateway_raises(self):
        with self.assertRaises(FeeCalculationError):
            self.calc.calculate(
                gateway="INVALID", gross_amount=Decimal("500.00")
            )

    def test_fee_capped_at_max(self):
        from ..constants import MAX_FEE_AMOUNT
        result = self.calc.calculate(
            gateway=PaymentGateway.BKASH, gross_amount=Decimal("100000.00")
        )
        self.assertLessEqual(result["fee"], MAX_FEE_AMOUNT)


# ---------------------------------------------------------------------------
# BkashProcessor Tests
# ---------------------------------------------------------------------------

class BkashProcessorTest(TestCase):

    def setUp(self):
        self.config = {
            "app_key": "test_key",
            "app_secret": "test_secret",
            "username": "test_user",
            "password": "test_pass",
            "base_url": "https://tokenized.sandbox.bka.sh/v1.2.0-beta",
        }
        self.processor = BkashProcessor(self.config)

    def test_validate_account_valid(self):
        self.assertTrue(self.processor.validate_account("01712345678"))
        self.assertTrue(self.processor.validate_account("01912345678"))

    def test_validate_account_invalid(self):
        self.assertFalse(self.processor.validate_account("12345678"))
        self.assertFalse(self.processor.validate_account(""))
        self.assertFalse(self.processor.validate_account(None))
        self.assertFalse(self.processor.validate_account("00112345678"))

    def test_send_payout_invalid_account_raises(self):
        with self.assertRaises(GatewayError):
            self.processor.send_payout(
                account_number="invalid",
                amount=Decimal("500.00"),
                reference="REF001",
            )

    def test_send_payout_zero_amount_raises(self):
        with self.assertRaises(GatewayError):
            self.processor.send_payout(
                account_number="01712345678",
                amount=Decimal("0.00"),
                reference="REF001",
            )

    @patch("api.payout_queue.processors.bkash.requests")
    def test_send_payout_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = [
            {"id_token": "mock_token"},
            {"statusCode": "0000", "trxID": "TRX12345"},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = self.processor.send_payout(
            account_number="01712345678",
            amount=Decimal("500.00"),
            reference="REF001",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "TRX12345")

    @patch("api.payout_queue.processors.bkash.requests")
    def test_send_payout_failure(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = [
            {"id_token": "mock_token"},
            {"statusCode": "2023", "statusMessage": "Insufficient balance"},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = self.processor.send_payout(
            account_number="01712345678",
            amount=Decimal("500.00"),
            reference="REF002",
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "2023")


# ---------------------------------------------------------------------------
# RocketProcessor Tests
# ---------------------------------------------------------------------------

class RocketProcessorTest(TestCase):

    def setUp(self):
        self.config = {
            "api_key": "test_api_key",
            "merchant_number": "01812345678",
            "base_url": "https://api.rocket.com.bd",
        }
        self.processor = RocketProcessor(self.config)

    def test_validate_account_valid(self):
        self.assertTrue(self.processor.validate_account("01512345678"))

    def test_validate_account_invalid(self):
        self.assertFalse(self.processor.validate_account("0001234567"))

    @patch("api.payout_queue.processors.rocket.requests")
    def test_send_payout_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status_code": "000",
            "transaction_id": "RKT12345",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = self.processor.send_payout(
            account_number="01512345678",
            amount=Decimal("300.00"),
            reference="REF003",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "RKT12345")


# ---------------------------------------------------------------------------
# PayoutBatch Model Tests
# ---------------------------------------------------------------------------

class PayoutBatchModelTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()

    def test_create_batch(self):
        batch = PayoutBatchFactory(created_by=self.admin)
        self.assertEqual(batch.status, PayoutBatchStatus.PENDING)
        self.assertFalse(batch.is_terminal)

    def test_state_transition_pending_to_processing(self):
        batch = PayoutBatchFactory()
        batch.transition_to(PayoutBatchStatus.PROCESSING)
        batch.refresh_from_db()
        self.assertEqual(batch.status, PayoutBatchStatus.PROCESSING)
        self.assertIsNotNone(batch.started_at)

    def test_invalid_transition_raises(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.COMPLETED)
        with self.assertRaises(PayoutBatchStateError):
            batch.transition_to(PayoutBatchStatus.PENDING)

    def test_acquire_lock(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        acquired = batch.acquire_lock("worker-001")
        self.assertTrue(acquired)
        self.assertEqual(batch.locked_by, "worker-001")

    def test_acquire_lock_already_locked(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        batch.acquire_lock("worker-001")
        acquired = batch.acquire_lock("worker-002")
        self.assertFalse(acquired)

    def test_release_lock(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        batch.acquire_lock("worker-001")
        batch.release_lock()
        batch.refresh_from_db()
        self.assertIsNone(batch.locked_at)
        self.assertEqual(batch.locked_by, "")

    def test_empty_name_raises(self):
        with self.assertRaises(ValidationError):
            PayoutBatchFactory(name="")

    def test_financial_immutability_on_terminal(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.COMPLETED)
        batch.total_amount = Decimal("999999.00")
        with self.assertRaises(ValidationError):
            batch.save()


# ---------------------------------------------------------------------------
# PayoutItem Model Tests
# ---------------------------------------------------------------------------

class PayoutItemModelTest(TestCase):

    def setUp(self):
        self.batch = PayoutBatchFactory()
        self.user = UserFactory()

    def test_create_item(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user)
        self.assertEqual(item.status, PayoutItemStatus.QUEUED)
        self.assertFalse(item.is_terminal)
        self.assertTrue(item.can_retry)

    def test_mark_success(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user)
        item.mark_success(gateway_reference="GW123")
        item.refresh_from_db()
        self.assertEqual(item.status, PayoutItemStatus.SUCCESS)
        self.assertEqual(item.gateway_reference, "GW123")
        self.assertIsNotNone(item.processed_at)

    def test_mark_success_already_success_raises(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user, status=PayoutItemStatus.SUCCESS)
        with self.assertRaises(PayoutItemStateError):
            item.mark_success(gateway_reference="GW999")

    def test_mark_failed_increments_retry(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user)
        item.mark_failed(error_code="ERR001", error_message="Network error")
        self.assertEqual(item.retry_count, 1)
        self.assertEqual(item.status, PayoutItemStatus.RETRYING)
        self.assertIsNotNone(item.next_retry_at)

    def test_mark_failed_exhausts_retries(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user)
        for _ in range(MAX_RETRY_ATTEMPTS):
            item.mark_failed(error_code="ERR001", error_message="Fail")
        self.assertEqual(item.status, PayoutItemStatus.FAILED)
        self.assertFalse(item.can_retry)

    def test_cancel_item(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user)
        item.cancel(reason="Test cancel")
        item.refresh_from_db()
        self.assertEqual(item.status, PayoutItemStatus.CANCELLED)

    def test_cancel_success_raises(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user, status=PayoutItemStatus.SUCCESS)
        with self.assertRaises(PayoutItemStateError):
            item.cancel()

    def test_fee_lte_gross_constraint(self):
        with self.assertRaises(ValidationError):
            PayoutItemFactory(
                batch=self.batch, user=self.user,
                gross_amount=Decimal("100.00"),
                fee_amount=Decimal("200.00"),
                net_amount=Decimal("-100.00"),
            )

    def test_financial_immutability_on_success(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user, status=PayoutItemStatus.SUCCESS)
        item.gross_amount = Decimal("999.00")
        with self.assertRaises(ValidationError):
            item.save()


# ---------------------------------------------------------------------------
# PaymentGatewayRegistry Tests
# ---------------------------------------------------------------------------

class GatewayRegistryTest(TestCase):

    def test_register_and_get(self):
        registry = PaymentGatewayRegistry()
        config = {
            "app_key": "k", "app_secret": "s",
            "username": "u", "password": "p",
            "base_url": "https://example.com",
        }
        processor = BkashProcessor(config)
        registry.register(PaymentGateway.BKASH, processor)
        retrieved = registry.get(PaymentGateway.BKASH)
        self.assertIs(retrieved, processor)

    def test_get_unregistered_raises(self):
        registry = PaymentGatewayRegistry()
        with self.assertRaises(GatewayError):
            registry.get(PaymentGateway.NAGAD)

    def test_register_invalid_gateway_raises(self):
        registry = PaymentGatewayRegistry()
        config = {
            "app_key": "k", "app_secret": "s",
            "username": "u", "password": "p",
            "base_url": "https://example.com",
        }
        processor = BkashProcessor(config)
        with self.assertRaises(ValueError):
            registry.register("INVALID_GW", processor)


# ---------------------------------------------------------------------------
# PayoutResult Tests
# ---------------------------------------------------------------------------

class PayoutResultTest(TestCase):

    def test_success_result(self):
        result = PayoutResult(success=True, gateway_reference="TRX001")
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "TRX001")

    def test_failure_result(self):
        result = PayoutResult(
            success=False, error_code="E001", error_message="Failed"
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "E001")

    def test_success_without_reference_raises(self):
        with self.assertRaises(ValueError):
            PayoutResult(success=True, gateway_reference="")
