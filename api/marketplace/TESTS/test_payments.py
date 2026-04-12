"""TESTS/test_payments.py — Payment & escrow tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.tenants.models import Tenant
from api.marketplace.models import Order, PaymentTransaction
from api.marketplace.enums import PaymentStatus

User = get_user_model()


class PaymentTransactionTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pay Tenant", slug="pay", domain="pay.localhost")
        self.user = User.objects.create_user(username="payer", password="pass")

    def test_mark_success(self):
        # Create a minimal order for FK
        order = Order.objects.create(
            tenant=self.tenant, user=self.user,
            total_price=Decimal("500.00"),
            shipping_name="Test", shipping_phone="01700000000",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )
        tx = PaymentTransaction.objects.create(
            tenant=self.tenant, order=order, user=self.user,
            method="bkash", amount=Decimal("500.00"),
        )
        self.assertEqual(tx.status, PaymentStatus.PENDING)
        tx.mark_success(gateway_id="TXN123", response={"status": "Completed"})
        self.assertEqual(tx.status, PaymentStatus.SUCCESS)
        self.assertIsNotNone(tx.completed_at)
