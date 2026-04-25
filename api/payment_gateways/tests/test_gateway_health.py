# tests/test_gateway_health.py
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestGatewayHealthService:
    def test_check_single_healthy(self):
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        with patch('requests.head') as mock:
            mock.return_value = MagicMock(status_code=200)
            svc    = GatewayHealthService()
            result = svc.check_single('bkash')
        assert result['status'] in ('healthy', 'degraded', 'unknown')

    def test_check_single_timeout(self):
        import requests
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        with patch('requests.head', side_effect=requests.exceptions.Timeout):
            svc    = GatewayHealthService()
            result = svc.check_single('stripe')
        assert result['status'] == 'timeout'

    def test_check_single_down(self):
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        with patch('requests.head') as mock:
            mock.return_value = MagicMock(status_code=503)
            svc    = GatewayHealthService()
            result = svc.check_single('nagad')
        assert result['status'] == 'down'
