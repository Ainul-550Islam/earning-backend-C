# services/translation/SourceChangeDetector.py
"""
Source text change detection — marks translations as needing re-translation
when source (English) text changes significantly.
"""
import hashlib
import logging
from typing import List, Dict
from django.utils import timezone
logger = logging.getLogger(__name__)


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


class SourceChangeDetector:
    """
    Source text পরিবর্তন হলে সব translations-কে 'needs_review' mark করে।
    Used in TranslationKey pre_save signal।
    """

    def detect_and_mark(self, translation_key_id: int, old_source: str, new_source: str) -> Dict:
        """Source text changed হলে dependent translations mark করে।"""
        if not old_source or not new_source:
            return {'changed': False}
        if _hash(old_source) == _hash(new_source):
            return {'changed': False}

        # Calculate similarity to determine severity
        from ..utils.fuzzy import levenshtein_similarity
        similarity = levenshtein_similarity(old_source, new_source)
        severity = 'minor' if similarity >= 80 else ('moderate' if similarity >= 50 else 'major')

        try:
            from ..models.core import Translation
            qs = Translation.objects.filter(
                key_id=translation_key_id,
                is_approved=True,
            ).exclude(language__is_default=True)

            marked = qs.update(
                is_approved=False,
                needs_review=True,
                review_note=f"Source changed ({severity}: {similarity:.0f}% similar). Re-translation needed.",
                source_changed_at=timezone.now(),
            )
            logger.info(f"Source change detected for key {translation_key_id}: {marked} translations marked")
            return {
                'changed': True,
                'severity': severity,
                'similarity': similarity,
                'marked_count': marked,
            }
        except Exception as e:
            logger.error(f"SourceChangeDetector.detect_and_mark failed: {e}")
            return {'changed': True, 'error': str(e)}

    def get_needs_review(self, language_code: str = None) -> List[Dict]:
        """Review দরকার এমন translations list করে।"""
        try:
            from ..models.core import Translation
            qs = Translation.objects.filter(needs_review=True)
            if language_code:
                qs = qs.filter(language__code=language_code)
            return list(qs.select_related('key', 'language').values(
                'id', 'key__key', 'language__code', 'value',
                'review_note', 'source_changed_at',
            )[:100])
        except Exception as e:
            logger.error(f"get_needs_review failed: {e}")
            return []

    def bulk_detect(self, limit: int = 500) -> Dict:
        """Existing translations-এর source hash mismatch বের করে।"""
        try:
            from ..models.core import Translation, Language
            default_lang = Language.objects.filter(is_default=True).first()
            if not default_lang:
                return {'error': 'No default language found'}

            source_translations = {
                t.key_id: t.value
                for t in Translation.objects.filter(language=default_lang).only('key_id', 'value')
            }

            stale = 0
            for trans in Translation.objects.filter(
                is_approved=True,
            ).exclude(language=default_lang).select_related('key')[:limit]:
                source_text = source_translations.get(trans.key_id, '')
                if source_text and trans.source_hash_at_translation:
                    current_hash = _hash(source_text)
                    if current_hash != trans.source_hash_at_translation:
                        trans.needs_review = True
                        trans.save(update_fields=['needs_review'])
                        stale += 1

            return {'scanned': limit, 'stale': stale}
        except Exception as e:
            logger.error(f"bulk_detect failed: {e}")
            return {'error': str(e)}


class SegmentLockService:
    """
    Approved translations-কে lock করে — accidental overwrite prevent করে।
    Only admin/reviewer can unlock.
    """

    def lock(self, translation_id: int, locked_by_user) -> Dict:
        """Translation segment lock করে।"""
        try:
            from ..models.core import Translation
            trans = Translation.objects.get(pk=translation_id)
            if not trans.is_approved:
                return {'success': False, 'error': 'Only approved translations can be locked'}
            trans.is_locked = True
            trans.locked_by = locked_by_user
            trans.locked_at = timezone.now()
            trans.save(update_fields=['is_locked', 'locked_by', 'locked_at'])
            return {'success': True, 'locked': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def unlock(self, translation_id: int, unlocked_by_user) -> Dict:
        """Translation segment unlock করে।"""
        try:
            from ..models.core import Translation
            trans = Translation.objects.get(pk=translation_id)
            trans.is_locked = False
            trans.locked_by = None
            trans.locked_at = None
            trans.save(update_fields=['is_locked', 'locked_by', 'locked_at'])
            return {'success': True, 'locked': False}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def bulk_lock_approved(self, language_code: str) -> Dict:
        """Language-এর সব approved translations lock করে।"""
        try:
            from ..models.core import Translation
            count = Translation.objects.filter(
                language__code=language_code, is_approved=True, is_locked=False
            ).update(is_locked=True)
            return {'success': True, 'locked': count}
        except Exception as e:
            return {'success': False, 'error': str(e)}
