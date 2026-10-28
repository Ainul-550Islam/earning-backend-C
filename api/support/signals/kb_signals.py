# api/support/signals/kb_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.KBSearch')
def on_kb_search(sender, instance, created, **kwargs):
    """Log KB search for analytics."""
    if created:
        logger.debug(f"KB search: '{instance.query}' → {instance.results_count} results")

@receiver(post_save, sender='support.KBFeedback')
def on_kb_feedback(sender, instance, created, **kwargs):
    """Update article helpful counters."""
    if created:
        try:
            article = instance.article
            if instance.is_helpful:
                article.helpful_yes += 1
            else:
                article.helpful_no += 1
            article.save(update_fields=["helpful_yes","helpful_no"])
        except Exception as e:
            logger.error(f"KB feedback counter update failed: {e}")