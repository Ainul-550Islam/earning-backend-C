# services/translation/TranslatorWorkflowService.py
"""
Translation workflow management — assignment, review, approval pipeline.
Comparable to Phrase/Lokalise project workflow.
"""
import logging
from typing import Optional, Dict, List
from django.utils import timezone
logger = logging.getLogger(__name__)


class TranslatorWorkflowService:
    """
    Human translation workflow:
    draft → assigned → translated → review → approved/rejected
    """

    def assign_translator(self, key_ids: List[int], language_code: str, translator_user) -> Dict:
        """Translation keys translator-এ assign করে।"""
        try:
            from ..models.core import TranslationKey, Language
            from ..models.content import TranslationRequest
            lang = Language.objects.filter(code=language_code, is_active=True).first()
            if not lang:
                return {'success': False, 'error': f'Language {language_code} not found'}

            created = 0
            for key_id in key_ids:
                key = TranslationKey.objects.filter(pk=key_id).first()
                if not key:
                    continue
                req, was_created = TranslationRequest.objects.get_or_create(
                    source_language=lang,
                    defaults={
                        'title': f'Translate {key.key} to {language_code}',
                        'requested_by': translator_user,
                        'assigned_to': translator_user,
                        'status': 'assigned',
                        'priority': key.priority or 'normal',
                    }
                )
                if was_created:
                    created += 1

            return {'success': True, 'assigned': created, 'language': language_code}
        except Exception as e:
            logger.error(f"assign_translator failed: {e}")
            return {'success': False, 'error': str(e)}

    def submit_translation(
        self, key: str, language_code: str, value: str,
        translator_user, comment: str = ''
    ) -> Dict:
        """Translator-এর translation submit করে — 'translated' status-এ যায়।"""
        try:
            from ..models.core import Translation, TranslationKey, Language
            trans_key = TranslationKey.objects.filter(key=key).first()
            language = Language.objects.filter(code=language_code, is_active=True).first()
            if not trans_key or not language:
                return {'success': False, 'error': 'Key or language not found'}

            # Check not locked by someone else
            existing = Translation.objects.filter(key=trans_key, language=language).first()
            if existing and getattr(existing, 'is_locked', False):
                return {'success': False, 'error': 'Translation is locked. Contact a reviewer to unlock.'}

            trans, created = Translation.objects.update_or_create(
                key=trans_key,
                language=language,
                defaults={
                    'value': value,
                    'is_approved': False,
                    'source': 'manual',
                    'translator': translator_user,
                    'translated_at': timezone.now(),
                    'translator_comment': comment,
                    'needs_review': True,
                }
            )

            # MTQE quality estimate
            try:
                default_lang = Language.objects.filter(is_default=True).first()
                if default_lang:
                    source_trans = Translation.objects.filter(
                        key=trans_key, language=default_lang
                    ).first()
                    if source_trans:
                        from .MTQEService import MTQEService
                        quality = MTQEService().estimate(
                            source_trans.value, value,
                            default_lang.code, language_code
                        )
                        trans.quality_score_numeric = quality['score']
                        trans.save(update_fields=['quality_score_numeric'])
            except Exception:
                pass

            return {
                'success': True,
                'translation_id': trans.pk,
                'key': key,
                'language': language_code,
                'created': created,
                'status': 'pending_review',
            }
        except Exception as e:
            logger.error(f"submit_translation failed: {e}")
            return {'success': False, 'error': str(e)}

    def review_translation(
        self, translation_id: int, decision: str,
        reviewer_user, comment: str = ''
    ) -> Dict:
        """
        Reviewer translation approve/reject করে।
        decision: 'approve' | 'reject'
        """
        try:
            from ..models.core import Translation
            trans = Translation.objects.filter(pk=translation_id).first()
            if not trans:
                return {'success': False, 'error': 'Translation not found'}

            if decision == 'approve':
                trans.is_approved = True
                trans.needs_review = False
                trans.approved_by = reviewer_user
                trans.approved_at = timezone.now()
                trans.review_note = comment or 'Approved'
                trans.save(update_fields=['is_approved', 'needs_review', 'approved_by', 'approved_at', 'review_note'])
                action = 'approved'

            elif decision == 'reject':
                trans.is_approved = False
                trans.needs_review = True
                trans.review_note = comment or 'Rejected — please revise'
                trans.save(update_fields=['is_approved', 'needs_review', 'review_note'])
                action = 'rejected'
            else:
                return {'success': False, 'error': 'Decision must be approve or reject'}

            return {
                'success': True,
                'translation_id': translation_id,
                'action': action,
                'reviewer': getattr(reviewer_user, 'email', str(reviewer_user)),
            }
        except Exception as e:
            logger.error(f"review_translation failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_pending_reviews(self, language_code: str = None, reviewer=None) -> List[Dict]:
        """Review দরকার এমন translations list করে।"""
        try:
            from ..models.core import Translation
            qs = Translation.objects.filter(needs_review=True, is_approved=False)
            if language_code:
                qs = qs.filter(language__code=language_code)
            return list(qs.select_related('key', 'language').values(
                'id', 'key__key', 'key__category', 'language__code',
                'value', 'review_note', 'quality_score_numeric',
                'translator_comment', 'translated_at',
            ).order_by('-translated_at')[:100])
        except Exception as e:
            logger.error(f"get_pending_reviews failed: {e}")
            return []

    def bulk_approve(self, language_code: str, min_quality_score: float = 85.0, reviewer=None) -> Dict:
        """High quality scores-এর translations auto-approve করে।"""
        try:
            from ..models.core import Translation
            qs = Translation.objects.filter(
                language__code=language_code,
                is_approved=False,
                needs_review=True,
                quality_score_numeric__gte=min_quality_score,
            )
            count = qs.update(
                is_approved=True,
                needs_review=False,
                approved_at=timezone.now(),
                review_note=f'Auto-approved (quality score >= {min_quality_score})',
            )
            return {'success': True, 'approved': count, 'language': language_code}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_workflow_stats(self, language_code: str) -> Dict:
        """Language-এর workflow statistics।"""
        try:
            from ..models.core import Translation, Language
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return {'error': 'Language not found'}
            qs = Translation.objects.filter(language=lang)
            total = qs.count()
            approved = qs.filter(is_approved=True).count()
            needs_review = qs.filter(needs_review=True).count()
            locked = qs.filter(is_locked=True).count()
            return {
                'language': language_code,
                'total': total,
                'approved': approved,
                'needs_review': needs_review,
                'locked': locked,
                'pending': total - approved - needs_review,
                'approval_rate': round(approved / total * 100, 1) if total else 0,
            }
        except Exception as e:
            return {'error': str(e)}
