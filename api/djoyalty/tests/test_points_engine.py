# api/djoyalty/tests/test_points_engine.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_loyalty_points


class PointsEngineTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='ENGCUST01')

    def test_process_earn_basic(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        points = PointsEngine.process_earn(self.customer, Decimal('100'))
        self.assertGreater(points, 0)

    def test_process_earn_creates_loyalty_points(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.models.points import LoyaltyPoints
        PointsEngine.process_earn(self.customer, Decimal('100'))
        self.assertTrue(LoyaltyPoints.objects.filter(customer=self.customer).exists())

    def test_process_earn_creates_ledger_entry(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.models.points import PointsLedger
        PointsEngine.process_earn(self.customer, Decimal('100'))
        self.assertTrue(PointsLedger.objects.filter(customer=self.customer, txn_type='credit').exists())

    def test_process_earn_zero_spend_returns_zero(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        points = PointsEngine.process_earn(self.customer, Decimal('0'))
        self.assertEqual(points, Decimal('0'))

    def test_process_earn_negative_spend_returns_zero(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        points = PointsEngine.process_earn(self.customer, Decimal('-50'))
        self.assertEqual(points, Decimal('0'))

    def test_process_earn_updates_balance(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.models.points import LoyaltyPoints
        PointsEngine.process_earn(self.customer, Decimal('200'))
        PointsEngine.process_earn(self.customer, Decimal('300'))
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertGreater(lp.balance, 0)
        self.assertGreater(lp.lifetime_earned, 0)

    def test_process_earn_decimal_precision(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        points = PointsEngine.process_earn(self.customer, Decimal('99.99'))
        # Points should be a valid Decimal
        self.assertIsInstance(points, Decimal)


class PointsLedgerServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='LEDCUST01')
        self.lp = make_loyalty_points(self.customer, balance=Decimal('500'))

    def test_get_balance_from_ledger(self):
        from djoyalty.services.points.PointsLedgerService import PointsLedgerService
        from djoyalty.models.points import PointsLedger
        PointsLedger.objects.create(
            customer=self.customer, txn_type='credit', source='purchase',
            points=Decimal('200'), balance_after=Decimal('200'),
        )
        balance = PointsLedgerService.get_balance_from_ledger(self.customer)
        self.assertEqual(balance, Decimal('200'))

    def test_get_ledger_history(self):
        from djoyalty.services.points.PointsLedgerService import PointsLedgerService
        from djoyalty.models.points import PointsLedger
        PointsLedger.objects.create(
            customer=self.customer, txn_type='credit', source='purchase',
            points=Decimal('100'), balance_after=Decimal('100'),
        )
        history = PointsLedgerService.get_ledger_history(self.customer)
        self.assertGreaterEqual(len(list(history)), 1)


class PointsAdjustmentServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='ADJCUST01')
        self.lp = make_loyalty_points(self.customer, balance=Decimal('200'))

    def test_positive_adjustment(self):
        from djoyalty.services.points.PointsAdjustmentService import PointsAdjustmentService
        lp = PointsAdjustmentService.adjust(self.customer, Decimal('100'), 'Test credit')
        self.assertEqual(lp.balance, Decimal('300'))

    def test_negative_adjustment(self):
        from djoyalty.services.points.PointsAdjustmentService import PointsAdjustmentService
        lp = PointsAdjustmentService.adjust(self.customer, Decimal('-50'), 'Test debit')
        self.assertEqual(lp.balance, Decimal('150'))

    def test_adjustment_creates_record(self):
        from djoyalty.services.points.PointsAdjustmentService import PointsAdjustmentService
        from djoyalty.models.points import PointsAdjustment
        PointsAdjustmentService.adjust(self.customer, Decimal('50'), 'Record test', adjusted_by='admin')
        self.assertTrue(PointsAdjustment.objects.filter(customer=self.customer, reason='Record test').exists())
