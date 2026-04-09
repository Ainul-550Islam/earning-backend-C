# api/djoyalty/tests/test_expiry.py
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from .factories import make_customer, make_loyalty_points


class PointsExpiryServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='EXPCUST01')
        self.lp = make_loyalty_points(self.customer, balance=Decimal('500'))

    def _create_expiry_record(self, points, days_offset=-1):
        from djoyalty.models.points import PointsExpiry
        return PointsExpiry.objects.create(
            customer=self.customer,
            tenant=self.customer.tenant,
            points=points,
            expires_at=timezone.now() + timedelta(days=days_offset),
            is_processed=False,
        )

    def test_process_expired_points_deducts_balance(self):
        from djoyalty.services.points.PointsExpiryService import PointsExpiryService
        from djoyalty.models.points import LoyaltyPoints
        self._create_expiry_record(Decimal('100'), days_offset=-1)
        PointsExpiryService.process_expired_points()
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertEqual(lp.balance, Decimal('400'))

    def test_process_marks_record_as_processed(self):
        from djoyalty.services.points.PointsExpiryService import PointsExpiryService
        from djoyalty.models.points import PointsExpiry
        record = self._create_expiry_record(Decimal('50'), days_offset=-1)
        PointsExpiryService.process_expired_points()
        record.refresh_from_db()
        self.assertTrue(record.is_processed)
        self.assertIsNotNone(record.processed_at)

    def test_future_expiry_not_processed(self):
        from djoyalty.services.points.PointsExpiryService import PointsExpiryService
        from djoyalty.models.points import PointsExpiry, LoyaltyPoints
        self._create_expiry_record(Decimal('200'), days_offset=30)
        PointsExpiryService.process_expired_points()
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertEqual(lp.balance, Decimal('500'))

    def test_already_processed_not_double_processed(self):
        from djoyalty.services.points.PointsExpiryService import PointsExpiryService
        from djoyalty.models.points import PointsExpiry, LoyaltyPoints
        record = self._create_expiry_record(Decimal('100'), days_offset=-1)
        record.is_processed = True
        record.save()
        PointsExpiryService.process_expired_points()
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertEqual(lp.balance, Decimal('500'))

    def test_expiry_creates_debit_ledger_entry(self):
        from djoyalty.services.points.PointsExpiryService import PointsExpiryService
        from djoyalty.models.points import PointsLedger
        self._create_expiry_record(Decimal('100'), days_offset=-1)
        PointsExpiryService.process_expired_points()
        debit_entries = PointsLedger.objects.filter(customer=self.customer, source='expiry', txn_type='debit')
        self.assertEqual(debit_entries.count(), 1)

    def test_process_returns_count(self):
        from djoyalty.services.points.PointsExpiryService import PointsExpiryService
        self._create_expiry_record(Decimal('100'), days_offset=-1)
        self._create_expiry_record(Decimal('50'), days_offset=-2)
        count = PointsExpiryService.process_expired_points()
        self.assertEqual(count, 2)
