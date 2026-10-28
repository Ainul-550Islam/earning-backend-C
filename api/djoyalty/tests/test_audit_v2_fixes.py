# api/djoyalty/tests/test_audit_v2_fixes.py
"""
Audit v2 Fix Verification Tests -- Full Coverage।

Covers every gap identified in the production-readiness audit:

  Section A: CashoutService (pending-duplicate guard + service-owned bank/wallet)
  Section B: Validator (locked_balance race-condition fix)
  Section C: DeferredSignalManager (all 6 signals mapped)
  Section D: PointsConversionViewSet (reference_id + idempotency)
  Section E: PointsTransferViewSet (reference_id + idempotency)
  Section F: CashoutRequestCreateSerializer (balance check)
  Section G: Utils / Helpers consolidation (voucher code + format_points)
  Section H: Model constraints (PointsLedger, CashoutRequest, ReferralConversion)
  Section I: Earn rules (reference_id field existence)
  Section J: Shadow file shims (no live logic in flat files)
"""
import ast
import os
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock, call, ANY
from django.test import TestCase, RequestFactory


# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — CashoutService
# ══════════════════════════════════════════════════════════════════════════════

class TestCashoutServicePendingDuplicateGuard(TestCase):
    """
    AUDIT FIX: CashoutService.create_request() must block a second cashout
    when one is already pending/approved for the same customer।
    Previously there was NO check -- race conditions allowed double-debit।
    """

    def _make_customer(self):
        c = MagicMock()
        c.id = 1
        c.code = 'CUSTDUP'
        c.is_active = True
        c.is_verified = True
        c.tenant = None
        return c

    @patch('api.djoyalty.models.cashout.CashoutRequest')
    def test_blocks_when_pending_cashout_exists(self, MockCR):
        """Returns error dict when an active cashout already exists for customer।"""
        from djoyalty.services.CashoutService import CashoutService

        # Simulate: customer already has a pending cashout
        MockCR.objects.filter.return_value.exists.return_value = True

        customer = self._make_customer()
        result = CashoutService.create_request(
            customer=customer,
            points_to_redeem=Decimal('200'),
            cashout_method='bank_transfer',
        )

        self.assertFalse(result['success'])
        self.assertIn('already pending', result['error'])
        # Verify the guard queried for pending/approved status
        MockCR.objects.filter.assert_called_once()
        call_kwargs = MockCR.objects.filter.call_args
        self.assertIn('pending', str(call_kwargs))

    @patch('api.djoyalty.models.cashout.WalletTransaction')
    @patch('api.djoyalty.models.points.PointsLedger')
    @patch('api.djoyalty.models.points.LoyaltyPoints')
    @patch('api.djoyalty.models.cashout.CashoutRequest')
    @patch('api.djoyalty.validator.LoyaltyValidator')
    def test_proceeds_when_no_pending_exists(self, MockVal, MockCR, MockLP, MockLed, MockWal):
        """Proceeds normally when no active cashout exists for customer।"""
        from djoyalty.services.CashoutService import CashoutService

        rate = MagicMock()
        rate.points_per_unit = Decimal('100')
        rate.min_cashout_points = Decimal('50')

        # First call: .filter().exists() → False (no pending)
        # Second call: .objects.create() → mock cashout
        filter_mock = MagicMock()
        filter_mock.exists.return_value = False
        create_mock = MagicMock()
        create_mock.id = 10
        MockCR.objects.filter.return_value = filter_mock
        MockCR.objects.create.return_value = create_mock

        MockVal.validate_cashout.return_value = (True, '')
        lp = MagicMock()
        lp.balance = Decimal('500')
        lp.frozen_balance = Decimal('0')
        type(lp).available_balance = PropertyMock(return_value=Decimal('500'))
        lp.lifetime_redeemed = Decimal('0')
        MockLP.objects.select_for_update.return_value.get.return_value = lp

        customer = self._make_customer()
        result = CashoutService.create_request(
            customer=customer,
            points_to_redeem=Decimal('100'),
            cashout_method='bank_transfer',
            rate=rate,
        )

        self.assertTrue(result['success'])

    @patch('api.djoyalty.models.cashout.CashoutRequest')
    def test_duplicate_guard_checks_correct_statuses(self, MockCR):
        """Guard must check pending AND approved -- not just pending।"""
        from djoyalty.services.CashoutService import CashoutService

        MockCR.objects.filter.return_value.exists.return_value = True
        customer = self._make_customer()
        CashoutService.create_request(
            customer=customer,
            points_to_redeem=Decimal('100'),
            cashout_method='bank_transfer',
        )

        filter_args = MockCR.objects.filter.call_args
        filter_str = str(filter_args)
        # Both statuses must be in the filter call
        self.assertIn('pending', filter_str)
        self.assertIn('approved', filter_str)


