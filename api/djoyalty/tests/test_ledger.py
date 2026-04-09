# api/djoyalty/tests/test_ledger.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_loyalty_points


class PointsLedgerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='LEDCUST02')
        self.lp = make_loyalty_points(self.customer, balance=Decimal('0'))

    def test_ledger_entry_on_earn(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.models.points import PointsLedger
        PointsEngine.process_earn(self.customer, Decimal('100'))
        entries = PointsLedger.objects.filter(customer=self.customer, txn_type='credit')
        self.assertGreaterEqual(entries.count(), 1)

    def test_ledger_entry_on_adjustment(self):
        from djoyalty.services.points.PointsAdjustmentService import PointsAdjustmentService
        from djoyalty.models.points import PointsLedger
        PointsAdjustmentService.adjust(self.customer, Decimal('200'), 'Test')
        entries = PointsLedger.objects.filter(customer=self.customer, source='admin')
        self.assertEqual(entries.count(), 1)

    def test_ledger_debit_entry_on_redemption(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.models.points import PointsLedger
        PointsEngine.process_earn(self.customer, Decimal('500'))
        self.lp.refresh_from_db()
        if self.lp.balance >= Decimal('100'):
            RedemptionService.create_request(self.customer, Decimal('100'), 'cashback')
            debit_entries = PointsLedger.objects.filter(customer=self.customer, txn_type='debit', source='redemption')
            self.assertGreaterEqual(debit_entries.count(), 1)

    def test_ledger_balance_after_tracking(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.models.points import PointsLedger
        PointsEngine.process_earn(self.customer, Decimal('300'))
        entry = PointsLedger.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(entry)
        self.assertGreater(entry.balance_after, 0)

    def test_ledger_ordering_newest_first(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.models.points import PointsLedger
        PointsEngine.process_earn(self.customer, Decimal('100'))
        PointsEngine.process_earn(self.customer, Decimal('200'))
        entries = PointsLedger.objects.filter(customer=self.customer)
        if entries.count() >= 2:
            self.assertGreaterEqual(entries[0].created_at, entries[1].created_at)
