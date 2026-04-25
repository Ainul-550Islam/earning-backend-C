# api/wallet/tests/test_signals.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WithdrawalMethod

User = get_user_model()


class SignalTest(TestCase):
    def test_wallet_auto_created_on_signup(self):
        user = User.objects.create_user(username="sigtest", password="pass", email="sig@test.com")
        self.assertTrue(Wallet.objects.filter(user=user).exists())

    def test_only_one_wallet_per_user(self):
        user = User.objects.create_user(username="onewal", password="pass", email="ow@test.com")
        count = Wallet.objects.filter(user=user).count()
        self.assertEqual(count, 1)

    def test_negative_balance_clamped(self):
        user = User.objects.create_user(username="negbal", password="pass", email="nb@test.com")
        wallet = Wallet.objects.get(user=user)
        wallet.current_balance = Decimal("-100")
        wallet.save()
        wallet.refresh_from_db()
        self.assertGreaterEqual(wallet.current_balance, Decimal("0"))

    def test_single_primary_payment_method(self):
        user = User.objects.create_user(username="pmsig", password="pass", email="pm@test.com")
        pm1 = WithdrawalMethod.objects.create(
            user=user, method_type="bkash", account_number="01700000001",
            account_name="P1", is_default=True
        )
        pm2 = WithdrawalMethod.objects.create(
            user=user, method_type="nagad", account_number="01700000002",
            account_name="P2", is_default=True
        )
        pm1.refresh_from_db()
        self.assertFalse(pm1.is_default)
        self.assertTrue(pm2.is_default)
