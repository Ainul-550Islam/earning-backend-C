# api/payment_gateways/token_refresh.py
# Gateway API token refresh management
import logging,time
from django.core.cache import cache
logger=logging.getLogger(__name__)

class GatewayTokenManager:
    def get_token(self,gateway):
        cached=cache.get(f'pg:token:{gateway}')
        if cached: return cached
        return self._refresh_token(gateway)
    def _refresh_token(self,gateway):
        try:
            refreshers={'bkash':self._refresh_bkash,'nagad':self._refresh_nagad,'paypal':self._refresh_paypal}
            refresher=refreshers.get(gateway)
            if refresher: return refresher()
        except Exception as e:
            logger.error(f'Token refresh failed for {gateway}: {e}')
        return None
    def _refresh_bkash(self):
        from api.payment_gateways.services.BkashService import BkashService
        try:
            svc=BkashService()
            token=svc.get_access_token()
            cache.set('pg:token:bkash',token,3600)
            return token
        except Exception as e:
            logger.error(f'bKash token refresh: {e}')
        return None
    def _refresh_nagad(self):
        return None
    def _refresh_paypal(self):
        from api.payment_gateways.services.PayPalService import PayPalService
        try:
            svc=PayPalService()
            token=svc._get_access_token()
            cache.set('pg:token:paypal',token,3600)
            return token
        except: return None
    def invalidate(self,gateway):
        cache.delete(f'pg:token:{gateway}')
gateway_token_manager=GatewayTokenManager()