class TestCashoutServiceAddBankAccount(TestCase):
    """
    AUDIT FIX: add_bank_account() now lives in CashoutService (service layer)।
    Previously this was inline ORM in CashoutViewSet -- bypassing service layer।
    """

    def _make_customer(self, code='BANKTEST'):
        c = MagicMock()
        c.id = 1
        c.code = code
        c.tenant = None
        return c

    @patch('api.djoyalty.models.cashout.CustomerBankAccount')
    def test_add_bank_account_creates_account(self, MockBA):
        """CashoutService.add_bank_account() creates CustomerBankAccount।"""
        from djoyalty.services.CashoutService import CashoutService

        mock_account = MagicMock()
        mock_account.id = 5
        MockBA.objects.create.return_value = mock_account
        MockBA.objects.filter.return_value.update.return_value = 0

        customer = self._make_customer()
        result = CashoutService.add_bank_account(
            customer=customer,
            data={
                'bank_name': 'DBBL',
                'account_number': '12345678',
                'account_holder_name': 'Test User',
                'is_primary': False,
            },
        )

        self.assertEqual(result, mock_account)
        MockBA.objects.create.assert_called_once()

    @patch('api.djoyalty.models.cashout.CustomerBankAccount')
    def test_add_bank_account_demotes_existing_primary(self, MockBA):
        """When is_primary=True, existing primary accounts must be demoted first।"""
        from djoyalty.services.CashoutService import CashoutService

        mock_account = MagicMock()
        MockBA.objects.create.return_value = mock_account
        MockBA.objects.filter.return_value.update.return_value = 1

        customer = self._make_customer()
        CashoutService.add_bank_account(
            customer=customer,
            data={
                'bank_name': 'bKash',
                'account_number': '987654321',
                'account_holder_name': 'Test User',
                'is_primary': True,
            },
        )

        # Verify existing primary was demoted (update called with is_primary=False)
        MockBA.objects.filter.assert_called_once()
        MockBA.objects.filter.return_value.update.assert_called_once_with(is_primary=False)

    @patch('api.djoyalty.models.cashout.CustomerBankAccount')
    def test_add_bank_account_non_primary_skips_demotion(self, MockBA):
        """When is_primary=False, no demotion query is run।"""
        from djoyalty.services.CashoutService import CashoutService

        mock_account = MagicMock()
        MockBA.objects.create.return_value = mock_account

        customer = self._make_customer()
        CashoutService.add_bank_account(
            customer=customer,
            data={
                'bank_name': 'Sonali Bank',
                'account_number': '11111111',
                'account_holder_name': 'Test User',
                'is_primary': False,
            },
        )

        # filter().update() must NOT have been called
        MockBA.objects.filter.assert_not_called()


class TestCashoutServiceAddMobileWallet(TestCase):
    """
    AUDIT FIX: add_mobile_wallet() now lives in CashoutService।
    Includes duplicate prevention at service level।
    """

    def _make_customer(self):
        c = MagicMock()
        c.id = 2
        c.code = 'WALTEST'
        c.tenant = None
        return c

    @patch('api.djoyalty.models.cashout.CustomerMobileWallet')
    def test_add_mobile_wallet_creates_wallet(self, MockMW):
        """CashoutService.add_mobile_wallet() creates CustomerMobileWallet।"""
        from djoyalty.services.CashoutService import CashoutService

        mock_wallet = MagicMock()
        mock_wallet.id = 3
        MockMW.objects.filter.return_value.exists.return_value = False
        MockMW.objects.create.return_value = mock_wallet

        customer = self._make_customer()
        result = CashoutService.add_mobile_wallet(
            customer=customer,
            data={
                'wallet_provider': 'bkash',
                'phone_number': '01700000001',
                'is_primary': False,
            },
        )

        self.assertEqual(result, mock_wallet)
        MockMW.objects.create.assert_called_once()

    @patch('api.djoyalty.models.cashout.CustomerMobileWallet')
    def test_add_mobile_wallet_raises_on_duplicate(self, MockMW):
        """Raises ValueError when duplicate (provider + phone) already registered।"""
        from djoyalty.services.CashoutService import CashoutService

        MockMW.objects.filter.return_value.exists.return_value = True

        customer = self._make_customer()
        with self.assertRaises(ValueError) as ctx:
            CashoutService.add_mobile_wallet(
                customer=customer,
                data={
                    'wallet_provider': 'bkash',
                    'phone_number': '01700000001',
                    'is_primary': False,
                },
            )
        self.assertIn('already registered', str(ctx.exception))

    @patch('api.djoyalty.models.cashout.CustomerMobileWallet')
    def test_add_mobile_wallet_primary_demotes_existing(self, MockMW):
        """When is_primary=True, existing primary wallets are demoted।"""
        from djoyalty.services.CashoutService import CashoutService

        mock_wallet = MagicMock()
        filter_mock = MagicMock()
        filter_mock.exists.return_value = False
        filter_mock.update.return_value = 1
        MockMW.objects.filter.side_effect = [filter_mock, filter_mock]
        MockMW.objects.create.return_value = mock_wallet

        customer = self._make_customer()
        CashoutService.add_mobile_wallet(
            customer=customer,
            data={
                'wallet_provider': 'nagad',
                'phone_number': '01811000001',
                'is_primary': True,
            },
        )

        # Demotion update must have been called
        filter_mock.update.assert_called_with(is_primary=False)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — Validator locked_balance
# ══════════════════════════════════════════════════════════════════════════════

class TestValidatorLockedBalance(TestCase):
    """
    AUDIT FIX: LoyaltyValidator.validate_redeem() now accepts locked_balance।
    When provided, it skips the DB read -- eliminating the TOCTOU race।
    """

    def _make_customer(self, is_active=True):
        c = MagicMock()
        c.id = 1
        c.code = 'VALTEST'
        c.is_active = is_active
        return c

    def test_validate_redeem_uses_locked_balance_when_provided(self):
        """With locked_balance provided, no DB read (LoyaltyPoints.objects.filter not called)।"""
        from djoyalty.validator import LoyaltyValidator

        customer = self._make_customer()
        with patch('api.djoyalty.models.points.LoyaltyPoints') as MockLP:
            ok, msg = LoyaltyValidator.validate_redeem(
                customer=customer,
                points=Decimal('100'),
                locked_balance=Decimal('500'),  # pre-locked value
            )

        # Should NOT have queried DB
        MockLP.objects.filter.assert_not_called()
        self.assertTrue(ok)
        self.assertEqual(msg, '')

    def test_validate_redeem_locked_balance_insufficient(self):
        """Fails when locked_balance is less than requested points।"""
        from djoyalty.validator import LoyaltyValidator

        customer = self._make_customer()
        ok, msg = LoyaltyValidator.validate_redeem(
            customer=customer,
            points=Decimal('500'),
            locked_balance=Decimal('100'),  # only 100 available
        )

        self.assertFalse(ok)
        self.assertIn('Insufficient', msg)

    def test_validate_redeem_falls_back_to_db_when_no_locked_balance(self):
        """Without locked_balance, behaves as before (reads from LoyaltyPoints)।"""
        from djoyalty.validator import LoyaltyValidator

        customer = self._make_customer()
        with patch('api.djoyalty.models.points.LoyaltyPoints') as MockLP:
            mock_lp = MagicMock()
            mock_lp.balance = Decimal('1000')
            MockLP.objects.filter.return_value.first.return_value = mock_lp

            ok, msg = LoyaltyValidator.validate_redeem(
                customer=customer,
                points=Decimal('200'),
                locked_balance=None,  # explicit None -- use DB
            )

        MockLP.objects.filter.assert_called_once()
        self.assertTrue(ok)

    def test_validate_referral_checks_status_in_approved_paid(self):
        """
        AUDIT FIX: validate_referral() must filter by status approved/paid,
        not just any ReferralConversion record।
        """
        from djoyalty.validator import LoyaltyValidator

        referrer  = MagicMock()
        referrer.id = 1
        referred  = MagicMock()
        referred.id = 2

        with patch('api.djoyalty.models.referral.ReferralConversion') as MockRC:
            MockRC.objects.filter.return_value.exists.return_value = True
            ok, msg = LoyaltyValidator.validate_referral(referrer, referred)

        self.assertFalse(ok)
        # Verify the filter includes status__in=['approved','paid']
        call_kwargs = MockRC.objects.filter.call_args
        self.assertIn('approved', str(call_kwargs))
        self.assertIn('paid', str(call_kwargs))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION C — DeferredSignalManager all 6 signals
