# api/djoyalty/tests/test_redemption.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_loyalty_points


class RedemptionServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='REDCUST01')
        self.lp = make_loyalty_points(self.customer, balance=Decimal('1000'))

    def test_create_request_success(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.models.redemption import RedemptionRequest
        req = RedemptionService.create_request(self.customer, Decimal('100'), 'cashback')
        self.assertIsNotNone(req)
        self.assertEqual(req.status, 'pending')
        self.assertEqual(req.points_used, Decimal('100'))

    def test_create_request_deducts_balance(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.models.points import LoyaltyPoints
        RedemptionService.create_request(self.customer, Decimal('200'), 'cashback')
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertEqual(lp.balance, Decimal('800'))

    def test_create_request_insufficient_points(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.exceptions import InsufficientPointsError
        with self.assertRaises(InsufficientPointsError):
            RedemptionService.create_request(self.customer, Decimal('9999'), 'cashback')

    def test_create_request_below_minimum(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.exceptions import RedemptionMinimumNotMetError
        with self.assertRaises(RedemptionMinimumNotMetError):
            RedemptionService.create_request(self.customer, Decimal('1'), 'cashback')

    def test_approve_request(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        req = RedemptionService.create_request(self.customer, Decimal('100'), 'cashback')
        approved = RedemptionService.approve(req.id, reviewed_by='admin')
        self.assertEqual(approved.status, 'approved')
        self.assertEqual(approved.reviewed_by, 'admin')

    def test_reject_request_refunds_points(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.models.points import LoyaltyPoints
        req = RedemptionService.create_request(self.customer, Decimal('300'), 'cashback')
        RedemptionService.reject(req.id, reason='Fraud', reviewed_by='admin')
        lp = LoyaltyPoints.objects.get(customer=self.customer)
        self.assertEqual(lp.balance, Decimal('1000'))

    def test_approve_already_approved_raises_error(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.exceptions import RedemptionAlreadyProcessedError
        req = RedemptionService.create_request(self.customer, Decimal('100'), 'cashback')
        RedemptionService.approve(req.id)
        with self.assertRaises(RedemptionAlreadyProcessedError):
            RedemptionService.approve(req.id)

    def test_create_request_creates_ledger_entry(self):
        from djoyalty.services.redemption.RedemptionService import RedemptionService
        from djoyalty.models.points import PointsLedger
        RedemptionService.create_request(self.customer, Decimal('100'), 'cashback')
        self.assertTrue(
            PointsLedger.objects.filter(customer=self.customer, source='redemption').exists()
        )
