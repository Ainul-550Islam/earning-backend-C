"""TESTS/test_admin_actions.py — API-level tests for admin-gated view actions."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from api.tenants.models import Tenant
from api.marketplace.models import (
    Category, Product, ProductVariant, ProductInventory,
    SellerProfile, SellerVerification, Order, OrderItem,
    PaymentTransaction, EscrowHolding,
)
from api.marketplace.enums import VerificationStatus, PaymentStatus, EscrowStatus
from api.marketplace.SELLER_MANAGEMENT.seller_profile import create_seller_profile

User = get_user_model()


class SellerVerificationAdminTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Admin T", slug="adm", domain="adm.localhost")
        self.admin = User.objects.create_superuser(username="admin1", password="pass", email="a@a.com")
        self.buyer = User.objects.create_user(username="buyer_a", password="pass")
        seller_user = User.objects.create_user(username="seller_a", password="pass")
        self.seller = create_seller_profile(seller_user, self.tenant, "Admin Store", "+8801700000020")
        self.verification = SellerVerification.objects.create(
            tenant=self.tenant, seller=self.seller, status=VerificationStatus.UNVERIFIED
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.client.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))

    def _url(self, action):
        return f"/seller-verification/{self.verification.pk}/{action}/"

    def test_approve_verification(self):
        resp = self.client.post(self._url("approve"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, VerificationStatus.VERIFIED)

    def test_reject_verification(self):
        resp = self.client.post(self._url("reject"), {"reason": "Fake docs"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, VerificationStatus.REJECTED)
        self.assertEqual(self.verification.rejection_reason, "Fake docs")

    def test_non_admin_cannot_approve(self):
        self.client.force_authenticate(user=self.buyer)
        self.client.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))
        resp = self.client.post(self._url("approve"))
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])


class PaymentMarkSuccessTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Pay Adm T", slug="pa", domain="pa.localhost")
        self.admin = User.objects.create_superuser(username="admin2", password="pass", email="b@b.com")
        self.user = User.objects.create_user(username="payer2", password="pass")
        self.order = Order.objects.create(
            tenant=self.tenant, user=self.user,
            total_price=Decimal("750.00"),
            shipping_name="Test", shipping_phone="01700000001",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )
        self.tx = PaymentTransaction.objects.create(
            tenant=self.tenant, order=self.order, user=self.user,
            method="bkash", amount=Decimal("750.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.client.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))

    def test_mark_success(self):
        url = f"/transactions/{self.tx.pk}/mark_success/"
        resp = self.client.post(url, {"gateway_id": "GW123", "status": "Completed"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentStatus.SUCCESS)


class EscrowReleaseTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Escrow T", slug="esc", domain="esc.localhost")
        self.admin = User.objects.create_superuser(username="admin3", password="pass", email="c@c.com")
        self.user = User.objects.create_user(username="buyer_e", password="pass")
        seller_user = User.objects.create_user(username="seller_e", password="pass")
        self.seller = create_seller_profile(seller_user, self.tenant, "Escrow Store", "+8801700000021")
        cat = Category.objects.create(tenant=self.tenant, name="Cat", slug="cat-e")
        product = Product.objects.create(
            tenant=self.tenant, seller=self.seller, category=cat,
            name="Prod", slug="prod-e", description="D",
            base_price=Decimal("200.00"), status="active",
        )
        variant = ProductVariant.objects.create(tenant=self.tenant, product=product, sku="ESC-001")
        ProductInventory.objects.create(tenant=self.tenant, variant=variant, quantity=10)
        order = Order.objects.create(
            tenant=self.tenant, user=self.user,
            total_price=Decimal("200.00"),
            shipping_name="T", shipping_phone="01700000002",
            shipping_address="Dhaka", shipping_city="Dhaka",
        )
        order_item = OrderItem.objects.create(
            tenant=self.tenant, order=order, seller=self.seller, variant=variant,
            product_name="Prod", quantity=1, unit_price=Decimal("200.00"),
            subtotal=Decimal("200.00"), seller_net=Decimal("170.00"),
        )
        self.escrow = EscrowHolding.objects.create(
            tenant=self.tenant, order_item=order_item, seller=self.seller,
            gross_amount=Decimal("200.00"), commission_deducted=Decimal("30.00"),
            net_amount=Decimal("170.00"),
            release_after=timezone.now() - timedelta(days=1),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.client.credentials(HTTP_X_TENANT_ID=str(self.tenant.pk))

    def test_release_escrow(self):
        url = f"/escrow/{self.escrow.pk}/release/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.escrow.refresh_from_db()
        self.assertEqual(self.escrow.status, EscrowStatus.RELEASED)
