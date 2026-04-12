# services/translation/TranslationGlossaryService.py
"""Glossary management service"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TranslationGlossaryService:
    """Glossary terms manage করার service"""

    def add_term(self, source_term: str, source_lang_code: str,
                 translations: Dict[str, str] = None,
                 domain: str = '', is_do_not_translate: bool = False,
                 is_brand_term: bool = False) -> Optional[object]:
        """Glossary term add করে"""
        try:
            from ..models.translation import TranslationGlossary, TranslationGlossaryEntry
            from ..models.core import Language
            source_lang = Language.objects.filter(code=source_lang_code).first()
            if not source_lang:
                return None
            term, _ = TranslationGlossary.objects.get_or_create(
                source_term=source_term,
                source_language=source_lang,
                defaults={
                    'domain': domain,
                    'is_do_not_translate': is_do_not_translate,
                    'is_brand_term': is_brand_term,
                }
            )
            if translations:
                for lang_code, translated_term in translations.items():
                    lang = Language.objects.filter(code=lang_code).first()
                    if lang:
                        TranslationGlossaryEntry.objects.update_or_create(
                            glossary=term, language=lang,
                            defaults={'translated_term': translated_term}
                        )
            return term
        except Exception as e:
            logger.error(f"Add glossary term failed: {e}")
            return None

    def get_for_language(self, source_lang_code: str, target_lang_code: str,
                         domain: str = '') -> List[Dict]:
        """নির্দিষ্ট language pair-এর জন্য glossary তুলে দেয়"""
        try:
            from ..models.translation import TranslationGlossary, TranslationGlossaryEntry
            qs = TranslationGlossary.objects.filter(source_language__code=source_lang_code)
            if domain:
                qs = qs.filter(domain=domain)
            result = []
            for term in qs:
                entry = TranslationGlossaryEntry.objects.filter(
                    glossary=term, language__code=target_lang_code
                ).first()
                result.append({
                    'source': term.source_term,
                    'target': entry.translated_term if entry else None,
                    'do_not_translate': term.is_do_not_translate,
                    'is_brand': term.is_brand_term,
                    'domain': term.domain,
                })
            return result
        except Exception as e:
            logger.error(f"Get glossary failed: {e}")
            return []
