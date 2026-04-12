# signals/missing_signals.py
"""Missing translation logged signals"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
logger = logging.getLogger(__name__)

try:
    from ..models.translation import MissingTranslation

    @receiver(post_save, sender=MissingTranslation)
    def on_missing_logged(sender, instance, created, **kwargs):
        """New missing translation log হলে notify করে"""
        if created:
            try:
                key = instance.key or 'unknown'
                lang = instance.language.code if instance.language else 'unknown'
                logger.warning(f"MISSING TRANSLATION: key='{key}' language='{lang}'")
                # Could send Slack/email notification here
            except Exception as e:
                logger.error(f"on_missing_logged signal failed: {e}")

except ImportError:
    pass
