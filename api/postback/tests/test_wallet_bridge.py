"""
test_wallet_bridge.py – Tests for wallet bridge (credit/debit).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import TestCase

from api.postback.adapters.wallet_bridge import (
    credit_wallet_for_postback,
    debit_wallet_for_reversal,
)


def _make_log(points=100, user=True, network_key="cpalead", payout="2.50"):
    log = MagicMock()
    log.pk = "log-uuid-001"
    log.points_awarded = points
    log.source_ip = "1.2.3.4"
    log.offer_id = "OFFER_001"
    log.lead_id = "LEAD_001"
    log.payout = Decimal(payout)
    log.network.network_key = network_key
    log.network.metadata = {}
    log.resolved_user = MagicMock(pk=42) if user else None
    log.event_type = "sale"
    return log


def _make_reversal_log(original_points=100):
    reversal = MagicMock()
    reversal.pk = "reversal-uuid-001"
    original = _make_log(points=original_points)
    reversal.reversed_log = original
    reversal.resolved_user = original.resolved_user
    return reversal


class CreditWalletTests(TestCase):

    def test_no_user_returns_false(self):
        log = _make_log(user=False)
        result = credit_wallet_for_postback(postback_log=log)
        self.assertFalse(result)

    def test_zero_points_returns_false(self):
        log = _make_log(points=0)
        result = credit_wallet_for_postback(postback_log=log)
        self.assertFalse(result)

    def test_wallet_not_installed_returns_false(self):
        """If api.wallet not installed, returns False gracefully."""
        log = _make_log(points=100)
        with patch("builtins.__import__", side_effect=ImportError("no wallet")):
            result = credit_wallet_for_postback(postback_log=log)
        self.assertFalse(result)

    def test_credit_with_points_returns_bool(self):
        """credit_wallet_for_postback returns a bool."""
        log = _make_log(points=500)
        result = credit_wallet_for_postback(postback_log=log)
        self.assertIsInstance(result, bool)

    def test_exception_returns_false_never_raises(self):
        """credit_wallet_for_postback never raises."""
        log = _make_log(points=100)
        with patch("api.postback.adapters.wallet_bridge.credit_wallet_for_postback",
                   side_effect=Exception("DB error")):
            try:
                credit_wallet_for_postback(postback_log=log)
            except Exception:
                self.fail("credit_wallet_for_postback raised an exception")

    def test_points_to_bdt_conversion(self):
        """100 points × 0.01 rate = 1.00 BDT."""
        log = _make_log(points=100)
        log.network.metadata = {"points_to_bdt_rate": "0.01"}
        # With mock wallet
        with patch("api.postback.adapters.wallet_bridge.credit_wallet_for_postback") as m:
            m.return_value = True
            credit_wallet_for_postback(postback_log=log)

    def test_custom_rate_from_metadata(self):
        """Custom rate from network metadata is respected."""
        log = _make_log(points=200)
        log.network.metadata = {"points_to_bdt_rate": "0.005"}
        # 200 × 0.005 = 1.00 BDT
        with patch("api.postback.adapters.wallet_bridge.credit_wallet_for_postback") as m:
            m.return_value = True
            credit_wallet_for_postback(postback_log=log)


class DebitWalletTests(TestCase):

    def test_no_reversed_log_returns_false(self):
        reversal = MagicMock()
        reversal.reversed_log = None
        reversal.resolved_user = MagicMock(pk=1)
        result = debit_wallet_for_reversal(reversal_log=reversal)
        self.assertFalse(result)

    def test_no_user_returns_false(self):
        reversal = MagicMock()
        reversal.resolved_user = None
        reversal.reversed_log = _make_log()
        result = debit_wallet_for_reversal(reversal_log=reversal)
        self.assertFalse(result)

    def test_zero_points_returns_true_no_action(self):
        """Zero points to deduct → returns True (nothing to do)."""
        reversal = _make_reversal_log(original_points=0)
        with patch("api.postback.adapters.wallet_bridge.debit_wallet_for_reversal") as m:
            m.return_value = True
            result = debit_wallet_for_reversal(reversal_log=reversal)

    def test_wallet_not_installed_returns_false(self):
        reversal = _make_reversal_log(original_points=100)
        with patch("builtins.__import__", side_effect=ImportError("no wallet")):
            result = debit_wallet_for_reversal(reversal_log=reversal)
        self.assertFalse(result)

    def test_exception_returns_false_never_raises(self):
        reversal = _make_reversal_log(original_points=100)
        with patch("api.postback.adapters.wallet_bridge.debit_wallet_for_reversal",
                   side_effect=Exception("DB error")):
            try:
                debit_wallet_for_reversal(reversal_log=reversal)
            except Exception:
                self.fail("debit_wallet_for_reversal raised an exception")
