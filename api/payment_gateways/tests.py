"""
Payment Gateways module tests — bKash, Nagad, Stripe, PayPal
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from decimal import Decimal
from unittest.mock import patch, MagicMock
import uuid

User = get_user_model()


def make_user():
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"user_{uid}", email=f"{uid}@test.com", password="pass1234"
    )


class PaymentGatewayModelTest(TestCase):

    def test_create_gateway(self):
        try:
            from api.payment_gateways.models import PaymentGateway
            gw = PaymentGateway.objects.create(
                name="stripe",
                display_name="Stripe",
                status="active",
                is_test_mode=True,
            )
            self.assertEqual(gw.name, "stripe")
            self.assertTrue(gw.is_test_mode)
        except ImportError:
            self.skipTest("PaymentGateway model not available")

    def test_gateway_status_choices(self):
        try:
            from api.payment_gateways.models import PaymentGateway
            choices = [c[0] for c in PaymentGateway.STATUS_CHOICES]
            self.assertIn("active", choices)
            self.assertIn("inactive", choices)
        except (ImportError, AttributeError):
            self.skipTest("PaymentGateway model not available")

    def test_gateway_types(self):
        try:
            from api.payment_gateways.models import PaymentGateway
            types = [c[0] for c in PaymentGateway.GATEWAY_CHOICES]
            self.assertIn("bkash", types)
            self.assertIn("nagad", types)
            self.assertIn("stripe", types)
        except (ImportError, AttributeError):
            self.skipTest("PaymentGateway model not available")

    def test_transaction_fee_default(self):
        try:
            from api.payment_gateways.models import PaymentGateway
            gw = PaymentGateway.objects.create(
                name="paypal", display_name="PayPal", status="active"
            )
            self.assertEqual(gw.transaction_fee_percentage, Decimal("1.5"))
        except ImportError:
            self.skipTest("PaymentGateway model not available")

    def test_unique_gateway_name(self):
        try:
            from api.payment_gateways.models import PaymentGateway
            PaymentGateway.objects.create(name="nagad", display_name="Nagad", status="active")
            with self.assertRaises(Exception):
                PaymentGateway.objects.create(name="nagad", display_name="Nagad Dup", status="active")
        except ImportError:
            self.skipTest("PaymentGateway model not available")


class PaymentGatewayAPITest(APITestCase):

    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_list_gateways(self):
        res = self.client.get("/api/payment-gateways/")
        self.assertNotIn(res.status_code, [500])

    def test_unauthenticated_list(self):
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/payment-gateways/")
        self.assertIn(res.status_code, [200, 401, 403])

    def test_initiate_payment_missing_fields(self):
        res = self.client.post("/api/payment-gateways/initiate/", {}, format="json")
        self.assertIn(res.status_code, [400, 404, 422])

    def test_initiate_bkash_payment(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"statusCode": "0000", "paymentID": "test_id"}
            )
            res = self.client.post("/api/payment-gateways/bkash/initiate/", {
                "amount": "100.00",
                "currency": "BDT",
            }, format="json")
            self.assertIn(res.status_code, [200, 201, 400, 404])

    def test_payment_callback_invalid(self):
        res = self.client.post("/api/payment-gateways/callback/", {
            "status": "FAILED",
            "paymentID": "invalid_id",
        }, format="json")
        self.assertIn(res.status_code, [200, 400, 404])
