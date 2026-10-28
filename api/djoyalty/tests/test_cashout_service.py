# api/djoyalty/tests/test_cashout_service.py
"""
Tests for CashoutService -- Audit Fix verification।
Ensures create_request() runs atomically with fraud check,
race-condition lock, WalletTransaction creation, and PointsLedger debit।
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, TransactionTestCase
from django.db import transaction


class TestCashoutServiceCreateRequest(TestCase):
    """Test CashoutService.create_request() full atomic flow."""

    def _make_customer(self, balance=Decimal('1000'), is_active=True, is_verified=True):
        mock = MagicMock()
        mock.id = 1
        mock.code = 'CUST001'
        mock.is_active = is_active
        mock.is_verified = is_verified
        mock.tenant = None
        return mock

    def _make_rate(self, points_per_unit=Decimal('100'), min_cashout=Decimal('100')):
        rate = MagicMock()
        rate.points_per_unit = points_per_unit
        rate.min_cashout_points = min_cashout
        return rate

    def _make_lp(self, balance=Decimal('1000'), frozen=Decimal('0')):
        lp = MagicMock()
        lp.balance = balance
        lp.frozen_balance = frozen
        lp.lifetime_redeemed = Decimal('0')
        # available_balance = balance - frozen
        type(lp).available_balance = PropertyMock(return_value=balance - frozen)
        lp.save = MagicMock()
        return lp

    @patch('djoyalty.services.CashoutService.WalletTransaction')
    @patch('djoyalty.services.CashoutService.PointsLedger')
    @patch('djoyalty.services.CashoutService.LoyaltyPoints')
    @patch('djoyalty.services.CashoutService.CashoutRequest')
    @patch('djoyalty.services.CashoutService.CashoutRate')
    @patch('djoyalty.services.CashoutService.LoyaltyValidator')
    def test_create_request_success(self, MockValidator, MockRate, MockCashout,
                                     MockLP, MockLedger, MockWallet):
        """Full happy path -- creates cashout + wallet txn + ledger entry."""
        from djoyalty.services.CashoutService import CashoutService

        customer = self._make_customer()
        rate     = self._make_rate()
        lp       = self._make_lp(balance=Decimal('500'))

        MockValidator.validate_cashout.return_value = (True, '')
        MockLP.objects.select_for_update.return_value.get.return_value = lp

        mock_cashout = MagicMock()
        mock_cashout.id = 42
        MockCashout.objects.create.return_value = mock_cashout

        result = CashoutService.create_request(
            customer=customer,
            points_to_redeem=Decimal('200'),
            cashout_method='bank_transfer',
            rate=rate,
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['cashout'], mock_cashout)
        MockValidator.validate_cashout.assert_called_once()
        MockLP.objects.select_for_update.assert_called_once()
        MockCashout.objects.create.assert_called_once()
        MockWallet.objects.create.assert_called_once()
        MockLedger.objects.create.assert_called_once()
        # Verify points were deducted
        self.assertEqual(lp.balance, Decimal('300'))

    @patch('djoyalty.services.CashoutService.LoyaltyValidator')
    def test_create_request_validation_failure(self, MockValidator):
        """Returns error dict when LoyaltyValidator.validate_cashout fails."""
        from djoyalty.services.CashoutService import CashoutService

        customer = self._make_customer()
        MockValidator.validate_cashout.return_value = (False, 'Customer account is not active.')

        result = CashoutService.create_request(
            customer=customer,
            points_to_redeem=Decimal('100'),
            cashout_method='bank_transfer',
        )

        self.assertFalse(result['success'])
        self.assertIn('not active', result['error'])

    @patch('djoyalty.services.CashoutService.LoyaltyPoints')
    @patch('djoyalty.services.CashoutService.LoyaltyValidator')
    def test_create_request_insufficient_balance_after_lock(self, MockValidator, MockLP):
        """Detects balance change between validate and select_for_update."""
        from djoyalty.services.CashoutService import CashoutService

        customer = self._make_customer()
        MockValidator.validate_cashout.return_value = (True, '')

        lp = self._make_lp(balance=Decimal('50'), frozen=Decimal('0'))
        MockLP.objects.select_for_update.return_value.get.return_value = lp

        result = CashoutService.create_request(
            customer=customer,
            points_to_redeem=Decimal('200'),
            cashout_method='bank_transfer',
            rate=self._make_rate(min_cashout=Decimal('50')),
        )

        self.assertFalse(result['success'])
        self.assertIn('Insufficient', result['error'])

    @patch('djoyalty.services.CashoutService.LoyaltyPoints')
    @patch('djoyalty.services.CashoutService.LoyaltyValidator')
    def test_create_request_no_rate_returns_error(self, MockValidator, MockLP):
        """Returns error when no CashoutRate found for method."""
        from djoyalty.services.CashoutService import CashoutService
        from djoyalty.services.CashoutService import CashoutRate

        customer = self._make_customer()
        MockValidator.validate_cashout.return_value = (True, '')

        with patch('djoyalty.services.CashoutService.CashoutRate') as MockRate:
            MockRate.objects.filter.return_value.order_by.return_value.first.return_value = None
            result = CashoutService.create_request(
                customer=customer,
                points_to_redeem=Decimal('100'),
                cashout_method='gift_card',
            )

        self.assertFalse(result['success'])
        self.assertIn('not available', result['error'])

    @patch('djoyalty.services.CashoutService.WalletTransaction')
    @patch('djoyalty.services.CashoutService.PointsLedger')
    @patch('djoyalty.services.CashoutService.LoyaltyPoints')
    @patch('djoyalty.services.CashoutService.CashoutRequest')
    @patch('djoyalty.services.CashoutService.LoyaltyValidator')
    def test_wallet_txn_failure_does_not_rollback_cashout(
            self, MockValidator, MockCashout, MockLP, MockLedger, MockWallet):
        """WalletTransaction failure must NOT roll back the cashout -- it's supplementary."""
        from djoyalty.services.CashoutService import CashoutService

        customer = self._make_customer()
        rate     = self._make_rate()
        lp       = self._make_lp(balance=Decimal('500'))

        MockValidator.validate_cashout.return_value = (True, '')
        MockLP.objects.select_for_update.return_value.get.return_value = lp

        mock_cashout = MagicMock()
        mock_cashout.id = 99
        MockCashout.objects.create.return_value = mock_cashout
        MockWallet.objects.create.side_effect = Exception('DB connection lost')

        result = CashoutService.create_request(
            customer=customer,
            points_to_redeem=Decimal('100'),
            cashout_method='bank_transfer',
            rate=rate,
        )

        # Cashout should still succeed even when wallet txn fails
        self.assertTrue(result['success'])
        self.assertEqual(result['cashout'], mock_cashout)

    def test_validate_destination_invalid_bank_account(self):
        """validate_destination returns error when bank account not found."""
        from djoyalty.services.CashoutService import CashoutService

        customer = self._make_customer()

        with patch('djoyalty.services.CashoutService.CustomerBankAccount') as MockBank:
            MockBank.objects.filter.return_value.first.return_value = None
            bank, wallet, err = CashoutService.validate_destination(
                customer=customer, bank_account_id=999
            )

        self.assertIsNone(bank)
        self.assertIsNotNone(err)
        self.assertIn('not found', err)

    def test_validate_destination_valid_bank_account(self):
        """validate_destination returns account when found."""
        from djoyalty.services.CashoutService import CashoutService

        customer = self._make_customer()
        mock_account = MagicMock()

        with patch('djoyalty.services.CashoutService.CustomerBankAccount') as MockBank:
            MockBank.objects.filter.return_value.first.return_value = mock_account
            bank, wallet, err = CashoutService.validate_destination(
                customer=customer, bank_account_id=1
            )

        self.assertEqual(bank, mock_account)
        self.assertIsNone(err)

    def test_get_customer_rate_returns_first_active_rate(self):
        """get_customer_rate returns first active rate for method."""
        from djoyalty.services.CashoutService import CashoutService

        customer = self._make_customer()
        mock_rate = MagicMock()

        with patch('djoyalty.services.CashoutService.CashoutRate') as MockRate:
            MockRate.objects.filter.return_value.order_by.return_value.first.return_value = mock_rate
            result = CashoutService.get_customer_rate(customer, 'bank_transfer')

        self.assertEqual(result, mock_rate)


