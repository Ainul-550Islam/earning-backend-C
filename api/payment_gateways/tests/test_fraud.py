# FILE 141 of 257 — tests/test_fraud.py
import pytest
from decimal import Decimal

@pytest.mark.django_db
class TestVelocityChecker:
    def test_no_transactions_zero_score(self, test_user):
        from payment_gateways.fraud.VelocityChecker import VelocityChecker
        result = VelocityChecker().check(test_user, Decimal('500'), 'bkash')
        assert result['risk_score'] == 0

@pytest.mark.django_db
class TestAnomalyDetector:
    def test_new_account_raises_score(self, db):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from payment_gateways.fraud.AnomalyDetector import AnomalyDetector
        User = get_user_model()
        new_user = User.objects.create_user(
            username='newuser2', email='new2@test.com', password='pass',
            date_joined=timezone.now()
        )
        result = AnomalyDetector()._check_new_account(new_user)
        assert result['score'] > 0

@pytest.mark.django_db
class TestIPBlocklist:
    def test_unblocked_ip_allowed(self, db):
        from payment_gateways.fraud.IPBlocklist import IPBlocklist
        result = IPBlocklist().check('192.168.1.1')
        assert result['blocked'] is False

    def test_block_and_check(self, db):
        from payment_gateways.fraud.IPBlocklist import IPBlocklist
        ipl = IPBlocklist()
        ipl.block('10.0.0.99', 'Test block')
        result = ipl.check('10.0.0.99')
        assert result['blocked'] is True
        ipl.unblock('10.0.0.99')
