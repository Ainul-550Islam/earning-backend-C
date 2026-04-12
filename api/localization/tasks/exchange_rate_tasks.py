# tasks/exchange_rate_tasks.py
"""Celery task: fetch exchange rates every hour"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.exchange_rate_tasks.update_rates')
    def update_exchange_rates():
        """All currencies-এর exchange rates update করে — hourly"""
        try:
            from ..services.currency.CurrencyRateProvider import CurrencyRateProvider
            from ..models.core import Currency
            from ..models.currency import ExchangeRate
            from django.utils import timezone
            provider = CurrencyRateProvider()
            result = provider.fetch_rates('USD', 'exchangerate-api')
            if not result.get('success'):
                logger.error(f"Rate fetch failed: {result.get('error')}")
                return {'success': False}
            rates = result['rates']
            updated = 0
            for currency_code, rate in rates.items():
                try:
                    from_curr = Currency.objects.filter(code='USD').first()
                    to_curr = Currency.objects.filter(code=currency_code).first()
                    if from_curr and to_curr:
                        ExchangeRate.objects.create(
                            from_currency=from_curr,
                            to_currency=to_curr,
                            rate=rate,
                            date=timezone.now().date(),
                            source='exchangerate-api',
                        )
                        # Update the Currency model exchange_rate field
                        to_curr.exchange_rate = rate
                        to_curr.exchange_rate_updated_at = timezone.now()
                        to_curr.save(update_fields=['exchange_rate', 'exchange_rate_updated_at'])
                        updated += 1
                except Exception as e:
                    logger.error(f"Rate update failed for {currency_code}: {e}")
            logger.info(f"Exchange rates updated: {updated} currencies")
            return {'success': True, 'updated': updated}
        except Exception as e:
            logger.error(f"update_exchange_rates task failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    logger.warning("Celery not installed — tasks disabled")
