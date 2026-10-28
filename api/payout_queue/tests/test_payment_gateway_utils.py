"""
payout_queue/tests/test_payment_gateway_utils.py  ← NEW FILE  (Part 2 / File 8)

utils/payment_gateway.py was ~20% covered.
Missing:
  - PayoutResult: all slot constraints
  - BasePaymentProcessor: _require_config, config type validation
  - PaymentGatewayRegistry: register/get/is_registered/registered_gateways
    (is_registered and registered_gateways had 0% coverage — never called)
"""
from __future__ import annotations

from decimal import Decimal
from django.test import TestCase

from ..choices import PaymentGateway
from ..exceptions import GatewayError, GatewayAuthError
from ..utils.payment_gateway import (
    PayoutResult, BasePaymentProcessor, PaymentGatewayRegistry,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PayoutResult
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PayoutResultTest(TestCase):

    def test_success_with_reference(self):
        r = PayoutResult(success=True, gateway_reference="TRX_001")
        self.assertTrue(r.success)
        self.assertEqual(r.gateway_reference, "TRX_001")
        self.assertEqual(r.error_code, "")
        self.assertEqual(r.error_message, "")
        self.assertEqual(r.raw_response, {})

    def test_success_requires_gateway_reference(self):
        with self.assertRaises(ValueError):
            PayoutResult(success=True, gateway_reference="")

    def test_success_requires_gateway_reference_non_empty(self):
        with self.assertRaises(ValueError):
            PayoutResult(success=True)  # gateway_reference defaults to ""

    def test_failure_without_reference(self):
        r = PayoutResult(success=False, error_code="ERR_001",
                         error_message="Something went wrong")
        self.assertFalse(r.success)
        self.assertEqual(r.error_code, "ERR_001")
        self.assertEqual(r.error_message, "Something went wrong")
        self.assertEqual(r.gateway_reference, "")

    def test_raw_response_defaults_to_empty_dict(self):
        r = PayoutResult(success=False, error_code="E")
        self.assertEqual(r.raw_response, {})

    def test_raw_response_stored(self):
        raw = {"statusCode": "0000", "trxID": "XYZ"}
        r = PayoutResult(success=True, gateway_reference="XYZ", raw_response=raw)
        self.assertEqual(r.raw_response, raw)

    def test_success_must_be_bool(self):
        with self.assertRaises(TypeError):
            PayoutResult(success=1, gateway_reference="ref")  # int not bool

    def test_failure_success_false(self):
        with self.assertRaises(TypeError):
            PayoutResult(success="yes")  # str not bool

    def test_repr_success(self):
        r = PayoutResult(success=True, gateway_reference="TRX")
        self.assertIn("SUCCESS", repr(r))
        self.assertIn("TRX", repr(r))

    def test_repr_failure(self):
        r = PayoutResult(success=False, error_code="ERR", error_message="fail")
        self.assertIn("FAILED", repr(r))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BasePaymentProcessor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ConcreteProcessor(BasePaymentProcessor):
    """Minimal concrete subclass for testing BasePaymentProcessor."""
    gateway = "TEST_GW"

    def _validate_config(self):
        self._require_config("api_key")

    def send_payout(self, *, account_number, amount, reference, **kwargs):
        return PayoutResult(success=True, gateway_reference="FAKE_REF")

    def verify_transaction(self, gateway_reference):
        return PayoutResult(success=True, gateway_reference=gateway_reference)

    def validate_account(self, account_number):
        return bool(account_number)

class BaseProcessorTest(TestCase):

    def test_config_stored(self):
        p = ConcreteProcessor({"api_key": "K"})
        self.assertEqual(p.config["api_key"], "K")

    def test_config_must_be_dict(self):
        with self.assertRaises(TypeError):
            ConcreteProcessor("not_a_dict")

    def test_config_must_be_dict_not_list(self):
        with self.assertRaises(TypeError):
            ConcreteProcessor(["api_key"])

    def test_require_config_passes(self):
        # no exception
        ConcreteProcessor({"api_key": "K"})

    def test_require_config_missing_key_raises(self):
        with self.assertRaises(GatewayAuthError):
            ConcreteProcessor({})   # api_key missing

    def test_require_config_empty_value_raises(self):
        with self.assertRaises(GatewayAuthError):
            ConcreteProcessor({"api_key": ""})   # empty string = missing

    def test_validate_account_works(self):
        p = ConcreteProcessor({"api_key": "K"})
        self.assertTrue(p.validate_account("01712345678"))
        self.assertFalse(p.validate_account(""))

    def test_send_payout_returns_result(self):
        p = ConcreteProcessor({"api_key": "K"})
        r = p.send_payout(account_number="01712345678",
                          amount=Decimal("100"), reference="REF")
        self.assertIsInstance(r, PayoutResult)

    def test_verify_transaction_returns_result(self):
        p = ConcreteProcessor({"api_key": "K"})
        r = p.verify_transaction("TRX_001")
        self.assertIsInstance(r, PayoutResult)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PaymentGatewayRegistry
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PaymentGatewayRegistryTest(TestCase):

    def _registry(self):
        return PaymentGatewayRegistry()

    def _processor(self):
        from ..processors.bkash import BkashProcessor
        return BkashProcessor({
            "app_key": "K", "app_secret": "S",
            "username": "u", "password": "p",
            "base_url": "https://example.com",
        })

    def test_register_and_get(self):
        reg = self._registry()
        proc = self._processor()
        reg.register(PaymentGateway.BKASH, proc)
        self.assertIs(reg.get(PaymentGateway.BKASH), proc)

    # ── is_registered — previously 0% coverage ──────────────────────────
    def test_is_registered_true(self):
        reg = self._registry()
        reg.register(PaymentGateway.BKASH, self._processor())
        self.assertTrue(reg.is_registered(PaymentGateway.BKASH))

    def test_is_registered_false_before_register(self):
        reg = self._registry()
        self.assertFalse(reg.is_registered(PaymentGateway.BKASH))

    def test_is_registered_false_wrong_key(self):
        reg = self._registry()
        reg.register(PaymentGateway.BKASH, self._processor())
        self.assertFalse(reg.is_registered(PaymentGateway.NAGAD))

    # ── registered_gateways — previously 0% coverage ────────────────────
    def test_registered_gateways_empty(self):
        reg = self._registry()
        self.assertEqual(reg.registered_gateways(), [])

    def test_registered_gateways_after_register(self):
        reg = self._registry()
        reg.register(PaymentGateway.BKASH, self._processor())
        self.assertIn(PaymentGateway.BKASH, reg.registered_gateways())

    def test_registered_gateways_multiple(self):
        reg = self._registry()
        from ..processors.nagad import NagadProcessor
        from ..processors.rocket import RocketProcessor
        reg.register(PaymentGateway.BKASH, self._processor())
        reg.register(PaymentGateway.NAGAD, NagadProcessor({
            "merchant_id": "M", "merchant_phone": "01712345678",
            "private_key": "P", "public_key": "Q",
            "base_url": "https://example.com",
        }))
        gws = reg.registered_gateways()
        self.assertIn(PaymentGateway.BKASH, gws)
        self.assertIn(PaymentGateway.NAGAD, gws)

    def test_get_unregistered_raises(self):
        reg = self._registry()
        with self.assertRaises(GatewayError):
            reg.get(PaymentGateway.NAGAD)

    def test_get_empty_string_raises(self):
        reg = self._registry()
        with self.assertRaises(GatewayError):
            reg.get("")

    def test_register_invalid_gateway_raises(self):
        reg = self._registry()
        with self.assertRaises(ValueError):
            reg.register("FAKE_GATEWAY", self._processor())

    def test_register_invalid_processor_raises(self):
        reg = self._registry()
        with self.assertRaises(TypeError):
            reg.register(PaymentGateway.BKASH, "not_a_processor")

    def test_register_overwrites_existing(self):
        reg = self._registry()
        proc1 = self._processor()
        proc2 = self._processor()
        reg.register(PaymentGateway.BKASH, proc1)
        reg.register(PaymentGateway.BKASH, proc2)
        self.assertIs(reg.get(PaymentGateway.BKASH), proc2)

    def test_registry_isolation(self):
        """Two registry instances are independent."""
        r1 = PaymentGatewayRegistry()
        r2 = PaymentGatewayRegistry()
        r1.register(PaymentGateway.BKASH, self._processor())
        self.assertFalse(r2.is_registered(PaymentGateway.BKASH))
