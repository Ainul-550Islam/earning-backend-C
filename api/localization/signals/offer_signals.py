# signals/offer_signals.py
"""CPAlead offer auto-translation signals"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
logger = logging.getLogger(__name__)


def connect_offer_signals():
    """
    Offer signals connect করে।
    Call this from apps.py ready() after CPAlead app is loaded.
    """
    try:
        from cpalead.models import Offer  # adjust to your actual model path

        @receiver(post_save, sender=Offer)
        def auto_translate_offer(sender, instance, created, **kwargs):
            """Offer save হলে all active languages-এ auto-translate করে"""
            if not getattr(instance, 'auto_translate', True):
                return
            try:
                from .models.core import Language
                from .services.translation.TranslationEngine import TranslationEngine
                from .models.content import LocalizedContent
                engine = TranslationEngine()
                fields_to_translate = ['title', 'description', 'requirements', 'short_description']
                languages = Language.objects.filter(is_active=True, is_default=False)

                for lang in languages:
                    for field in fields_to_translate:
                        source_text = getattr(instance, field, '') or ''
                        if not source_text.strip():
                            continue
                        # Check if translation already exists and is approved
                        existing = LocalizedContent.objects.filter(
                            content_type='offer',
                            object_id=str(instance.pk),
                            language=lang,
                            field_name=field,
                            is_approved=True,
                        ).first()
                        if existing and not created:
                            continue  # Don't overwrite approved translations on update

                        result = engine.translate(
                            source_text, 'en', lang.code,
                            domain='offer', use_memory=True,
                        )
                        if result.get('translated'):
                            LocalizedContent.objects.update_or_create(
                                content_type='offer',
                                object_id=str(instance.pk),
                                language=lang,
                                field_name=field,
                                defaults={
                                    'value': result['translated'],
                                    'is_machine_translated': result.get('provider') != 'translation_memory',
                                    'is_approved': False,  # Requires human review
                                    'review_status': 'pending',
                                }
                            )
                logger.info(f"Auto-translated offer #{instance.pk} to {languages.count()} languages")
            except Exception as e:
                logger.error(f"auto_translate_offer failed for offer #{getattr(instance,'pk','?')}: {e}")

        logger.info("Offer auto-translation signals connected")

    except ImportError:
        logger.debug("CPAlead Offer model not found — offer signals not connected (expected if cpalead app not installed)")
    except Exception as e:
        logger.error(f"connect_offer_signals failed: {e}")
