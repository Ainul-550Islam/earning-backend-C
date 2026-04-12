# signals/preference_signals.py
"""User language preference change signals"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)

try:
    from ..models.core import UserLanguagePreference

    @receiver(post_save, sender=UserLanguagePreference)
    def on_preference_saved(sender, instance, created, **kwargs):
        """User preference update হলে cache clear করে"""
        try:
            user_id = instance.user_id if instance.user_id else None
            if user_id:
                cache.delete(f"user_pref_{user_id}")
                logger.debug(f"User preference cache cleared for user_id: {user_id}")
        except Exception as e:
            logger.error(f"on_preference_saved signal failed: {e}")

except ImportError:
    pass
