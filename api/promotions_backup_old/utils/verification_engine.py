# api/promotions/utils/verification_engine.py
import logging
from dataclasses import dataclass
from typing import Optional
logger = logging.getLogger('utils.verification')

@dataclass
class VerificationDecision:
    approved: bool; confidence: float; method: str; issues: list; details: dict

class VerificationEngine:
    """
    Master verification engine — combines all proof checks.
    Routes to appropriate verifier based on task type.
    """
    def verify(self, submission_id: int) -> VerificationDecision:
        try:
            from api.promotions.models import TaskSubmission
            sub      = TaskSubmission.objects.select_related('campaign','campaign__platform').get(pk=submission_id)
            platform = sub.campaign.platform.name.lower() if sub.campaign.platform else ''
            task_type = getattr(sub, 'task_type', '')

            # Text tasks
            if task_type in ('survey', 'review', 'comment', 'translate'):
                return self._verify_text(sub)
            # Screenshot tasks
            return self._verify_screenshot(sub, platform)
        except Exception as e:
            logger.error(f'Verification failed: {e}')
            return VerificationDecision(False, 0.0, 'error', [str(e)], {})

    def _verify_screenshot(self, sub, platform: str) -> VerificationDecision:
        from api.promotions.utils.screenshot_validator import ScreenshotValidator
        keywords = getattr(sub.campaign, 'required_keywords', []) or []
        try:
            proof_bytes = self._get_proof_bytes(sub)
            result = ScreenshotValidator().validate(proof_bytes, platform, keywords, sub.campaign.target_url or '')
            return VerificationDecision(result.valid, result.confidence, 'screenshot', result.issues, {'platform': result.platform})
        except Exception as e:
            return VerificationDecision(False, 0.0, 'screenshot_error', [str(e)], {})

    def _verify_text(self, sub) -> VerificationDecision:
        from api.promotions.ai.nlp_analyzer import NLPAnalyzer
        text = getattr(sub, 'text_proof', '') or ''
        if not text: return VerificationDecision(False, 0.0, 'text', ['no_text'], {})
        result = NLPAnalyzer().analyze(text)
        approved = result.quality_score >= 0.5 and not result.is_spam
        return VerificationDecision(approved, result.quality_score, 'nlp', result.issues if hasattr(result,'issues') else [], {})

    def _get_proof_bytes(self, sub) -> bytes:
        try:
            import requests
            url = getattr(sub, 'proof_screenshot_url', None)
            if url: return requests.get(url, timeout=10).content
        except Exception: pass
        return b''
