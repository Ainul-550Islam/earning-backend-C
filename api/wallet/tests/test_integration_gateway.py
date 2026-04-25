# api/wallet/tests/test_integration_gateway.py
"""Integration tests for payment gateway services."""
from decimal import Decimal
from django.test import TestCase
from unittest.mock import patch, MagicMock


class BkashServiceTest(TestCase):
    def test_validate_number_valid(self):
        from ..services.gateway.BkashService import BkashService
        self.assertTrue(BkashService.validate_number("01712345678"))
        self.assertTrue(BkashService.validate_number("01812345678"))

    def test_validate_number_invalid(self):
        from ..services.gateway.BkashService import BkashService
        self.assertFalse(BkashService.validate_number("123456"))
        self.assertFalse(BkashService.validate_number("0101234567"))

    @patch("requests.post")
    def test_disburse_success(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"statusCode": "0000", "trxID": "TRX123", "statusMessage": "Success"}
        )
        from ..services.gateway.BkashService import BkashService
        BkashService._token = "fake_token"
        result = BkashService.disburse("01712345678", Decimal("500"), "REF001")
        self.assertTrue(result["success"])
        self.assertEqual(result["trxID"], "TRX123")

    @patch("requests.post")
    def test_disburse_failure(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"statusCode": "1001", "statusMessage": "Failed"}
        )
        from ..services.gateway.BkashService import BkashService
        BkashService._token = "fake_token"
        result = BkashService.disburse("01712345678", Decimal("500"))
        self.assertFalse(result["success"])


class UsdtServiceTest(TestCase):
    def test_validate_trc20_address(self):
        from ..services.gateway.UsdtService import UsdtService
        self.assertTrue(UsdtService.validate_address("T" + "A" * 33, "usdttrc20"))
        self.assertFalse(UsdtService.validate_address("invalid", "usdttrc20"))

    def test_validate_erc20_address(self):
        from ..services.gateway.UsdtService import UsdtService
        self.assertTrue(UsdtService.validate_address("0x" + "a" * 40, "usdterc20"))
        self.assertFalse(UsdtService.validate_address("0xinvalid", "usdterc20"))

    @patch("requests.get")
    def test_get_exchange_rate(self, mock_get):
        mock_get.return_value = MagicMock(json=lambda: {"rate": "0.0091"})
        from ..services.gateway.UsdtService import UsdtService
        rate = UsdtService.get_exchange_rate("bdt", "usd")
        self.assertAlmostEqual(rate, 0.0091, places=4)


class WebhookDispatcherTest(TestCase):
    def test_bkash_completed_payload(self):
        from ..integration.webhooks_integration import WebhookDispatcher
        with patch.object(WebhookDispatcher, "_complete_withdrawal", return_value={"processed": True}):
            result = WebhookDispatcher.handle_bkash(1, {
                "transactionStatus": "Completed", "trxID": "TRX456"
            })
            self.assertTrue(result["processed"])

    def test_unknown_gateway_returns_not_processed(self):
        from ..integration.webhooks_integration import WebhookDispatcher
        result = WebhookDispatcher.dispatch(1, "unknown_gateway", {})
        self.assertFalse(result["processed"])