class TestCashoutServiceReferenceSecurity(TestCase):
    """Verify cashout reference is full UUID (no collision risk)."""

    def test_reference_format_is_full_uuid(self):
        """Reference must be 'CO-' + 32 hex chars (not 8)."""
        import re
        from unittest.mock import patch, MagicMock, PropertyMock
        from djoyalty.services.CashoutService import CashoutService

        created_refs = []

        with patch('djoyalty.services.CashoutService.LoyaltyValidator') as MV, \
             patch('djoyalty.services.CashoutService.LoyaltyPoints') as MLP, \
             patch('djoyalty.services.CashoutService.CashoutRequest') as MCO, \
             patch('djoyalty.services.CashoutService.WalletTransaction'), \
             patch('djoyalty.services.CashoutService.PointsLedger'):

            MV.validate_cashout.return_value = (True, '')
            lp = MagicMock()
            lp.balance = Decimal('1000')
            lp.frozen_balance = Decimal('0')
            type(lp).available_balance = PropertyMock(return_value=Decimal('1000'))
            lp.lifetime_redeemed = Decimal('0')
            MLP.objects.select_for_update.return_value.get.return_value = lp

            mock_cashout = MagicMock()
            mock_cashout.id = 1

            def capture_create(**kwargs):
                created_refs.append(kwargs.get('reference', ''))
                return mock_cashout

            MCO.objects.create.side_effect = capture_create

            customer = MagicMock()
            customer.code = 'TEST'
            customer.is_active = True
            customer.tenant = None
            rate = MagicMock()
            rate.points_per_unit = Decimal('100')
            rate.min_cashout_points = Decimal('50')

            CashoutService.create_request(
                customer=customer,
                points_to_redeem=Decimal('100'),
                cashout_method='bank_transfer',
                rate=rate,
            )

        self.assertTrue(len(created_refs) > 0)
        ref = created_refs[0]
        # Must be CO- + 32 hex chars (full UUID, not 8 chars)
        self.assertRegex(ref, r'^CO-[A-F0-9]{32}$', f'Reference {ref!r} is not full UUID format')
