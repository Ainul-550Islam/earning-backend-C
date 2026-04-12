# signals/currency_signals.py
"""Currency rate update signals"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)

try:
    from ..models.core import Currency

    @receiver(post_save, sender=Currency)
    def on_currency_saved(sender, instance, created, **kwargs):
        """Currency save হলে currency cache clear করে"""
        try:
            cache.delete('currencies_list_v1')
            cache.delete(f"exchange_rate_USD_{instance.code}")
            cache.delete(f"exchange_rate_{instance.code}_USD")
            logger.debug(f"Currency cache cleared: {instance.code}")
        except Exception as e:
            logger.error(f"on_currency_saved signal failed: {e}")

except ImportError:
    pass
