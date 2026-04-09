# api/djoyalty/tests/test_performance.py
"""Performance tests — query count checks।"""
from decimal import Decimal
from django.test import TestCase
from django.test.utils import override_settings
from .factories import make_customer, make_loyalty_points, make_txn


class QueryCountTest(TestCase):
    """Ensure key operations don't generate excessive DB queries।"""

    def setUp(self):
        self.customers = [make_customer(code=f'PERF{i:04d}') for i in range(10)]
        for c in self.customers:
            make_loyalty_points(c, balance=Decimal('100'))
            make_txn(c, value=Decimal('50'))

    def test_earn_points_query_count(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        customer = make_customer(code='PERF_EARN01')
        make_loyalty_points(customer, balance=Decimal('0'))
        with self.assertNumQueries(7):
            PointsEngine.process_earn(customer, Decimal('100'))

    def test_customer_list_no_n_plus_1(self):
        from djoyalty.models.core import Customer
        with self.assertNumQueries(3):
            customers = list(
                Customer.objects.prefetch_related('transactions', 'events')
                .order_by('-created_at')[:10]
            )
            for c in customers:
                _ = c.transactions.all()

    def test_bulk_earn_performance(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        import time
        start = time.time()
        for customer in self.customers:
            PointsEngine.process_earn(customer, Decimal('100'))
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f'Bulk earn too slow: {elapsed:.2f}s for 10 customers')

    def test_ledger_query_performance(self):
        from djoyalty.services.points.PointsEngine import PointsEngine
        from djoyalty.services.points.PointsLedgerService import PointsLedgerService
        customer = make_customer(code='PERF_LED01')
        for _ in range(20):
            PointsEngine.process_earn(customer, Decimal('10'))
        history = PointsLedgerService.get_ledger_history(customer, limit=50)
        self.assertGreaterEqual(len(list(history)), 1)
