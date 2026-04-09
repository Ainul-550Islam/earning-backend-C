# api/djoyalty/tests/test_fraud.py
from decimal import Decimal
from django.test import TestCase
from .factories import make_customer, make_txn


class LoyaltyFraudServiceTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='FRDCUST01')

    def test_check_rapid_transactions_clean(self):
        from djoyalty.services.advanced.LoyaltyFraudService import LoyaltyFraudService
        result = LoyaltyFraudService.check_rapid_transactions(self.customer)
        self.assertFalse(result)

    def test_check_rapid_transactions_flagged(self):
        from djoyalty.services.advanced.LoyaltyFraudService import LoyaltyFraudService
        from djoyalty.constants import FRAUD_RAPID_TXN_COUNT
        for _ in range(FRAUD_RAPID_TXN_COUNT + 2):
            make_txn(self.customer, value=Decimal('10'))
        result = LoyaltyFraudService.check_rapid_transactions(self.customer)
        self.assertTrue(result)

    def test_rapid_txn_creates_fraud_log(self):
        from djoyalty.services.advanced.LoyaltyFraudService import LoyaltyFraudService
        from djoyalty.models.advanced import PointsAbuseLog
        from djoyalty.constants import FRAUD_RAPID_TXN_COUNT
        for _ in range(FRAUD_RAPID_TXN_COUNT + 2):
            make_txn(self.customer, value=Decimal('10'))
        LoyaltyFraudService.check_rapid_transactions(self.customer)
        logs = PointsAbuseLog.objects.filter(customer=self.customer)
        self.assertGreaterEqual(logs.count(), 1)

    def test_check_daily_redemption_within_limit(self):
        from djoyalty.services.advanced.LoyaltyFraudService import LoyaltyFraudService
        result = LoyaltyFraudService.check_daily_redemption(self.customer, Decimal('100'))
        self.assertFalse(result)

    def test_check_daily_redemption_exceeded(self):
        from djoyalty.services.advanced.LoyaltyFraudService import LoyaltyFraudService
        from djoyalty.constants import FRAUD_MAX_DAILY_REDEMPTION
        result = LoyaltyFraudService.check_daily_redemption(self.customer, FRAUD_MAX_DAILY_REDEMPTION + Decimal('1'))
        self.assertTrue(result)
