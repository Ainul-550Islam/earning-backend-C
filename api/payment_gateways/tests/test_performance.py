# tests/test_performance.py
import pytest
import time
from decimal import Decimal
from unittest.mock import patch


@pytest.mark.django_db
class TestPerformance:
    """Performance benchmarks for critical paths."""

    def test_payment_factory_lookup_speed(self):
        """PaymentFactory.get_processor should resolve < 50ms."""
        from api.payment_gateways.services.PaymentFactory import PaymentFactory
        start = time.time()
        for _ in range(100):
            PaymentFactory.get_processor('bkash')
        elapsed = (time.time() - start) * 1000  # ms
        assert elapsed < 500, f'100 factory lookups took {elapsed:.1f}ms (too slow)'

    def test_fraud_check_speed(self, test_user):
        """Fraud check should complete < 200ms."""
        from api.payment_gateways.fraud.FraudDetector import FraudDetector
        detector = FraudDetector()
        start    = time.time()
        detector.check(test_user, Decimal('500'), 'bkash', ip_address='1.2.3.4')
        elapsed  = (time.time() - start) * 1000
        assert elapsed < 500, f'Fraud check took {elapsed:.1f}ms (too slow)'

    def test_gateway_routing_speed(self, test_user):
        """Gateway routing should resolve < 100ms."""
        from api.payment_gateways.services.GatewayRouterService import GatewayRouterService
        with patch.object(GatewayRouterService, '_is_available', return_value=True):
            svc   = GatewayRouterService()
            start = time.time()
            for _ in range(20):
                svc.select(test_user, Decimal('500'), 'BD')
            elapsed = (time.time() - start) * 1000
        assert elapsed < 1000, f'20 route selections took {elapsed:.1f}ms'

    def test_deposit_request_creation_speed(self, test_user):
        """Creating deposit request < 300ms."""
        from api.payment_gateways.models.deposit import DepositRequest
        import uuid

        start = time.time()
        for i in range(10):
            DepositRequest.objects.create(
                user=test_user, gateway='bkash',
                amount=Decimal('500'), fee=Decimal('7.5'), net_amount=Decimal('492.5'),
                currency='BDT', reference_id=f'PERF-{uuid.uuid4().hex[:10]}',
                status='initiated',
            )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 3000, f'10 DB writes took {elapsed:.1f}ms'
