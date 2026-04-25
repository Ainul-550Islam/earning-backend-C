# api/wallet/tests/test_balance_types.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, BalanceReserve, BalanceBonus
from ..services import WalletService, BalanceService

User = get_user_model()


class BalanceTypesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="baltest", password="pass", email="bal@test.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()

    def test_available_balance_calculation(self):
        self.wallet.frozen_balance   = Decimal("200")
        self.wallet.reserved_balance = Decimal("100")
        self.wallet.save()
        self.assertEqual(self.wallet.available_balance, Decimal("700"))

    def test_available_never_negative(self):
        self.wallet.frozen_balance = Decimal("2000")
        self.wallet.save()
        self.assertEqual(self.wallet.available_balance, Decimal("0"))

    def test_total_balance_sum(self):
        self.wallet.pending_balance = Decimal("300")
        self.wallet.bonus_balance   = Decimal("100")
        self.wallet.save()
        self.assertEqual(self.wallet.total_balance, Decimal("1400"))

    def test_freeze_unfreeze(self):
        self.wallet.freeze(Decimal("300"), "Test freeze")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.frozen_balance, Decimal("300"))
        self.assertEqual(self.wallet.current_balance, Decimal("700"))

        self.wallet.unfreeze(Decimal("300"), "Test unfreeze")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.frozen_balance, Decimal("0"))
        self.assertEqual(self.wallet.current_balance, Decimal("1000"))

    def test_freeze_insufficient_raises(self):
        with self.assertRaises(ValueError):
            self.wallet.freeze(Decimal("5000"), "Too much")

    def test_reserve_reduces_available(self):
        BalanceService.reserve(self.wallet, Decimal("300"), "Test reserve")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.reserved_balance, Decimal("300"))
        self.assertEqual(self.wallet.available_balance, Decimal("700"))

    def test_release_reserve(self):
        reserve = BalanceService.reserve(self.wallet, Decimal("200"))
        BalanceService.release_reserve(reserve)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.reserved_balance, Decimal("0"))

    def test_grant_bonus_credits_bonus_balance(self):
        BalanceService.grant_bonus(self.wallet, Decimal("100"), source="admin")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.bonus_balance, Decimal("100"))
        self.assertEqual(self.wallet.total_bonuses, Decimal("100"))

    def test_expire_bonus(self):
        from django.utils import timezone
        from datetime import timedelta
        bonus = BalanceBonus.objects.create(
            wallet=self.wallet, amount=Decimal("100"),
            status="active", expires_at=timezone.now() - timedelta(hours=1)
        )
        self.wallet.bonus_balance = Decimal("100")
        self.wallet.save()
        count = BalanceService.expire_bonuses()
        self.assertGreaterEqual(count, 1)
        bonus.refresh_from_db()
        self.assertEqual(bonus.status, "expired")
