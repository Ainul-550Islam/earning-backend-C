# services/translation/TranslationMemoryService.py
"""
TranslationMemoryService — Full fuzzy TM with Levenshtein + Trigram similarity.
Industry standard: exact (100%) + fuzzy (70-99%) + context matches.
"""
import hashlib
import logging
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

# Fuzzy match thresholds
EXACT_SCORE    = 100.0
HIGH_FUZZY     = 85.0   # Strong fuzzy — usually safe to use with minor edits
MEDIUM_FUZZY   = 70.0   # Suggest to translator for review
MIN_FUZZY      = 60.0   # Show as reference only


class TranslationMemoryService:
    """
    Full Translation Memory service with fuzzy matching.
    Supports: exact match, fuzzy (Levenshtein+Trigram), context match, TMX import.
    """

    def add_segment(
        self,
        source_text: str,
        target_text: str,
        source_lang_code: str,
        target_lang_code: str,
        domain: str = '',
        is_approved: bool = False,
        quality_rating: int = None,
        context: str = '',
        client: str = '',
        project: str = '',
    ) -> Optional[object]:
        """New TM segment add করে। Duplicate হলে quality check করে update করে।"""
        try:
            from ..models.translation import TranslationMemory
            from ..models.core import Language
            source_lang = Language.objects.filter(code=source_lang_code).first()
            target_lang = Language.objects.filter(code=target_lang_code).first()
            if not source_lang or not target_lang:
                logger.error(f"Language not found: {source_lang_code} or {target_lang_code}")
                return None

            source_hash = _hash_text(source_text)

            existing = TranslationMemory.objects.filter(
                source_hash=source_hash,
                source_language=source_lang,
                target_language=target_lang,
            ).first()

            if existing:
                # Update if better quality
                should_update = False
                if is_approved and not existing.is_approved:
                    should_update = True
                if quality_rating and (not existing.quality_rating or quality_rating > existing.quality_rating):
                    should_update = True

                if should_update:
                    existing.target_text = target_text
                    existing.is_approved = is_approved or existing.is_approved
                    if quality_rating:
                        existing.quality_rating = quality_rating
                    if domain and not existing.domain:
                        existing.domain = domain
                    existing.save(update_fields=['target_text', 'is_approved', 'quality_rating', 'domain'])
                return existing

            # Create new
            tm = TranslationMemory.objects.create(
                source_language=source_lang,
                target_language=target_lang,
                source_text=source_text,
                target_text=target_text,
                source_hash=source_hash,
                domain=domain,
                is_approved=is_approved,
                quality_rating=quality_rating,
                context=context,
                client=client,
                project=project,
            )
            return tm

        except Exception as e:
            logger.error(f"TM add_segment failed: {e}")
            return None

    def search(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        domain: str = '',
        min_score: float = 70.0,
        max_results: int = 5,
    ) -> List[Dict]:
        """
        Fuzzy TM search — exact match প্রথমে, তারপর fuzzy।
        Returns sorted list by score desc.
        """
        results = []

        # 1. Exact match (100%)
        exact = self._exact_match(source_text, source_lang, target_lang, domain)
        if exact:
            results.append({
                'entry': exact,
                'score': EXACT_SCORE,
                'type': 'exact',
                'source_text': exact.source_text,
                'target_text': exact.target_text,
                'is_approved': exact.is_approved,
                'quality_rating': exact.quality_rating,
                'domain': exact.domain,
            })
            if min_score >= EXACT_SCORE:
                return results

        # 2. Fuzzy match
        if min_score < EXACT_SCORE:
            fuzzy_results = self._fuzzy_search(
                source_text, source_lang, target_lang,
                domain=domain, min_score=min_score,
                max_results=max_results,
            )
            for fr in fuzzy_results:
                if not results or fr['entry'].pk != results[0]['entry'].pk:
                    results.append(fr)

        # Sort by score
        results.sort(key=lambda x: -x['score'])
        return results[:max_results]

    def _exact_match(
        self, source_text: str, source_lang: str, target_lang: str, domain: str = ''
    ) -> Optional[object]:
        """SHA256 hash দিয়ে exact match খোঁজে — O(1)"""
        try:
            from ..models.translation import TranslationMemory
            source_hash = _hash_text(source_text)
            qs = TranslationMemory.objects.filter(
                source_hash=source_hash,
                source_language__code=source_lang,
                target_language__code=target_lang,
            )
            if domain:
                qs = qs.filter(domain__in=[domain, ''])
            result = qs.order_by('-is_approved', '-quality_rating', '-usage_count').first()
            if result:
                result.usage_count += 1
                result.save(update_fields=['usage_count'])
            return result
        except Exception as e:
            logger.error(f"Exact TM match failed: {e}")
            return None

    def _fuzzy_search(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        domain: str = '',
        min_score: float = 70.0,
        max_results: int = 5,
    ) -> List[Dict]:
        """
        Levenshtein + Trigram fuzzy matching.
        Fetches candidate segments (length-filtered) then scores them.
        """
        try:
            from ..models.translation import TranslationMemory
            from ...utils.fuzzy import combined_similarity

            # Length filter — segments that are too different in length won't match well
            src_len = len(source_text)
            min_len = max(1, int(src_len * 0.5))
            max_len = int(src_len * 2.0)

            candidates_qs = TranslationMemory.objects.filter(
                source_language__code=source_lang,
                target_language__code=target_lang,
                source_word_count__gte=max(1, int(src_len / 10)),
                source_word_count__lte=max(1, int(src_len / 4)),
            )
            if domain:
                candidates_qs = candidates_qs.filter(domain__in=[domain, ''])

            # Fetch top candidates by usage (most used TM entries first)
            candidates = list(
                candidates_qs.order_by('-usage_count', '-is_approved')
                .values('id', 'source_text', 'target_text', 'is_approved',
                        'quality_rating', 'domain', 'usage_count')[:200]
            )

            # Score each candidate
            scored = []
            for cand in candidates:
                score = combined_similarity(source_text, cand['source_text'])
                if score >= min_score:
                    scored.append((score, cand))

            scored.sort(key=lambda x: -x[0])

            # Fetch full objects for top results
            results = []
            top_ids = [c['id'] for _, c in scored[:max_results]]
            if top_ids:
                entries = {
                    e.pk: e
                    for e in TranslationMemory.objects.filter(pk__in=top_ids)
                }
                for score, cand in scored[:max_results]:
                    entry = entries.get(cand['id'])
                    if entry:
                        match_type = 'exact' if score >= 99.9 else ('high_fuzzy' if score >= HIGH_FUZZY else 'fuzzy')
                        results.append({
                            'entry': entry,
                            'score': score,
                            'type': match_type,
                            'source_text': entry.source_text,
                            'target_text': entry.target_text,
                            'is_approved': entry.is_approved,
                            'quality_rating': entry.quality_rating,
                            'domain': entry.domain,
                        })

            return results

        except Exception as e:
            logger.error(f"Fuzzy TM search failed: {e}")
            return []

    def import_tmx(self, tmx_content: str, source_lang: str, target_lang: str) -> Dict:
        """TMX (Translation Memory eXchange) format import করে"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(tmx_content)
            imported = 0
            failed = 0
            skipped = 0

            for tu in root.findall('.//tu'):
                try:
                    tuvs = tu.findall('tuv')
                    # Try both with and without xml namespace
                    src_tuv = next(
                        (t for t in tuvs if t.get('{http://www.w3.org/XML/1998/namespace}lang', '').lower().startswith(source_lang.lower())),
                        next((t for t in tuvs if t.get('lang', '').lower().startswith(source_lang.lower())), None)
                    )
                    tgt_tuv = next(
                        (t for t in tuvs if t.get('{http://www.w3.org/XML/1998/namespace}lang', '').lower().startswith(target_lang.lower())),
                        next((t for t in tuvs if t.get('lang', '').lower().startswith(target_lang.lower())), None)
                    )

                    if src_tuv is None or tgt_tuv is None:
                        skipped += 1
                        continue

                    src_seg = src_tuv.find('seg')
                    tgt_seg = tgt_tuv.find('seg')
                    if src_seg is None or tgt_seg is None:
                        skipped += 1
                        continue

                    src_text = (src_seg.text or '').strip()
                    tgt_text = (tgt_seg.text or '').strip()

                    if not src_text or not tgt_text:
                        skipped += 1
                        continue

                    result = self.add_segment(src_text, tgt_text, source_lang, target_lang, is_approved=True)
                    if result:
                        imported += 1
                    else:
                        failed += 1

                except Exception as e:
                    logger.debug(f"TMX tu parse failed: {e}")
                    failed += 1

            return {
                'success': True,
                'imported': imported,
                'failed': failed,
                'skipped': skipped,
                'total': imported + failed + skipped,
            }

        except Exception as e:
            logger.error(f"TMX import failed: {e}")
            return {'success': False, 'error': str(e), 'imported': 0, 'failed': 0}

    def export_tmx(self, source_lang: str, target_lang: str, domain: str = '') -> str:
        """TM entries-গুলো TMX format-এ export করে"""
        try:
            from ..models.translation import TranslationMemory
            qs = TranslationMemory.objects.filter(
                source_language__code=source_lang,
                target_language__code=target_lang,
            )
            if domain:
                qs = qs.filter(domain=domain)

            lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<tmx version="1.4">',
                f'  <header creationtool="World1Localization" srclang="{source_lang}" adminlang="en" datatype="PlainText"/>',
                '  <body>',
            ]

            for tm in qs.order_by('-usage_count')[:10000]:
                src = (tm.source_text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                tgt = (tm.target_text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                lines.extend([
                    '    <tu>',
                    f'      <tuv xml:lang="{source_lang}"><seg>{src}</seg></tuv>',
                    f'      <tuv xml:lang="{target_lang}"><seg>{tgt}</seg></tuv>',
                    '    </tu>',
                ])

            lines.extend(['  </body>', '</tmx>'])
            return '\n'.join(lines)

        except Exception as e:
            logger.error(f"TMX export failed: {e}")
            return ''

    def get_stats(self, source_lang: str, target_lang: str) -> Dict:
        """TM statistics"""
        try:
            from ..models.translation import TranslationMemory
            qs = TranslationMemory.objects.filter(
                source_language__code=source_lang,
                target_language__code=target_lang,
            )
            total = qs.count()
            approved = qs.filter(is_approved=True).count()
            total_usage = sum(qs.values_list('usage_count', flat=True)) or 0
            top_domains = list(
                qs.values_list('domain', flat=True)
                .exclude(domain='')
                .distinct()[:10]
            )
            return {
                'total_segments': total,
                'approved_segments': approved,
                'unapproved_segments': total - approved,
                'total_usage_count': total_usage,
                'top_domains': top_domains,
                'source_lang': source_lang,
                'target_lang': target_lang,
            }
        except Exception as e:
            logger.error(f"TM stats failed: {e}")
            return {'error': str(e)}

    def batch_index_from_translations(
        self, language_code: str, source_lang_code: str = 'en',
        limit: int = 1000
    ) -> Dict:
        """
        Existing Translation records-গুলো TM-তে index করে।
        Run once to populate TM from existing translations.
        """
        try:
            from ..models.core import Language, Translation
            source_lang = Language.objects.filter(code=source_lang_code).first()
            target_lang = Language.objects.filter(code=language_code).first()
            if not source_lang or not target_lang:
                return {'success': False, 'error': 'Language not found'}

            indexed = 0
            failed = 0
            translations = Translation.objects.filter(
                language=target_lang,
                is_approved=True,
            ).select_related('key').order_by('-created_at')[:limit]

            for trans in translations:
                # Get source text from default language
                source_trans = Translation.objects.filter(
                    key=trans.key, language=source_lang
                ).first()
                if source_trans and source_trans.value:
                    result = self.add_segment(
                        source_trans.value, trans.value,
                        source_lang_code, language_code,
                        is_approved=True, quality_rating=4,
                    )
                    if result:
                        indexed += 1
                    else:
                        failed += 1

            return {
                'success': True,
                'indexed': indexed,
                'failed': failed,
                'language': language_code,
            }

        except Exception as e:
            logger.error(f"Batch index failed: {e}")
            return {'success': False, 'error': str(e)}


# ── Module-level helper ───────────────────────────────────────────
def _hash_text(text: str) -> str:
    """Normalized SHA256 hash — same as TranslationMemory.save()"""
    normalized = ' '.join(text.lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


import hashlib  # noqa: E402 — needed for _hash_text
