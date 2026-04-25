# api/wallet/tests/test_admin.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class AdminWalletTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username="admintest", email="adm@t.com", password="pass")
        self.user  = User.objects.create_user(username="walletuser", email="wu@t.com", password="pass")
        self.client.force_authenticate(user=self.admin)
        from ..services.core.WalletService import WalletService
        self.wallet = WalletService.get_or_create(self.user)

    def test_admin_credit_endpoint(self):
        resp = self.client.post(f"/api/wallet/wallets/{self.wallet.id}/admin_credit/",
            {"amount": "500", "description": "Test credit"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("500"))

    def test_admin_debit_endpoint(self):
        self.wallet.current_balance = Decimal("1000"); self.wallet.save()
        resp = self.client.post(f"/api/wallet/wallets/{self.wallet.id}/admin_debit/",
            {"amount": "200", "description": "Test debit"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("800"))

    def test_admin_lock_wallet(self):
        resp = self.client.post(f"/api/wallet/wallets/{self.wallet.id}/lock/",
            {"reason": "Test lock"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.wallet.refresh_from_db()
        self.assertTrue(self.wallet.is_locked)

    def test_admin_unlock_wallet(self):
        self.wallet.lock("Test"); 
        resp = self.client.post(f"/api/wallet/wallets/{self.wallet.id}/unlock/")
        self.assertEqual(resp.status_code, 200)
        self.wallet.refresh_from_db()
        self.assertFalse(self.wallet.is_locked)

    def test_admin_list_all_wallets(self):
        resp = self.client.get("/api/wallet/wallets/")
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_blocked(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f"/api/wallet/wallets/{self.wallet.id}/admin_credit/",
            {"amount":"100","description":"hack"}, format="json")
        self.assertIn(resp.status_code, [403, 401])
