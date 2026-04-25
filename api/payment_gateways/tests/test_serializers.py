# FILE 129 of 257 — tests/test_serializers.py
import pytest
from decimal import Decimal
from payment_gateways.serializers import CreatePaymentSerializer, VerifyPaymentSerializer

@pytest.mark.django_db
class TestCreatePaymentSerializer:
    def test_valid_bkash(self):
        s = CreatePaymentSerializer(data={'gateway':'bkash','amount':'500.00'})
        assert s.is_valid(), s.errors

    def test_valid_stripe(self):
        s = CreatePaymentSerializer(data={'gateway':'stripe','amount':'100.00'})
        assert s.is_valid(), s.errors

    def test_invalid_gateway(self):
        s = CreatePaymentSerializer(data={'gateway':'unknown','amount':'100.00'})
        assert not s.is_valid()

    def test_amount_too_low(self):
        s = CreatePaymentSerializer(data={'gateway':'bkash','amount':'1.00'})
        assert not s.is_valid()

    def test_all_eight_gateways(self):
        for gw in ['bkash','nagad','sslcommerz','amarpay','upay','shurjopay','stripe','paypal']:
            s = CreatePaymentSerializer(data={'gateway':gw,'amount':'100.00'})
            assert s.is_valid(), f'{gw} failed: {s.errors}'
