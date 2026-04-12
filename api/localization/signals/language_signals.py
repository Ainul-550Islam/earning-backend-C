# signals/language_signals.py
"""Language activate/deactivate signals"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)

try:
    from ..models.core import Language

    @receiver(post_save, sender=Language)
    def on_language_saved(sender, instance, created, **kwargs):
        """Language save হলে language list cache clear করে"""
        try:
            cache.delete('languages_list_v1')
            cache.delete(f"language_detail_{instance.code}")
            if not instance.is_active:
                cache.delete(f"translations_api_{instance.code}")
            logger.debug(f"Language cache cleared: {instance.code}")
        except Exception as e:
            logger.error(f"on_language_saved signal failed: {e}")

except ImportError:
    pass
