# services/translation/TranslationEngine.py
"""
TranslationEngine — Main translation facade.
ProviderRouter + TranslationMemory + Glossary + QA pipeline.
"""
import re
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class TranslationEngine:
    """
    Main translation engine — orchestrates all translation services.
    Flow: TM lookup → Glossary check → Provider translate → Glossary enforce → QA
    """

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        domain: str = '',
        use_memory: bool = True,
        enforce_glossary: bool = True,
        run_qa: bool = False,
        context: str = '',
    ) -> Dict:
        """
        Single text translate করে — full pipeline।
        """
        if not text or not text.strip():
            return {'translated': text, 'source': 'empty', 'provider': 'none'}

        # Step 1: Translation Memory lookup
        if use_memory:
            tm_result = self._check_tm(text, source_lang, target_lang, domain)
            if tm_result:
                translated = tm_result.target_text
                # Apply glossary even on TM results
                if enforce_glossary:
                    translated = self._apply_glossary(text, translated, target_lang, domain)
                return {
                    'translated': translated,
                    'source': 'memory',
                    'score': 100,
                    'provider': 'translation_memory',
                    'tm_id': tm_result.pk,
                }

        # Step 2: Glossary — Do Not Translate terms
        dnt_terms = self._get_dnt_terms(source_lang, domain)
        protected_text, placeholders = self._protect_dnt_terms(text, dnt_terms)

        # Step 3: Provider translation
        router_result = self._call_provider(protected_text, source_lang, target_lang)
        translated_raw = router_result.get('translated', text)

        # Step 4: Restore DNT terms + apply glossary preferred translations
        translated = self._restore_dnt_terms(translated_raw, placeholders)
        if enforce_glossary:
            translated = self._apply_glossary(text, translated, target_lang, domain)

        # Step 5: QA check (optional)
        qa_result = None
        if run_qa:
            try:
                from .TranslationQAService import TranslationQAService
                qa_result = TranslationQAService().check_all(text, translated, source_lang, target_lang)
            except Exception as e:
                logger.error(f"QA check failed: {e}")

        # Step 6: Save to Translation Memory
        if translated and translated != text:
            self._save_to_tm(text, translated, source_lang, target_lang, domain)

        result = {
            'translated': translated,
            'source': 'provider',
            'provider': router_result.get('provider', 'unknown'),
            'source_lang': source_lang,
            'target_lang': target_lang,
            'domain': domain,
        }
        if qa_result:
            result['qa'] = qa_result

        return result

    def bulk_translate(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        domain: str = '',
    ) -> List[Dict]:
        """Multiple texts translate করে — TM hits batched first"""
        tm_results = {}
        missing_indices = []

        # Check TM for all texts first
        for i, text in enumerate(texts):
            tm = self._check_tm(text, source_lang, target_lang, domain)
            if tm:
                tm_results[i] = {
                    'translated': tm.target_text,
                    'source': 'memory',
                    'provider': 'translation_memory',
                }
            else:
                missing_indices.append(i)

        # Translate missing ones via provider
        if missing_indices:
            try:
                from .ProviderRouter import ProviderRouter
                router = ProviderRouter()
                missing_texts = [texts[i] for i in missing_indices]
                provider_results = router.bulk_translate(missing_texts, source_lang, target_lang)
                for idx, result in zip(missing_indices, provider_results):
                    # Apply glossary
                    if result.get('translated'):
                        result['translated'] = self._apply_glossary(
                            texts[idx], result['translated'], target_lang, domain
                        )
                    tm_results[idx] = result
            except Exception as e:
                logger.error(f"Bulk provider call failed: {e}")
                for idx in missing_indices:
                    tm_results[idx] = {'translated': texts[idx], 'source': 'error'}

        return [tm_results.get(i, {'translated': texts[i], 'source': 'error'}) for i in range(len(texts))]

    # ── Private helpers ──────────────────────────────────────────

    def _check_tm(self, text: str, source_lang: str, target_lang: str, domain: str = ''):
        """Translation Memory-তে exact match খোঁজে"""
        try:
            from ..models.translation import TranslationMemory
            return TranslationMemory.find_exact_match(text, source_lang, target_lang, domain)
        except Exception as e:
            logger.debug(f"TM check failed: {e}")
            return None

    def _call_provider(self, text: str, source_lang: str, target_lang: str) -> Dict:
        """ProviderRouter দিয়ে translate করে"""
        try:
            from .ProviderRouter import ProviderRouter
            return ProviderRouter().translate(text, source_lang, target_lang)
        except Exception as e:
            logger.error(f"Provider call failed: {e}")
            return {'translated': text, 'provider': 'error', 'error': str(e)}

    def _get_dnt_terms(self, source_lang: str, domain: str = '') -> List[str]:
        """Glossary থেকে Do Not Translate terms পাওয়া"""
        try:
            from ..models.translation import TranslationGlossary
            qs = TranslationGlossary.objects.filter(
                source_language__code=source_lang,
                is_do_not_translate=True
            )
            if domain:
                qs = qs.filter(domain__in=[domain, ''])
            return list(qs.values_list('source_term', flat=True)[:100])
        except Exception as e:
            logger.debug(f"DNT terms fetch failed: {e}")
            return []

    def _protect_dnt_terms(self, text: str, dnt_terms: List[str]):
        """
        DNT terms-কে placeholder দিয়ে replace করে translation-এর আগে।
        যেমন: "CPAlead offers" → "DNTPLACEHOLDER_0 offers"
        """
        placeholders = {}
        protected = text

        for i, term in enumerate(dnt_terms):
            placeholder = f"DNTPH{i}X"
            # Case-insensitive replacement with word boundary
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            if pattern.search(protected):
                placeholders[placeholder] = term
                protected = pattern.sub(placeholder, protected)

        return protected, placeholders

    def _restore_dnt_terms(self, translated: str, placeholders: Dict[str, str]) -> str:
        """Placeholder-গুলো original DNT terms দিয়ে restore করে"""
        result = translated
        for placeholder, original_term in placeholders.items():
            result = result.replace(placeholder, original_term)
        return result

    def _apply_glossary(
        self, source_text: str, translated_text: str,
        target_lang: str, domain: str = ''
    ) -> str:
        """
        Glossary preferred translations enforce করে।
        যেমন: "earn" → "আয়" (preferred), not "উপার্জন"
        Real regex replacement with word boundaries.
        """
        try:
            from ..models.translation import TranslationGlossary, TranslationGlossaryEntry
            # Get entries for target language
            entries = TranslationGlossaryEntry.objects.filter(
                language__code=target_lang,
                glossary__source_language__code__isnull=False,
                glossary__is_forbidden=False,
                is_approved=True,
            ).select_related('glossary').values(
                'glossary__source_term', 'translated_term', 'forbidden_terms'
            )[:200]

            result = translated_text
            for entry in entries:
                source_term = entry['glossary__source_term']
                preferred = entry['translated_term']

                if not source_term or not preferred:
                    continue

                # Check if source term appears in original source text (context check)
                if not re.search(r'\b' + re.escape(source_term) + r'\b', source_text, re.IGNORECASE):
                    continue

                # Replace any forbidden alternatives in translation
                forbidden = entry.get('forbidden_terms') or []
                if isinstance(forbidden, list):
                    for forbidden_term in forbidden:
                        if forbidden_term and forbidden_term in result:
                            result = re.sub(
                                r'\b' + re.escape(forbidden_term) + r'\b',
                                preferred,
                                result
                            )

            return result

        except Exception as e:
            logger.debug(f"Glossary apply failed: {e}")
            return translated_text

    def _save_to_tm(
        self, source_text: str, translated_text: str,
        source_lang: str, target_lang: str, domain: str = ''
    ):
        """Successful translation TM-এ save করে"""
        try:
            from .TranslationMemoryService import TranslationMemoryService
            TranslationMemoryService().add_segment(
                source_text, translated_text,
                source_lang, target_lang,
                domain=domain,
                is_approved=False,
                quality_rating=3,
            )
        except Exception as e:
            logger.debug(f"TM save failed: {e}")
