# tests/test_gateway_router.py
import pytest
from decimal import Decimal
from unittest.mock import patch


@pytest.mark.django_db
class TestGatewayRouterService:
    def test_bd_small_amount_selects_bkash_or_nagad(self, test_user):
        from api.payment_gateways.services.GatewayRouterService import GatewayRouterService
        with patch.object(GatewayRouterService, '_is_available', return_value=True):
            svc    = GatewayRouterService()
            result = svc.select(test_user, Decimal('500'), country='BD')
        assert result['gateway'] in ('bkash', 'nagad', 'sslcommerz', 'amarpay', 'upay', 'shurjopay')

    def test_preferred_gateway_used_when_available(self, test_user):
        from api.payment_gateways.services.GatewayRouterService import GatewayRouterService
        with patch.object(GatewayRouterService, '_is_available', return_value=True):
            svc    = GatewayRouterService()
            result = svc.select(test_user, Decimal('500'), country='BD', preferred='nagad')
        assert result['gateway'] == 'nagad'
        assert result['reason'] == 'user_preferred'

    def test_us_country_selects_ach_or_stripe(self, test_user):
        from api.payment_gateways.services.GatewayRouterService import GatewayRouterService
        with patch.object(GatewayRouterService, '_is_available', return_value=True):
            svc    = GatewayRouterService()
            result = svc.select(test_user, Decimal('1000'), country='US')
        assert result['gateway'] in ('ach', 'stripe', 'paypal')

    def test_no_available_gateway_raises(self, test_user):
        from api.payment_gateways.services.GatewayRouterService import GatewayRouterService
        with patch.object(GatewayRouterService, '_is_available', return_value=False):
            with patch.object(GatewayRouterService, '_get_fallback_list', return_value=[]):
                svc = GatewayRouterService()
                with pytest.raises(Exception, match='No payment gateway'):
                    svc.select(test_user, Decimal('500'), country='BD')
