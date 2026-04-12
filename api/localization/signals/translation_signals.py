# signals/translation_signals.py
"""Translation save/approve/reject signals"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)

try:
    from ..models.core import Translation

    @receiver(post_save, sender=Translation)
    def on_translation_saved(sender, instance, created, **kwargs):
        """Translation save হলে cache invalidate করে"""
        try:
            lang_code = instance.language.code if instance.language else ''
            if lang_code:
                cache.delete(f"translations_api_{lang_code}")
                cache.delete(f"translation_coverage_{lang_code}")
                logger.debug(f"Cache invalidated for language: {lang_code}")
        except Exception as e:
            logger.error(f"on_translation_saved signal failed: {e}")

    @receiver(post_delete, sender=Translation)
    def on_translation_deleted(sender, instance, **kwargs):
        """Translation delete হলে cache invalidate করে"""
        try:
            lang_code = instance.language.code if instance.language else ''
            if lang_code:
                cache.delete(f"translations_api_{lang_code}")
        except Exception as e:
            logger.error(f"on_translation_deleted signal failed: {e}")

except ImportError:
    pass


# TranslationVersion tracking — every edit creates a version
try:
    from ..models.core import Translation
    from ..models.translation import TranslationVersion

    @receiver(pre_save, sender=Translation)
    def create_translation_version(sender, instance, **kwargs):
        """Translation save হলে version history তৈরি করে"""
        if not instance.pk:
            return  # New instance — no previous version to track
        try:
            old = Translation.objects.filter(pk=instance.pk).first()
            if old and old.value != instance.value:
                last_version = TranslationVersion.objects.filter(
                    translation=old
                ).order_by('-version_number').first()
                next_version = (last_version.version_number + 1) if last_version else 1
                TranslationVersion.objects.create(
                    translation=old,
                    version_number=next_version,
                    value=old.value,
                    value_plural=old.value_plural or '',
                    source='manual',
                )
        except Exception as e:
            logger.error(f"create_translation_version signal failed: {e}")

except ImportError:
    pass
