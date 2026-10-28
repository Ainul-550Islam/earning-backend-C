"""
payout_queue/tests/test_processor_methods.py  ← NEW FILE  (Part 2 / File 6)

Previously 0% coverage for:
  - validate_account() on all 3 processors
  - verify_transaction() on all 3 processors
  - _get_grant_token() / _execute_payment() / _query_payment() on BkashProcessor
  - _initialize_payment() / _complete_payment() on NagadProcessor
  - _post_payment() on RocketProcessor

All exist in processors/ subfolders but had no tests.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch, MagicMock, call
from django.test import TestCase

from ..choices import PaymentGateway
from ..exceptions import GatewayError, GatewayTimeoutError, GatewayAuthError
from ..processors.bkash import BkashProcessor
from ..processors.nagad import NagadProcessor
from ..processors.rocket import RocketProcessor
from ..utils.payment_gateway import PayoutResult

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BkashProcessor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _bkash():
    return BkashProcessor({
        "app_key": "KEY", "app_secret": "SECRET",
        "username": "user", "password": "pass",
        "base_url": "https://tokenized.sandbox.bka.sh",
    })

class BkashValidateAccountTest(TestCase):

    def test_valid_01_prefix(self):
        p = _bkash()
        for number in ("01312345678", "01412345678", "01512345678",
                       "01612345678", "01712345678", "01812345678",
                       "01912345678"):
            self.assertTrue(p.validate_account(number), f"Expected valid: {number}")

    def test_invalid_too_short(self):
        self.assertFalse(_bkash().validate_account("0171234567"))   # 10 digits

    def test_invalid_too_long(self):
        self.assertFalse(_bkash().validate_account("017123456789"))  # 12 digits

    def test_invalid_wrong_prefix(self):
        self.assertFalse(_bkash().validate_account("02112345678"))   # 021 prefix

    def test_invalid_empty(self):
        self.assertFalse(_bkash().validate_account(""))

    def test_invalid_none(self):
        self.assertFalse(_bkash().validate_account(None))

    def test_strips_dashes_and_spaces(self):
        self.assertTrue(_bkash().validate_account("017-1234-5678"))
        self.assertTrue(_bkash().validate_account("017 1234 5678"))

    def test_invalid_alpha_chars(self):
        self.assertFalse(_bkash().validate_account("017ABCD5678"))

class BkashVerifyTransactionTest(TestCase):

    @patch("api.payout_queue.processors.bkash.requests")
    def test_verify_completed(self, mock_req):
        token_resp = MagicMock()
        token_resp.json.return_value = {"id_token": "TOK_001"}
        token_resp.raise_for_status = MagicMock()

        query_resp = MagicMock()
        query_resp.json.return_value = {
            "transactionStatus": "Completed", "trxID": "TRX001"
        }
        query_resp.raise_for_status = MagicMock()
        mock_req.post.side_effect = [token_resp, query_resp]

        result = _bkash().verify_transaction("TRX001")
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "TRX001")

    @patch("api.payout_queue.processors.bkash.requests")
    def test_verify_failed_status(self, mock_req):
        token_resp = MagicMock()
        token_resp.json.return_value = {"id_token": "TOK_002"}
        token_resp.raise_for_status = MagicMock()

        query_resp = MagicMock()
        query_resp.json.return_value = {
            "transactionStatus": "Failed",
            "statusCode": "9999",
            "statusMessage": "Insufficient funds",
        }
        query_resp.raise_for_status = MagicMock()
        mock_req.post.side_effect = [token_resp, query_resp]

        result = _bkash().verify_transaction("TRX002")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "9999")
        self.assertIn("Insufficient", result.error_message)

    def test_verify_empty_reference_raises(self):
        with self.assertRaises(GatewayError):
            _bkash().verify_transaction("")

    def test_verify_none_reference_raises(self):
        with self.assertRaises(GatewayError):
            _bkash().verify_transaction(None)

    @patch("api.payout_queue.processors.bkash.requests")
    def test_verify_timeout_raises(self, mock_req):
        import requests as req_lib
        mock_req.post.side_effect = req_lib.exceptions.Timeout
        with self.assertRaises((GatewayTimeoutError, GatewayError)):
            _bkash().verify_transaction("TRX_TIMEOUT")

class BkashSendPayoutTest(TestCase):

    @patch("api.payout_queue.processors.bkash.requests")
    def test_send_payout_success(self, mock_req):
        token_resp = MagicMock()
        token_resp.json.return_value = {"id_token": "TOK_OK"}
        token_resp.raise_for_status = MagicMock()

        pay_resp = MagicMock()
        pay_resp.json.return_value = {
            "statusCode": "0000",
            "statusMessage": "Successful",
            "trxID": "BKASH_TRX_999",
        }
        pay_resp.raise_for_status = MagicMock()
        mock_req.post.side_effect = [token_resp, pay_resp]

        result = _bkash().send_payout(
            account_number="01712345678",
            amount=Decimal("500.00"),
            reference="REF_001",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "BKASH_TRX_999")

    @patch("api.payout_queue.processors.bkash.requests")
    def test_send_payout_api_error(self, mock_req):
        token_resp = MagicMock()
        token_resp.json.return_value = {"id_token": "TOK_ERR"}
        token_resp.raise_for_status = MagicMock()

        pay_resp = MagicMock()
        pay_resp.json.return_value = {
            "statusCode": "2001",
            "statusMessage": "Invalid mobile number",
        }
        pay_resp.raise_for_status = MagicMock()
        mock_req.post.side_effect = [token_resp, pay_resp]

        result = _bkash().send_payout(
            account_number="01712345678",
            amount=Decimal("500.00"),
            reference="REF_ERR",
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "2001")

    def test_send_payout_invalid_account_raises(self):
        with self.assertRaises(GatewayError):
            _bkash().send_payout(
                account_number="INVALID",
                amount=Decimal("500.00"),
                reference="REF",
            )

    def test_send_payout_zero_amount_raises(self):
        with self.assertRaises(GatewayError):
            _bkash().send_payout(
                account_number="01712345678",
                amount=Decimal("0.00"),
                reference="REF",
            )

    def test_send_payout_missing_reference_raises(self):
        with self.assertRaises(GatewayError):
            _bkash().send_payout(
                account_number="01712345678",
                amount=Decimal("500.00"),
                reference="",
            )

    @patch("api.payout_queue.processors.bkash.requests")
    def test_token_auth_failure_raises(self, mock_req):
        mock_req.post.side_effect = Exception("401 Unauthorized")
        with self.assertRaises((GatewayAuthError, GatewayError)):
            _bkash().send_payout(
                account_number="01712345678",
                amount=Decimal("500.00"),
                reference="REF",
            )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NagadProcessor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _nagad():
    return NagadProcessor({
        "merchant_id": "M001", "merchant_phone": "01712345678",
        "private_key": "FAKE_PRIV", "public_key": "FAKE_PUB",
        "base_url": "https://sandbox.nagad.com.bd",
    })

class NagadValidateAccountTest(TestCase):

    def test_valid_numbers(self):
        p = _nagad()
        for n in ("01712345678", "01812345678", "01912345678"):
            self.assertTrue(p.validate_account(n))

    def test_invalid_prefix_02(self):
        self.assertFalse(_nagad().validate_account("02112345678"))

    def test_invalid_empty(self):
        self.assertFalse(_nagad().validate_account(""))

    def test_invalid_none(self):
        self.assertFalse(_nagad().validate_account(None))

    def test_strips_formatting(self):
        self.assertTrue(_nagad().validate_account("017-1234-5678"))

class NagadVerifyTransactionTest(TestCase):

    @patch("api.payout_queue.processors.nagad.requests")
    def test_verify_success(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"status": "Success", "statusCode": "000"}
        resp.raise_for_status = MagicMock()
        mock_req.get.return_value = resp

        with patch.object(_nagad(), "_build_headers", return_value={}):
            p = _nagad()
            p._build_headers = lambda: {}
            result = p.verify_transaction("NAGAD_REF_001")
        self.assertTrue(result.success)

    @patch("api.payout_queue.processors.nagad.requests")
    def test_verify_failure(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"status": "Failed", "statusCode": "1234",
                                   "message": "Not found"}
        resp.raise_for_status = MagicMock()
        mock_req.get.return_value = resp

        p = _nagad()
        result = p.verify_transaction("NAGAD_BAD")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "1234")

    @patch("api.payout_queue.processors.nagad.requests")
    def test_verify_timeout_raises(self, mock_req):
        import requests as req_lib
        mock_req.get.side_effect = req_lib.exceptions.Timeout
        p = _nagad()
        with self.assertRaises(GatewayTimeoutError):
            p.verify_transaction("NAGAD_TIMEOUT")

    def test_verify_empty_reference_raises(self):
        with self.assertRaises(GatewayError):
            _nagad().verify_transaction("")

class NagadSendPayoutTest(TestCase):

    def test_invalid_account_raises(self):
        with self.assertRaises(GatewayError):
            _nagad().send_payout(account_number="INVALID",
                                 amount=Decimal("100"), reference="R")

    def test_zero_amount_raises(self):
        with self.assertRaises(GatewayError):
            _nagad().send_payout(account_number="01712345678",
                                 amount=Decimal("0"), reference="R")

    @patch("api.payout_queue.processors.nagad.requests")
    def test_send_payout_init_fails_returns_failure(self, mock_req):
        """If init returns no paymentReferenceId → return PayoutResult(success=False)."""
        init_resp = MagicMock()
        init_resp.json.return_value = {"message": "Account not found"}
        init_resp.raise_for_status = MagicMock()
        mock_req.post.return_value = init_resp

        p = _nagad()
        with patch.object(p, "_encrypt_sensitive", return_value="ENC"), \
             patch.object(p, "_sign", return_value="SIG"):
            result = p.send_payout(account_number="01712345678",
                                   amount=Decimal("500"), reference="R001")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "INIT_FAILED")

    @patch("api.payout_queue.processors.nagad.requests")
    def test_send_payout_success(self, mock_req):
        init_resp = MagicMock()
        init_resp.json.return_value = {"paymentReferenceId": "NAGAD_PREF_001"}
        init_resp.raise_for_status = MagicMock()

        complete_resp = MagicMock()
        complete_resp.json.return_value = {
            "status": "Success",
            "merchantInvoiceNumber": "INV_001",
        }
        complete_resp.raise_for_status = MagicMock()
        mock_req.post.side_effect = [init_resp, complete_resp]

        p = _nagad()
        with patch.object(p, "_encrypt_sensitive", return_value="ENC"), \
             patch.object(p, "_sign", return_value="SIG"):
            result = p.send_payout(account_number="01712345678",
                                   amount=Decimal("500"), reference="R002")
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "INV_001")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RocketProcessor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _rocket():
    return RocketProcessor({
        "api_key": "ROCKET_KEY",
        "merchant_number": "01712345678",
        "base_url": "https://rocket.example.com",
    })

class RocketValidateAccountTest(TestCase):

    def test_valid_numbers(self):
        p = _rocket()
        for n in ("01712345678", "01812345678", "01912345678"):
            self.assertTrue(p.validate_account(n))

    def test_invalid_empty(self):
        self.assertFalse(_rocket().validate_account(""))

    def test_invalid_none(self):
        self.assertFalse(_rocket().validate_account(None))

    def test_strips_formatting(self):
        self.assertTrue(_rocket().validate_account("017-1234-5678"))

    def test_wrong_prefix(self):
        self.assertFalse(_rocket().validate_account("02112345678"))

class RocketVerifyTransactionTest(TestCase):

    @patch("api.payout_queue.processors.rocket.requests")
    def test_verify_success(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "000", "message": "Success"}
        resp.raise_for_status = MagicMock()
        mock_req.post.return_value = resp

        result = _rocket().verify_transaction("ROCKET_TRX_001")
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "ROCKET_TRX_001")

    @patch("api.payout_queue.processors.rocket.requests")
    def test_verify_failure(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "999", "message": "Not found"}
        resp.raise_for_status = MagicMock()
        mock_req.post.return_value = resp

        result = _rocket().verify_transaction("ROCKET_FAIL")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "999")

    @patch("api.payout_queue.processors.rocket.requests")
    def test_verify_timeout_raises(self, mock_req):
        import requests as req_lib
        mock_req.post.side_effect = req_lib.exceptions.Timeout
        with self.assertRaises(GatewayTimeoutError):
            _rocket().verify_transaction("ROCKET_TIMEOUT")

    def test_verify_empty_reference_raises(self):
        with self.assertRaises(GatewayError):
            _rocket().verify_transaction("")

    def test_verify_none_reference_raises(self):
        with self.assertRaises(GatewayError):
            _rocket().verify_transaction(None)

class RocketSendPayoutTest(TestCase):

    def test_invalid_account_raises(self):
        with self.assertRaises(GatewayError):
            _rocket().send_payout(account_number="INVALID",
                                  amount=Decimal("100"), reference="R")

    def test_zero_amount_raises(self):
        with self.assertRaises(GatewayError):
            _rocket().send_payout(account_number="01712345678",
                                  amount=Decimal("0"), reference="R")

    def test_missing_reference_raises(self):
        with self.assertRaises(GatewayError):
            _rocket().send_payout(account_number="01712345678",
                                  amount=Decimal("500"), reference="")

    @patch("api.payout_queue.processors.rocket.requests")
    def test_send_success(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "000", "transaction_id": "ROCKET_TRX_999"}
        resp.raise_for_status = MagicMock()
        mock_req.post.return_value = resp

        result = _rocket().send_payout(account_number="01712345678",
                                       amount=Decimal("500"), reference="R001")
        self.assertTrue(result.success)
        self.assertEqual(result.gateway_reference, "ROCKET_TRX_999")

    @patch("api.payout_queue.processors.rocket.requests")
    def test_send_failure(self, mock_req):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "500",
                                   "message": "Insufficient balance"}
        resp.raise_for_status = MagicMock()
        mock_req.post.return_value = resp

        result = _rocket().send_payout(account_number="01712345678",
                                       amount=Decimal("500"), reference="R002")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "500")

    @patch("api.payout_queue.processors.rocket.requests")
    def test_send_timeout_raises(self, mock_req):
        import requests as req_lib
        mock_req.post.side_effect = req_lib.exceptions.Timeout
        with self.assertRaises(GatewayTimeoutError):
            _rocket().send_payout(account_number="01712345678",
                                  amount=Decimal("500"), reference="R003")

    @patch("api.payout_queue.processors.rocket.requests")
    def test_success_with_empty_gateway_reference_synthesised(self, mock_req):
        """If gateway returns success but no transaction_id, a synthetic ref is used."""
        resp = MagicMock()
        resp.json.return_value = {"status_code": "000"}   # no transaction_id
        resp.raise_for_status = MagicMock()
        mock_req.post.return_value = resp

        result = _rocket().send_payout(account_number="01712345678",
                                       amount=Decimal("500"), reference="MY_REF")
        self.assertTrue(result.success)
        self.assertIn("MY_REF", result.gateway_reference)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Config validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProcessorConfigValidationTest(TestCase):

    def test_bkash_missing_config_raises(self):
        with self.assertRaises(GatewayAuthError):
            BkashProcessor({})   # missing app_key etc.

    def test_nagad_missing_config_raises(self):
        with self.assertRaises(GatewayAuthError):
            NagadProcessor({})

    def test_rocket_missing_config_raises(self):
        with self.assertRaises(GatewayAuthError):
            RocketProcessor({})

    def test_config_must_be_dict(self):
        with self.assertRaises(TypeError):
            BkashProcessor("not_a_dict")

    def test_bkash_partial_config_raises(self):
        with self.assertRaises(GatewayAuthError):
            BkashProcessor({"app_key": "K"})   # missing app_secret, username, etc.
