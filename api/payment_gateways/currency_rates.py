# api/payment_gateways/currency_rates.py
from decimal import Decimal
import logging, requests
from django.core.cache import cache
from django.conf import settings
logger=logging.getLogger(__name__)

class CurrencyRateService:
    def sync_from_api(self):
        api_key=getattr(settings,'EXCHANGE_RATE_API_KEY','')
        if not api_key: return self._use_fallback()
        try:
            r=requests.get(f'https://v6.exchangerate-api.com/v6/{api_key}/latest/USD',timeout=10)
            d=r.json()
            rates=d.get('conversion_rates',{})
            from api.payment_gateways.models.core import Currency
            from django.utils import timezone
            updated=0
            for code,rate in rates.items():
                Currency.objects.filter(code=code).update(exchange_rate=Decimal(str(rate)),last_updated=timezone.now())
                cache.set(f'pg:fx:USD:{code}',float(rate),3600)
                updated+=1
            cache.delete('pg:fx:all')
            return {'synced':True,'updated':updated}
        except Exception as e:
            logger.error(f'Currency rate sync failed: {e}')
            return {'synced':False,'error':str(e)}
    def _use_fallback(self):
        HARDCODED={'BDT':110.5,'USD':1.0,'EUR':0.92,'GBP':0.79,'AUD':1.53,'CAD':1.36,'USDT':1.0,'BTC':0.0000155,'ETH':0.00032}
        for code,rate in HARDCODED.items():
            cache.set(f'pg:fx:USD:{code}',rate,3600)
        return {'synced':True,'updated':len(HARDCODED),'source':'fallback'}
    def get_rate(self,currency):
        v=cache.get(f'pg:fx:USD:{currency.upper()}')
        if v: return Decimal(str(v))
        self.sync_from_api()
        v=cache.get(f'pg:fx:USD:{currency.upper()}')
        return Decimal(str(v)) if v else Decimal('1')
currency_rates_service=CurrencyRateService()
