# api/djoyalty/tests/test_transfer.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_loyalty_points


class PointsTransferServiceTest(TestCase):

    def setUp(self):
        self.sender = make_customer(code='SNDCUST01')
        self.receiver = make_customer(code='RCVCUST01')
        self.sender_lp = make_loyalty_points(self.sender, balance=Decimal('500'))
        self.receiver_lp = make_loyalty_points(self.receiver, balance=Decimal('100'))

    def test_transfer_success(self):
        from djoyalty.services.points.PointsTransferService import PointsTransferService
        from djoyalty.models.points import LoyaltyPoints
        PointsTransferService.transfer(self.sender, self.receiver, Decimal('200'))
        sender_lp = LoyaltyPoints.objects.get(customer=self.sender)
        receiver_lp = LoyaltyPoints.objects.get(customer=self.receiver)
        self.assertEqual(sender_lp.balance, Decimal('300'))
        self.assertEqual(receiver_lp.balance, Decimal('300'))

    def test_transfer_creates_record(self):
        from djoyalty.services.points.PointsTransferService import PointsTransferService
        from djoyalty.models.points import PointsTransfer
        PointsTransferService.transfer(self.sender, self.receiver, Decimal('100'))
        self.assertTrue(
            PointsTransfer.objects.filter(
                from_customer=self.sender,
                to_customer=self.receiver,
                status='completed',
            ).exists()
        )

    def test_transfer_insufficient_balance(self):
        from djoyalty.services.points.PointsTransferService import PointsTransferService
        from djoyalty.exceptions import InsufficientPointsError
        with self.assertRaises(InsufficientPointsError):
            PointsTransferService.transfer(self.sender, self.receiver, Decimal('9999'))

    def test_transfer_to_self_raises_error(self):
        from djoyalty.services.points.PointsTransferService import PointsTransferService
        from djoyalty.exceptions import PointsTransferError
        with self.assertRaises(PointsTransferError):
            PointsTransferService.transfer(self.sender, self.sender, Decimal('100'))

    def test_transfer_creates_ledger_entries(self):
        from djoyalty.services.points.PointsTransferService import PointsTransferService
        from djoyalty.models.points import PointsLedger
        PointsTransferService.transfer(self.sender, self.receiver, Decimal('150'))
        sender_debit = PointsLedger.objects.filter(customer=self.sender, txn_type='debit', source='transfer')
        receiver_credit = PointsLedger.objects.filter(customer=self.receiver, txn_type='credit', source='transfer')
        self.assertEqual(sender_debit.count(), 1)
        self.assertEqual(receiver_credit.count(), 1)
