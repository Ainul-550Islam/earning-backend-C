# services/translation/AutoTranslationService.py
"""Auto-translate missing keys via provider pipeline"""
import logging
from typing import Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class AutoTranslationService:
    """
    Missing translations auto-translate করে।
    Source language (default: en) থেকে target language-এ।
    Dry run mode: কতটা হবে দেখায়, actually করে না।
    """

    def translate_missing(
        self,
        language_code: str,
        source_language_code: str = 'en',
        limit: int = 100,
        dry_run: bool = False,
        namespace: str = '',
        provider: str = 'auto',
    ) -> Dict:
        """
        Target language-এর missing translations auto-translate করে।
        """
        try:
            from ...models.core import Language, Translation, TranslationKey

            target_lang = Language.objects.filter(code=language_code, is_active=True).first()
            if not target_lang:
                return {'success': False, 'error': f'Language {language_code} not found or inactive',
                        'language': language_code, 'total_missing': 0, 'translated': 0,
                        'failed': 0, 'dry_run': dry_run}

            source_lang = Language.objects.filter(code=source_language_code, is_active=True).first()
            if not source_lang:
                return {'success': False, 'error': f'Source language {source_language_code} not found',
                        'language': language_code, 'total_missing': 0, 'translated': 0,
                        'failed': 0, 'dry_run': dry_run}

            # Find keys that have source translation but NOT target translation
            translated_key_ids = Translation.objects.filter(
                language=target_lang
            ).exclude(value='').values_list('key_id', flat=True)

            source_translations = Translation.objects.filter(
                language=source_lang
            ).exclude(value='').select_related('key')

            if namespace:
                source_translations = source_translations.filter(key__category=namespace)

            missing_source = source_translations.exclude(key_id__in=translated_key_ids)
            total_missing = missing_source.count()

            if dry_run:
                preview = list(missing_source.values('key__key', 'value')[:10])
                return {
                    'success': True,
                    'language': language_code,
                    'source_language': source_language_code,
                    'total_missing': total_missing,
                    'translated': 0,
                    'failed': 0,
                    'dry_run': True,
                    'limit': limit,
                    'preview': preview,
                }

            # Actually translate
            from .TranslationEngine import TranslationEngine
            engine = TranslationEngine()

            translated = 0
            failed = 0
            errors = []

            batch = list(missing_source[:limit])
            for source_trans in batch:
                try:
                    result = engine.translate(
                        source_trans.value,
                        source_language_code,
                        language_code,
                        domain=source_trans.key.category or '',
                        use_memory=True,
                    )
                    translated_text = result.get('translated', '')
                    if translated_text and translated_text != source_trans.value:
                        Translation.objects.create(
                            key=source_trans.key,
                            language=target_lang,
                            value=translated_text,
                            source='auto',
                            is_approved=False,
                            word_count=len(translated_text.split()),
                            character_count=len(translated_text),
                        )
                        translated += 1
                    else:
                        failed += 1

                except Exception as e:
                    failed += 1
                    errors.append(f"{source_trans.key.key}: {str(e)[:50]}")

            logger.info(f"Auto-translate {language_code}: {translated} done, {failed} failed / {total_missing} missing")

            return {
                'success': True,
                'language': language_code,
                'source_language': source_language_code,
                'total_missing': total_missing,
                'translated': translated,
                'failed': failed,
                'dry_run': False,
                'limit': limit,
                'errors': errors[:5],
            }

        except Exception as e:
            logger.error(f"AutoTranslation failed for {language_code}: {e}")
            return {
                'success': False, 'error': str(e),
                'language': language_code, 'total_missing': 0,
                'translated': 0, 'failed': 0, 'dry_run': dry_run,
            }

    def translate_key(
        self, key: str, target_lang: str, source_lang: str = 'en', domain: str = ''
    ) -> Dict:
        """Single key translate করে"""
        try:
            from ...models.core import Translation, TranslationKey, Language
            tkey = TranslationKey.objects.filter(key=key).first()
            if not tkey:
                return {'success': False, 'error': f'Key {key} not found'}
            src_lang_obj = Language.objects.filter(code=source_lang).first()
            src_trans = Translation.objects.filter(key=tkey, language=src_lang_obj).first()
            if not src_trans:
                return {'success': False, 'error': f'No source translation for {key}'}
            from .TranslationEngine import TranslationEngine
            result = TranslationEngine().translate(src_trans.value, source_lang, target_lang, domain=domain)
            return {'success': True, 'key': key, 'translated': result.get('translated', '')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