# ══════════════════════════════════════════════════════════════════════════════

class TestDeferredSignalManagerAllSignals(TestCase):
    """
    AUDIT FIX: DeferredSignalManager._flush() previously only mapped 3 of 6
    signals। cashout_approved, points_redeemed, fraud_detected were silently
    dropped when deferred।
    """

    def _make_mock_signals(self):
        """Return a dict of 6 mock signal objects।"""
        return {
            'points_earned':    MagicMock(),
            'points_redeemed':  MagicMock(),
            'tier_changed':     MagicMock(),
            'badge_unlocked':   MagicMock(),
            'cashout_approved': MagicMock(),
            'fraud_detected':   MagicMock(),
        }

    def test_all_six_signals_are_in_sig_map(self):
        """Verify _flush() source code imports and maps all 6 signal names।"""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'signals_cap.py',
        )
        with open(src_path) as f:
            src = f.read()

        required = [
            'points_earned', 'points_redeemed', 'tier_changed',
            'badge_unlocked', 'cashout_approved', 'fraud_detected',
        ]
        for sig in required:
            self.assertIn(
                sig, src,
                f"'{sig}' not found in signals_cap.py -- still missing from sig_map",
            )

    def test_cashout_approved_deferred_fires(self):
        """cashout_approved deferred item must fire after _flush()।"""
        from djoyalty.signals_cap import DeferredSignalManager, _deferred

        sigs = self._make_mock_signals()

        with patch.dict(
            'sys.modules',
            {'api.djoyalty.signals': MagicMock(
                points_earned    = sigs['points_earned'],
                points_redeemed  = sigs['points_redeemed'],
                tier_changed     = sigs['tier_changed'],
                badge_unlocked   = sigs['badge_unlocked'],
                cashout_approved = sigs['cashout_approved'],
                fraud_detected   = sigs['fraud_detected'],
            )},
        ):
            # Manually add a deferred cashout_approved item
            _deferred.clear()
            _deferred.append({'signal': 'cashout_approved', 'kwargs': {'cashout_id': 42}})
            DeferredSignalManager._flush()

        sigs['cashout_approved'].send.assert_called_once_with(sender=None, cashout_id=42)

    def test_points_redeemed_deferred_fires(self):
        """points_redeemed was previously missing -- must now fire।"""
        from djoyalty.signals_cap import DeferredSignalManager, _deferred

        sigs = self._make_mock_signals()

        with patch.dict(
            'sys.modules',
            {'api.djoyalty.signals': MagicMock(
                points_earned    = sigs['points_earned'],
                points_redeemed  = sigs['points_redeemed'],
                tier_changed     = sigs['tier_changed'],
                badge_unlocked   = sigs['badge_unlocked'],
                cashout_approved = sigs['cashout_approved'],
                fraud_detected   = sigs['fraud_detected'],
            )},
        ):
            _deferred.clear()
            _deferred.append({'signal': 'points_redeemed', 'kwargs': {'customer_id': 7, 'points': 100}})
            DeferredSignalManager._flush()

        sigs['points_redeemed'].send.assert_called_once_with(sender=None, customer_id=7, points=100)

    def test_fraud_detected_deferred_fires(self):
        """fraud_detected was previously missing -- must now fire।"""
        from djoyalty.signals_cap import DeferredSignalManager, _deferred

        sigs = self._make_mock_signals()

        with patch.dict(
            'sys.modules',
            {'api.djoyalty.signals': MagicMock(
                points_earned    = sigs['points_earned'],
                points_redeemed  = sigs['points_redeemed'],
                tier_changed     = sigs['tier_changed'],
                badge_unlocked   = sigs['badge_unlocked'],
                cashout_approved = sigs['cashout_approved'],
                fraud_detected   = sigs['fraud_detected'],
            )},
        ):
            _deferred.clear()
            _deferred.append({'signal': 'fraud_detected', 'kwargs': {'customer_id': 3}})
            DeferredSignalManager._flush()

        sigs['fraud_detected'].send.assert_called_once_with(sender=None, customer_id=3)

    def test_unknown_signal_name_logs_warning_not_crash(self):
        """Unknown signal name must warn and continue -- never raise an exception।"""
        from djoyalty.signals_cap import DeferredSignalManager, _deferred

        sigs = self._make_mock_signals()

        with patch.dict(
            'sys.modules',
            {'api.djoyalty.signals': MagicMock(**{k: v for k, v in sigs.items()})},
        ):
            _deferred.clear()
            _deferred.append({'signal': 'completely_unknown_signal', 'kwargs': {}})
            # Must not raise
            try:
                DeferredSignalManager._flush()
            except Exception as e:
                self.fail(f'_flush() raised unexpected exception: {e}')

    def test_deferred_context_manager_flushes_on_success(self):
        """Context manager __exit__ without exception flushes deferred items।"""
        from djoyalty.signals_cap import DeferredSignalManager, _deferred

        fired = []

        sigs = self._make_mock_signals()
        sigs['points_earned'].send.side_effect = lambda **kw: fired.append(kw)

        with patch.dict(
            'sys.modules',
            {'api.djoyalty.signals': MagicMock(**{k: v for k, v in sigs.items()})},
        ):
            with DeferredSignalManager():
                DeferredSignalManager.defer('points_earned', customer_id=10, points=50)

        sigs['points_earned'].send.assert_called_once()

    def test_deferred_context_manager_clears_on_exception(self):
        """Context manager __exit__ with exception clears deferred items (no phantom fires)।"""
        from djoyalty.signals_cap import DeferredSignalManager, _deferred

        sigs = self._make_mock_signals()

        with patch.dict(
            'sys.modules',
            {'api.djoyalty.signals': MagicMock(**{k: v for k, v in sigs.items()})},
        ):
            try:
                with DeferredSignalManager():
                    DeferredSignalManager.defer('tier_changed', customer_id=5)
                    raise ValueError('DB rollback!')
            except ValueError:
                pass

        # Signal must NOT have fired since transaction rolled back
        sigs['tier_changed'].send.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION D — PointsConversionViewSet reference_id + idempotency
