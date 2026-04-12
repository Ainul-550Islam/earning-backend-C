# signals/cache_signals.py
"""Model change → cache invalidation signals"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)

CACHE_KEYS_TO_CLEAR_ON_COUNTRY_CHANGE = [
    'countries_list_v1',
]

try:
    from ..models.core import Country

    @receiver(post_save, sender=Country)
    def on_country_saved(sender, instance, **kwargs):
        for key in CACHE_KEYS_TO_CLEAR_ON_COUNTRY_CHANGE:
            cache.delete(key)
        cache.delete(f"country_detail_{instance.code}_False")
        cache.delete(f"country_detail_{instance.code}_True")
        cache.delete(f"content_region_country_{instance.code}")

    @receiver(post_delete, sender=Country)
    def on_country_deleted(sender, instance, **kwargs):
        for key in CACHE_KEYS_TO_CLEAR_ON_COUNTRY_CHANGE:
            cache.delete(key)

except ImportError:
    pass
