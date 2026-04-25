# api/wallet/tests/test_views.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from ..models import Wallet, WithdrawalMethod
from ..services import WalletService

User = get_user_model()


class WalletViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user(username="viewtest", password="pass", email="vt@test.com")
        self.client.force_authenticate(user=self.user)
        self.wallet = WalletService.get_or_create(self.user)

    def test_get_my_wallet(self):
        resp = self.client.get("/api/wallet/wallets/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["currency"], "BDT")

    def test_get_summary(self):
        resp = self.client.get("/api/wallet/wallets/summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("current_balance", resp.data["data"])

    def test_transfer_insufficient(self):
        other = User.objects.create_user(username="other1", password="pass", email="ot1@test.com")
        resp  = self.client.post("/api/wallet/wallets/transfer/", {
            "recipient": other.username, "amount": "9999"
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data["success"])

    def test_transfer_success(self):
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()
        other = User.objects.create_user(username="other2", password="pass", email="ot2@test.com")
        resp  = self.client.post("/api/wallet/wallets/transfer/", {
            "recipient": other.username, "amount": "300"
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/wallet/wallets/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_lock_requires_admin(self):
        resp = self.client.post(f"/api/wallet/wallets/{self.wallet.id}/lock/", {"reason":"Test"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_lock(self):
        admin = User.objects.create_superuser(username="viewadmin", password="pass", email="va@test.com")
        self.client.force_authenticate(user=admin)
        resp = self.client.post(f"/api/wallet/wallets/{self.wallet.id}/lock/", {"reason":"Test"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertTrue(self.wallet.is_locked)

    def test_balance_breakdown(self):
        resp = self.client.get("/api/wallet/wallets/balance_breakdown/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data["data"]
        self.assertIn("current", data)
        self.assertIn("available", data)
