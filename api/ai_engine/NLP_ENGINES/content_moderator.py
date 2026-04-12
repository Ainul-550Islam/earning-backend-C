"""
api/ai_engine/NLP_ENGINES/content_moderator.py
===============================================
Content Moderator — text + image combined moderation।
"""

import logging

logger = logging.getLogger(__name__)


class ContentModerator:
    """
    Multi-modal content moderation।
    Text + Image signals combine করো।
    """

    def moderate_text(self, text: str, user=None, tenant_id=None) -> dict:
        from .spam_detector import SpamDetector
        from .profanity_filter import ProfanityFilter
        from .sentiment_analyzer import SentimentAnalyzer

        spam   = SpamDetector().detect(text)
        prof   = ProfanityFilter().check(text)
        sentiment = SentimentAnalyzer().analyze(text)

        is_flagged = spam['is_spam'] or prof['has_profanity']
        violation_score = max(spam['spam_confidence'], 0.9 if prof['has_profanity'] else 0.0)

        violation_type = 'other'
        if prof['has_profanity']:
            violation_type = 'profanity'
        elif spam['is_spam']:
            violation_type = 'spam'

        action = 'allow'
        if violation_score >= 0.9:
            action = 'remove'
        elif violation_score >= 0.6:
            action = 'review_needed'
        elif violation_score >= 0.4:
            action = 'warn'

        result = {
            'is_flagged':       is_flagged,
            'violation_type':   violation_type,
            'violation_score':  round(violation_score, 4),
            'action_taken':     action,
            'signals': {
                'spam':      spam,
                'profanity': prof,
                'sentiment': sentiment,
            },
        }

        # DB Log করো
        if is_flagged:
            self._log(result, text, user, tenant_id)

        return result

    def _log(self, result: dict, text: str, user, tenant_id):
        try:
            from ..models import ContentModerationLog
            ContentModerationLog.objects.create(
                content_type='text',
                content_preview=text[:200],
                violation_type=result['violation_type'],
                violation_score=result['violation_score'],
                action_taken=result['action_taken'],
                is_auto_action=True,
                user=user,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(f"Moderation log error: {e}")
