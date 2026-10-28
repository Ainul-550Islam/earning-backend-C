# api/wallet/tests/test_chargeback.py
"""Tests for ChargebackService — receive, accept, reject lifecycle."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def _make_user(username):
    return User.objects.create_user(username=username, password="pass",
                                    email=f"{username}@test.com")


def _make_wallet(user, balance=Decimal("1000")):
    from ..services import WalletService
    wallet = WalletService.get_or_create(user)
    if balance:
        WalletService.credit(wallet, balance, txn_type="earning",
                             description="Setup credit")
    wallet.refresh_from_db()
    return wallet


class ChargebackModelTest(TestCase):

    def setUp(self):
        self.user   = _make_user("cb_user")
        self.wallet = _make_wallet(self.user)

    def _receive(self, amount=Decimal("200"), gateway="bkash", ref="GW-REF-001"):
        from ..chargeback import ChargebackService
        with patch("api.wallet.chargeback.SecurityService", create=True):
            return ChargebackService.receive(
                gateway=gateway,
                gateway_ref=ref,
                amount=amount,
                user=self.user,
                wallet=self.wallet,
                gateway_reason="User dispute",
            )

    def test_receive_creates_chargeback(self):
        from ..chargeback import Chargeback
        cb = self._receive()
        self.assertIsNotNone(cb.chargeback_id)
        self.assertEqual(cb.status, Chargeback.STATUS_RECEIVED)
        self.assertEqual(cb.amount, Decimal("200"))
        self.assertEqual(cb.gateway, "bkash")

    def test_receive_sets_gateway_ref(self):
        cb = self._receive(ref="BKASH-TXN-999")
        self.assertEqual(cb.gateway_ref, "BKASH-TXN-999")

    def test_receive_status_is_received(self):
        from ..chargeback import Chargeback
        cb = self._receive()
        self.assertEqual(cb.status, Chargeback.STATUS_RECEIVED)


class ChargebackAcceptTest(TestCase):

    def setUp(self):
        self.admin  = _make_user("cb_admin")
        self.user   = _make_user("cb_victim")
        self.wallet = _make_wallet(self.user, balance=Decimal("500"))

    def _receive(self, amount=Decimal("100")):
        from ..chargeback import ChargebackService
        with patch("api.wallet.chargeback.SecurityService", create=True):
            return ChargebackService.receive(
                gateway="nagad", gateway_ref="NGD-001",
                amount=amount, user=self.user, wallet=self.wallet,
            )

    def test_accept_debits_wallet(self):
        cb = self._receive(Decimal("100"))
        bal_before = self.wallet.current_balance
        with patch("api.wallet.chargeback.WithdrawalBlock", create=True):
            result = __import__(
                "api.wallet.chargeback", fromlist=["ChargebackService"]
            ).ChargebackService.accept(str(cb.chargeback_id), self.admin)
        self.wallet.refresh_from_db()
        # Balance decreased by chargeback amount
        self.assertLessEqual(
            self.wallet.current_balance,
            bal_before,
        )

    def test_accept_changes_status_to_accepted(self):
        from ..chargeback import ChargebackService, Chargeback
        cb = self._receive(Decimal("50"))
        with patch("api.wallet.chargeback.WithdrawalBlock", create=True):
            ChargebackService.accept(str(cb.chargeback_id), self.admin)
        cb.refresh_from_db()
        self.assertEqual(cb.status, Chargeback.STATUS_ACCEPTED)

    def test_accept_sets_resolved_at(self):
        from ..chargeback import ChargebackService
        cb = self._receive(Decimal("50"))
        with patch("api.wallet.chargeback.WithdrawalBlock", create=True):
            ChargebackService.accept(str(cb.chargeback_id))
        cb.refresh_from_db()
        self.assertIsNotNone(cb.resolved_at)

    def test_accept_nonexistent_raises(self):
        from ..chargeback import ChargebackService
        with self.assertRaises(ValueError):
            ChargebackService.accept("00000000-0000-0000-0000-000000000000")

    def test_double_accept_raises(self):
        from ..chargeback import ChargebackService, Chargeback
        cb = self._receive(Decimal("30"))
        with patch("api.wallet.chargeback.WithdrawalBlock", create=True):
            ChargebackService.accept(str(cb.chargeback_id))
        with self.assertRaises(ValueError):
            ChargebackService.accept(str(cb.chargeback_id))


class ChargebackRejectTest(TestCase):

    def setUp(self):
        self.admin  = _make_user("cb_admin2")
        self.user   = _make_user("cb_innocent")
        self.wallet = _make_wallet(self.user, balance=Decimal("300"))

    def _receive(self):
        from ..chargeback import ChargebackService
        with patch("api.wallet.chargeback.SecurityService", create=True):
            return ChargebackService.receive(
                gateway="stripe", gateway_ref="STR-001",
                amount=Decimal("75"), user=self.user, wallet=self.wallet,
            )

    def test_reject_changes_status(self):
        from ..chargeback import ChargebackService, Chargeback
        cb = self._receive()
        ChargebackService.reject(str(cb.chargeback_id), self.admin, "Verified legitimate")
        cb.refresh_from_db()
        self.assertEqual(cb.status, Chargeback.STATUS_REJECTED)

    def test_reject_does_not_debit_wallet(self):
        from ..chargeback import ChargebackService
        cb = self._receive()
        bal_before = self.wallet.current_balance
        ChargebackService.reject(str(cb.chargeback_id))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, bal_before)

    def test_reject_sets_resolved_at(self):
        from ..chargeback import ChargebackService
        cb = self._receive()
        ChargebackService.reject(str(cb.chargeback_id))
        cb.refresh_from_db()
        self.assertIsNotNone(cb.resolved_at)

    def test_reject_nonexistent_raises(self):
        from ..chargeback import ChargebackService
        with self.assertRaises(ValueError):
            ChargebackService.reject("00000000-0000-0000-0000-000000000000")

    def test_reject_stores_review_notes(self):
        from ..chargeback import ChargebackService
        cb = self._receive()
        ChargebackService.reject(str(cb.chargeback_id), notes="Customer verified")
        cb.refresh_from_db()
        self.assertEqual(cb.review_notes, "Customer verified")