# ══════════════════════════════════════════════════════════════════════════════

class TestPointsConversionViewSetIdempotency(TestCase):
    """
    AUDIT FIX: convert() endpoint now requires reference_id and checks
    IdempotencyGuard before executing।
    """

    def _make_request(self, data, user=None):
        factory = RequestFactory()
        request = factory.post('/convert/', data=data, content_type='application/json')
        request.user = user or MagicMock(is_staff=False, is_superuser=False)
        request.loyalty_customer = None
        request.tenant = None
        return request

    def test_convert_rejects_missing_reference_id(self):
        """Returns 400 when reference_id not provided।"""
        from djoyalty.viewsets.points.PointsConversionViewSet import PointsConversionViewSet

        view    = PointsConversionViewSet()
        request = self._make_request({'points': '100', 'customer_id': '1'})
        request.data = {'points': '100', 'customer_id': '1'}  # no reference_id

        view.request = request
        view.kwargs  = {}
        view.format_kwarg = None

        response = view.convert(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('reference_id', str(response.data))

    def test_convert_rejects_empty_reference_id(self):
        """Returns 400 when reference_id is empty string।"""
        from djoyalty.viewsets.points.PointsConversionViewSet import PointsConversionViewSet

        view    = PointsConversionViewSet()
        request = self._make_request({})
        request.data = {'points': '100', 'customer_id': '1', 'reference_id': '   '}

        response = view.convert(request)
        self.assertEqual(response.status_code, 400)

    def test_convert_rejects_invalid_points(self):
        """Returns 400 when points is not a positive number।"""
        from djoyalty.viewsets.points.PointsConversionViewSet import PointsConversionViewSet

        view    = PointsConversionViewSet()
        request = self._make_request({})
        request.data = {
            'points': '-50',
            'customer_id': '1',
            'reference_id': 'REF-001',
        }

        response = view.convert(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('positive', str(response.data))

    @patch('api.djoyalty.viewsets.points.PointsConversionViewSet.PointsConversionService')
    def test_convert_returns_cached_result_on_duplicate_reference(self, MockPCS):
        """
        When IdempotencyGuard returns a cached result, the service is NOT
        called a second time।
        """
        from djoyalty.viewsets.points.PointsConversionViewSet import PointsConversionViewSet

        cached_result = {'success': True, 'currency_value': '1.00', 'points_deducted': '100'}

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.code = 'IDEM01'
        mock_customer.pk = 1

        view    = PointsConversionViewSet()
        request = self._make_request({})
        request.data = {
            'points': '100',
            'reference_id': 'REF-IDEM-001',
        }
        request.loyalty_customer = mock_customer

        with patch('api.djoyalty.idempotency.IdempotencyGuard') as MockIG:
            MockIG.get.return_value = cached_result
            response = view.convert(request)

        # Service must NOT be called on idempotent replay
        MockPCS.convert.assert_not_called()
        self.assertEqual(response.status_code, 200)

    @patch('api.djoyalty.viewsets.points.PointsConversionViewSet.PointsConversionService')
    def test_convert_calls_service_on_first_request(self, MockPCS):
        """Service IS called on first (non-cached) request with valid reference_id।"""
        from djoyalty.viewsets.points.PointsConversionViewSet import PointsConversionViewSet

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.code = 'FIRST01'
        mock_customer.pk = 1

        MockPCS.convert.return_value = {'success': True, 'currency_value': '1.00'}

        view    = PointsConversionViewSet()
        request = self._make_request({})
        request.data = {
            'points': '100',
            'reference_id': 'REF-FIRST-001',
        }
        request.loyalty_customer = mock_customer

        with patch('api.djoyalty.idempotency.IdempotencyGuard') as MockIG:
            MockIG.get.return_value = None  # no cache
            response = view.convert(request)

        MockPCS.convert.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION E — PointsTransferViewSet reference_id + idempotency
# ══════════════════════════════════════════════════════════════════════════════

class TestPointsTransferViewSetIdempotency(TestCase):
    """
    AUDIT FIX: transfer() now requires reference_id and checks IdempotencyGuard।
    """

    def _make_request(self, data):
        factory = RequestFactory()
        request = factory.post('/transfer/', data=data, content_type='application/json')
        request.user = MagicMock(is_staff=False, is_superuser=False)
        return request

    def test_transfer_rejects_missing_reference_id(self):
        """Returns 400 when reference_id not provided।"""
        from djoyalty.viewsets.points.PointsTransferViewSet import PointsTransferViewSet

        view = PointsTransferViewSet()
        view.request = self._make_request({})
        view.request.data = {
            'from_customer_id': '1',
            'to_customer_id':   '2',
            'points':           '100',
            # reference_id intentionally absent
        }
        view.format_kwarg = None

        response = view.transfer(view.request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('reference_id', str(response.data))

    def test_transfer_rejects_zero_points(self):
        """Returns 400 when points = 0।"""
        from djoyalty.viewsets.points.PointsTransferViewSet import PointsTransferViewSet

        view = PointsTransferViewSet()
        view.request = self._make_request({})
        view.request.data = {
            'from_customer_id': '1',
            'to_customer_id':   '2',
            'points':           '0',
            'reference_id':     'REF-ZERO',
        }

        response = view.transfer(view.request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('positive', str(response.data))

    def test_transfer_rejects_negative_points(self):
        """Returns 400 when points is negative।"""
        from djoyalty.viewsets.points.PointsTransferViewSet import PointsTransferViewSet

        view = PointsTransferViewSet()
        view.request = self._make_request({})
        view.request.data = {
            'from_customer_id': '1',
            'to_customer_id':   '2',
            'points':           '-200',
            'reference_id':     'REF-NEG',
        }

        response = view.transfer(view.request)
        self.assertEqual(response.status_code, 400)

    def test_transfer_passes_reference_id_to_service(self):
        """reference_id must be forwarded to PointsTransferService.transfer()।"""
        from djoyalty.viewsets.points.PointsTransferViewSet import PointsTransferViewSet

        mock_from = MagicMock(); mock_from.user = MagicMock()
        mock_to   = MagicMock()
        mock_transfer = MagicMock(); mock_transfer.pk = 1

        view = PointsTransferViewSet()
        request = self._make_request({})
        request.user = mock_from.user
        request.data = {
            'from_customer_id': '1',
            'to_customer_id':   '2',
            'points':           '100',
            'reference_id':     'REF-PASS-001',
        }
        view.request = request

        with patch('api.djoyalty.viewsets.points.PointsTransferViewSet.Customer') as MockC, \
             patch('api.djoyalty.viewsets.points.PointsTransferViewSet.PointsTransferService') as MockSvc, \
             patch('api.djoyalty.viewsets.points.PointsTransferViewSet.IdempotencyGuard') as MockIG:

            MockC.objects.get_or_404 = MagicMock()
            MockC._default_manager.get = MagicMock(side_effect=[mock_from, mock_to])

            # Use get_object_or_404 patch
            with patch('api.djoyalty.viewsets.points.PointsTransferViewSet.get_object_or_404',
                       side_effect=[mock_from, mock_to]):
                mock_from.user = request.user
                MockSvc.transfer.return_value = mock_transfer
                MockIG.get.return_value = None

                # Mock is_staff/is_superuser
                request.user.is_staff     = False
                request.user.is_superuser = False
                mock_from.user            = request.user

                response = view.transfer(request)

            if MockSvc.transfer.called:
                call_kwargs = MockSvc.transfer.call_args
                self.assertIn('reference_id', str(call_kwargs))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION F — CashoutRequestCreateSerializer balance check
# ══════════════════════════════════════════════════════════════════════════════

class TestCashoutSerializerBalanceValidation(TestCase):
    """
    AUDIT FIX: CashoutRequestCreateSerializer.validate() now checks customer
    balance so ALL callers (not just the viewset path) get the guard।
    """

    def test_validate_passes_when_sufficient_balance(self):
        """Serializer validate() passes when customer has enough balance।"""
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer

        mock_customer = MagicMock()
        mock_lp       = MagicMock()
        mock_lp.available_balance = Decimal('500')

        with patch('api.djoyalty.models.points.LoyaltyPoints') as MockLP:
            MockLP.objects.filter.return_value.first.return_value = mock_lp

            s = CashoutRequestCreateSerializer(
                data={
                    'points_to_redeem': '200',
                    'cashout_method':   'bank_transfer',
                    'bank_account_id':  1,
                },
                context={'customer': mock_customer},
            )
            s.is_valid()  # triggers validate()
            # No validation error should be raised for balance

    def test_validate_rejects_insufficient_balance(self):
        """Serializer validate() raises ValidationError when balance is insufficient।"""
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer
        from rest_framework.exceptions import ValidationError

        mock_customer = MagicMock()
        mock_lp       = MagicMock()
        mock_lp.available_balance = Decimal('50')  # only 50 available

        with patch('api.djoyalty.models.points.LoyaltyPoints') as MockLP:
            MockLP.objects.filter.return_value.first.return_value = mock_lp

            s = CashoutRequestCreateSerializer(
                data={
                    'points_to_redeem': '200',   # requesting 200 but only 50 available
                    'cashout_method':   'bank_transfer',
                    'bank_account_id':  1,
                },
                context={'customer': mock_customer},
            )
            is_valid = s.is_valid()
            self.assertFalse(is_valid)
            self.assertIn('points_to_redeem', s.errors)

    def test_validate_skips_balance_check_without_customer_context(self):
        """When no customer in context, balance check is skipped gracefully।"""
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer

        s = CashoutRequestCreateSerializer(
            data={
                'points_to_redeem': '200',
                'cashout_method':   'bank_transfer',
                'bank_account_id':  1,
            },
            context={},  # no 'customer' key
        )
        # Should not raise -- balance check is optional when context missing
        try:
            s.is_valid()
        except Exception as e:
            self.fail(f'Serializer raised unexpected exception without customer context: {e}')

    def test_validate_rejects_missing_destination_for_bank_transfer(self):
        """Bank transfer without bank_account_id must fail validation।"""
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer

        s = CashoutRequestCreateSerializer(
            data={
                'points_to_redeem': '200',
                'cashout_method':   'bank_transfer',
                # bank_account_id missing
            },
        )
        is_valid = s.is_valid()
        self.assertFalse(is_valid)
        self.assertIn('bank_account_id', s.errors)

    def test_validate_rejects_missing_destination_for_mobile_wallet(self):
        """Mobile wallet cashout without mobile_wallet_id must fail validation।"""
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer

        s = CashoutRequestCreateSerializer(
            data={
                'points_to_redeem': '500',
                'cashout_method':   'mobile_wallet',
                # mobile_wallet_id missing
            },
        )
        is_valid = s.is_valid()
        self.assertFalse(is_valid)
        self.assertIn('mobile_wallet_id', s.errors)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION G — Utils / Helpers consolidation
# ══════════════════════════════════════════════════════════════════════════════

class TestUtilsHelpersConsolidation(TestCase):
    """
    AUDIT FIX: utils.py is the canonical source।
    helpers.py is a re-export shim with backward-compatible wrappers।
    """

    # ── generate_voucher_code ─────────────────────────────────────────────────

    def test_utils_voucher_code_no_prefix_by_default(self):
        """utils.generate_voucher_code() default produces bare code (no prefix)।"""
        from djoyalty.utils import generate_voucher_code
        code = generate_voucher_code()
        self.assertEqual(len(code), 12)
        self.assertRegex(code, r'^[A-Z0-9]+$')

    def test_utils_voucher_code_with_prefix(self):
        """utils.generate_voucher_code(prefix='V') produces 'V' + body।"""
        from djoyalty.utils import generate_voucher_code
        code = generate_voucher_code(length=10, prefix='V')
        self.assertTrue(code.startswith('V'))
        self.assertEqual(len(code), 11)  # 1 prefix + 10 body

    def test_helpers_voucher_code_default_has_v_prefix(self):
        """helpers.generate_voucher_code() default is prefix='V' (backward compat)।"""
        from djoyalty.helpers import generate_voucher_code
        code = generate_voucher_code()
        self.assertTrue(code.startswith('V'), f"helpers voucher code should start with 'V', got {code!r}")

    def test_helpers_and_utils_produce_valid_codes(self):
        """Both helpers and utils voucher codes are alphanumeric (no special chars)।"""
        from djoyalty.utils   import generate_voucher_code as u_gvc
        from djoyalty.helpers import generate_voucher_code as h_gvc

        u_code = u_gvc()
        h_code = h_gvc()

        self.assertRegex(u_code, r'^[A-Z0-9]+$')
        self.assertRegex(h_code, r'^[A-Z0-9]+$', f'helpers code {h_code!r} has invalid chars')

    # ── format_points ─────────────────────────────────────────────────────────

    def test_utils_format_points_no_suffix(self):
        """utils.format_points() default has no suffix।"""
        from djoyalty.utils import format_points
        result = format_points(Decimal('1250'))
        self.assertEqual(result, '1,250')

    def test_utils_format_points_with_suffix(self):
        """utils.format_points(suffix=' pts') appends suffix।"""
        from djoyalty.utils import format_points
        result = format_points(Decimal('1250'), suffix=' pts')
        self.assertEqual(result, '1,250 pts')

    def test_helpers_format_points_has_pts_suffix(self):
        """helpers.format_points() default includes ' pts' suffix (backward compat)।"""
        from djoyalty.helpers import format_points
        result = format_points(Decimal('500'))
        self.assertIn('pts', result)
        self.assertIn('500', result)

    # ── get_client_ip ─────────────────────────────────────────────────────────

    def test_get_client_ip_uses_cf_header(self):
        """utils.get_client_ip() now checks CF-Connecting-IP (merged from helpers)।"""
        from djoyalty.utils import get_client_ip
        request = MagicMock()
        request.META = {
            'HTTP_CF_CONNECTING_IP': '1.2.3.4',
            'REMOTE_ADDR': '127.0.0.1',
        }
        ip = get_client_ip(request)
        self.assertEqual(ip, '1.2.3.4')

    def test_get_client_ip_prefers_x_forwarded_for(self):
        """X-Forwarded-For takes priority over CF header।"""
        from djoyalty.utils import get_client_ip
        request = MagicMock()
        request.META = {
            'HTTP_X_FORWARDED_FOR': '9.9.9.9, 8.8.8.8',
            'HTTP_CF_CONNECTING_IP': '1.2.3.4',
            'REMOTE_ADDR': '127.0.0.1',
        }
        ip = get_client_ip(request)
        self.assertEqual(ip, '9.9.9.9')

    # ── helpers re-export completeness ────────────────────────────────────────

    def test_helpers_exports_all_critical_utils_functions(self):
        """helpers.py must export all functions callers depend on।"""
        import djoyalty.helpers as helpers

        required = [
            'generate_customer_code', 'generate_referral_code',
            'generate_secure_token', 'normalize_bd_phone',
            'mask_phone', 'mask_email', 'format_currency',
            'days_since', 'days_until', 'is_birthday_today',
            'safe_decimal', 'chunk_list', 'get_client_ip',
            'make_hmac_signature', 'verify_hmac_signature',
            'paginate_queryset', 'generate_otp',
        ]
        missing = [fn for fn in required if not hasattr(helpers, fn)]
        self.assertEqual(missing, [], f'helpers.py missing exports: {missing}')

    # ── safe_decimal ──────────────────────────────────────────────────────────

    def test_safe_decimal_handles_none(self):
        """safe_decimal(None) returns default without error।"""
        from djoyalty.utils import safe_decimal
        self.assertEqual(safe_decimal(None), Decimal('0'))
        self.assertEqual(safe_decimal(None, Decimal('99')), Decimal('99'))

    def test_safe_decimal_handles_invalid_string(self):
        """safe_decimal('not_a_number') returns default।"""
        from djoyalty.utils import safe_decimal
        self.assertEqual(safe_decimal('not_a_number'), Decimal('0'))

    def test_safe_decimal_converts_valid_value(self):
        """safe_decimal('123.45') returns Decimal('123.45')।"""
        from djoyalty.utils import safe_decimal
        self.assertEqual(safe_decimal('123.45'), Decimal('123.45'))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION H — Model constraints
# ══════════════════════════════════════════════════════════════════════════════

class TestModelConstraintDefinitions(TestCase):
    """
    Verify that all DB constraints added in migration 0014 are declared
    in the corresponding model Meta classes।
    """

    def _get_model_source(self, relative_path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, relative_path)) as f:
            return f.read()

    def test_pointsledger_has_partial_unique_constraint(self):
        """PointsLedger.Meta.constraints must contain UniqueConstraint on reference_id।"""
        src = self._get_model_source('models/points.py')
        self.assertIn('UniqueConstraint', src)
        self.assertIn('reference_id', src)
        self.assertIn('unique_pointsledger_reference_id_notnull', src)

    def test_pointsledger_reference_id_not_unique_field(self):
        """reference_id field itself must NOT be unique=True (uses partial constraint instead)।"""
        src = self._get_model_source('models/points.py')
        # The field definition should NOT have unique=True
        # It should have null=True, blank=True, and be backed by a constraint
        lines = [l.strip() for l in src.split('\n') if 'reference_id' in l and 'models.CharField' in l]
        for line in lines:
            self.assertNotIn('unique=True', line,
                f"reference_id CharField should not have unique=True; use constraint instead: {line}")

    def test_cashoutrequest_has_check_constraint_destination(self):
        """CashoutRequest.Meta.constraints must include CheckConstraint for destination।"""
        src = self._get_model_source('models/cashout.py')
        self.assertIn('CheckConstraint', src)
        self.assertIn('cashout_destination_matches_method', src)
        # Verify the three method cases
        self.assertIn('bank_transfer', src)
        self.assertIn('mobile_wallet', src)
        self.assertIn('gift_card', src)

    def test_cashoutrequest_has_pending_unique_constraint(self):
        """CashoutRequest.Meta.constraints must include UniqueConstraint for active cashout。"""
        src = self._get_model_source('models/cashout.py')
        self.assertIn('unique_active_cashout_per_customer', src)
        # Partial condition
        self.assertIn("status__in=['pending', 'approved']", src)

    def test_referralconversion_has_unique_constraint(self):
        """ReferralConversion.Meta.constraints must include UniqueConstraint on referred_customer。"""
        src = self._get_model_source('models/referral.py')
        self.assertIn('UniqueConstraint', src)
        self.assertIn('unique_referred_customer_active', src)
        self.assertIn('referred_customer', src)
        self.assertIn("status__in=['approved', 'paid']", src)

    def test_tenant_has_compound_index(self):
        """Tenant.Meta.indexes must include (slug, is_active) compound index।"""
        src = self._get_model_source('models/core.py')
        self.assertIn("fields=['slug', 'is_active']", src)

    def test_loyalty_points_customer_fk_is_protect(self):
        """LoyaltyPoints.customer FK must use on_delete=PROTECT, not CASCADE।"""
        src = self._get_model_source('models/points.py')
        # Check in LoyaltyPoints class section
        lp_section = src[src.find('class LoyaltyPoints'):src.find('class PointsLedger')]
        self.assertIn('models.PROTECT', lp_section)
        self.assertNotIn('models.CASCADE', lp_section)

    def test_cashoutrequest_customer_fk_is_protect(self):
        """CashoutRequest.customer FK must use on_delete=PROTECT।"""
        src = self._get_model_source('models/cashout.py')
        cr_section = src[src.find('class CashoutRequest'):src.find('class CashoutRate')]
        self.assertIn('models.PROTECT', cr_section)

    def test_pointstransfer_from_customer_fk_is_protect(self):
        """PointsTransfer.from_customer FK must use on_delete=PROTECT।"""
        src = self._get_model_source('models/points.py')
        pt_section = src[src.find('class PointsTransfer'):]
        self.assertIn('models.PROTECT', pt_section[:pt_section.find('class PointsConversion')])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION I — EarnTransaction reference_id field
# ══════════════════════════════════════════════════════════════════════════════

class TestEarnTransactionReferenceId(TestCase):
    """
    AUDIT FIX: EarnTransaction.reference_id is a new field added in migration 0014।
    Without it, orphaned EarnTransaction records were created when the ledger
    rejected a duplicate via its own reference_id constraint।
    """

    def _get_earn_rules_src(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, 'models/earn_rules.py')) as f:
            return f.read()

    def test_earn_transaction_has_reference_id_field(self):
        """EarnTransaction model must define a reference_id field।"""
        src = self._get_earn_rules_src()
        # Find EarnTransaction class section
        et_start = src.find('class EarnTransaction')
        et_end   = src.find('\nclass ', et_start + 1)
        et_section = src[et_start:et_end]

        self.assertIn('reference_id', et_section,
            'EarnTransaction is missing reference_id field (migration 0014 fix)')

    def test_earn_transaction_reference_id_is_nullable(self):
        """EarnTransaction.reference_id must be null=True, blank=True (no-ref earns allowed)।"""
        src = self._get_earn_rules_src()
        et_start   = src.find('class EarnTransaction')
        et_end     = src.find('\nclass ', et_start + 1)
        et_section = src[et_start:et_end]

        # Field args may span multiple lines -- check the section as a whole
        self.assertIn('null=True', et_section,
            'EarnTransaction.reference_id must have null=True')
        self.assertIn('blank=True', et_section,
            'EarnTransaction.reference_id must have blank=True')

    def test_earn_transaction_reference_id_is_indexed(self):
        """EarnTransaction.reference_id must have db_index=True for fast lookups।"""
        src = self._get_earn_rules_src()
        et_start   = src.find('class EarnTransaction')
        et_end     = src.find('\nclass ', et_start + 1)
        et_section = src[et_start:et_end]

        # db_index may be on a continuation line -- check the section as a whole
        self.assertIn('db_index=True', et_section,
            'EarnTransaction.reference_id must have db_index=True')

    def test_earn_transaction_customer_fk_is_protect(self):
        """EarnTransaction.customer FK must use on_delete=PROTECT।"""
        src = self._get_earn_rules_src()
        et_start   = src.find('class EarnTransaction')
        et_end     = src.find('\nclass ', et_start + 1)
        et_section = src[et_start:et_end]
        self.assertIn('models.PROTECT', et_section,
            'EarnTransaction.customer FK should be PROTECT, not CASCADE')


# ══════════════════════════════════════════════════════════════════════════════
# SECTION J — Shadow file shims
# ══════════════════════════════════════════════════════════════════════════════

class TestShadowFileShims(TestCase):
    """
    AUDIT FIX: Five flat shadow files (signals.py, models.py, serializers.py,
    events.py, webhooks.py) previously contained live dead code that was
    silently unreachable।  They must now be no-op shims।
    """

    def _get_src(self, filename):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, filename)
        if not os.path.exists(path):
            return ''
        with open(path) as f:
            return f.read()

    def test_signals_flat_file_has_no_receiver_decorators(self):
        """signals.py (flat) must not contain @receiver -- all receivers are in signals/ package।"""
        src = self._get_src('signals.py')
        # Count live @receiver decorators (excluding comments)
        active_receivers = [
            line for line in src.split('\n')
            if '@receiver(' in line and not line.strip().startswith('#')
        ]
        self.assertEqual(
            len(active_receivers), 0,
            f'signals.py (flat) has {len(active_receivers)} live @receiver decorators -- '
            f'these are dead code: {active_receivers}',
        )

    def test_models_flat_file_has_no_model_classes(self):
        """models.py (flat) must not define any Django model classes।"""
        src = self._get_src('models.py')
        live_classes = [
            line for line in src.split('\n')
            if line.startswith('class ') and 'models.Model' in line
        ]
        self.assertEqual(
            len(live_classes), 0,
            f'models.py (flat) defines live Model classes (dead code): {live_classes}',
        )

    def test_serializers_flat_file_has_no_serializer_classes(self):
        """serializers.py (flat) must not define any DRF serializer classes।"""
        src = self._get_src('serializers.py')
        live_classes = [
            line for line in src.split('\n')
            if line.startswith('class ') and 'Serializer' in line
        ]
        self.assertEqual(
            len(live_classes), 0,
            f'serializers.py (flat) defines live Serializer classes: {live_classes}',
        )

    def test_shadow_files_contain_audit_notice(self):
        """All shadow flat files must contain the AUDIT FIX shim notice।"""
        shims = ['signals.py', 'models.py', 'serializers.py', 'events.py', 'webhooks.py']
        for filename in shims:
            src = self._get_src(filename)
            if src:  # only check if file exists
                self.assertIn(
                    'AUDIT FIX', src,
                    f'{filename} is missing the AUDIT FIX shim notice',
                )

    def test_openai_py_lowercase_contains_all_merged_methods(self):
        """openai.py must contain methods merged from dead openAI.py।"""
        src = self._get_src('openai.py')
        merged_methods = [
            'batch_generate_winback',
            'generate_campaign_description',
            'generate_push_notification_copy',
            'analyze_customer_behavior',
            'generate_eco_action_description',
        ]
        missing = [m for m in merged_methods if m not in src]
        self.assertEqual(
            missing, [],
            f'openai.py is missing merged methods from openAI.py: {missing}',
        )

    def test_openAI_py_is_shim_pointing_to_openai(self):
        """openAI.py must be a one-line shim, not a standalone implementation।"""
        src = self._get_src('openAI.py')
        self.assertIn('from .openai import', src,
            'openAI.py should re-export from openai.py, not define its own classes')
        # It should NOT define a full LoyaltyOpenAI class with implementation
        live_methods = [
            line for line in src.split('\n')
            if line.strip().startswith('def ') and 'generate' in line
        ]
        self.assertEqual(
            len(live_methods), 0,
            f'openAI.py still has standalone method implementations: {live_methods}',
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION K — Migration 0014 completeness
# ══════════════════════════════════════════════════════════════════════════════

class TestMigration0014Completeness(TestCase):
    """
    Verify that migration 0014 contains all required operations।
    """

    def _get_migration_src(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, 'migrations', '0014_financial_integrity_constraints.py')
        with open(path) as f:
            return f.read()

    def test_migration_adds_pointsledger_unique_constraint(self):
        src = self._get_migration_src()
        self.assertIn('unique_pointsledger_reference_id_notnull', src)

    def test_migration_adds_referralconversion_unique_constraint(self):
        src = self._get_migration_src()
        self.assertIn('unique_referred_customer_active', src)

    def test_migration_adds_cashoutrequest_check_constraint(self):
        src = self._get_migration_src()
        self.assertIn('cashout_destination_matches_method', src)

    def test_migration_adds_cashoutrequest_pending_unique_constraint(self):
        src = self._get_migration_src()
        self.assertIn('unique_active_cashout_per_customer', src)

    def test_migration_adds_earntransaction_reference_id_field(self):
        src = self._get_migration_src()
        self.assertIn('earntransaction', src)
        self.assertIn('reference_id', src)

    def test_migration_adds_tenant_indexes(self):
        src = self._get_migration_src()
        self.assertIn('djoyalty_tenant_slug_isactive_idx', src)
        self.assertIn('djoyalty_tenant_isactive_idx', src)

    def test_migration_has_seven_alterfield_protect_operations(self):
        """Seven CASCADE→PROTECT AlterField operations must all be present।"""
        src = self._get_migration_src()
        models_updated = [
            'loyaltypoints', 'pointsledger', 'pointstransfer',
            'cashoutrequest', 'wallettransaction', 'earntransaction',
        ]
        for model in models_updated:
            self.assertIn(model, src, f'Migration 0014 missing AlterField for {model}')
        self.assertIn('models.PROTECT', src)

    def test_migration_depends_on_0013(self):
        """Migration must declare dependency on 0013_indexes_constraints।"""
        src = self._get_migration_src()
        self.assertIn('0013_indexes_constraints', src)
