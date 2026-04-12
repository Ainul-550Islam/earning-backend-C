# api/promotions/ai/fraud_score.py
# AI-Powered Fraud Scoring — Submission level real-time fraud detection
# OCR + Image + Behavior সব মিলিয়ে final fraud score দেয়
# =============================================================================

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('ai.fraud_score')

CACHE_PREFIX_FRAUD = 'ai:fraud:{}'
CACHE_TTL_FRAUD    = 3600


@dataclass
class AIFraudScore:
    submission_id:    int
    overall_score:    float          # 0.0 = clean, 1.0 = definite fraud
    risk_level:       str            # low, medium, high, critical
    component_scores: dict           # {'ocr': 0.1, 'image': 0.3, 'behavior': 0.5}
    fraud_types:      list
    evidence:         dict           = field(default_factory=dict)
    action:           str            = 'allow'  # allow, flag, reject, ban
    confidence:       float          = 0.0
    explanation:      str            = ''


class AIFraudScorer:
    """
    Multi-modal AI fraud scoring।
    OCR, Image Analysis, Behavioral Analysis একসাথে মিলিয়ে scoring করে।

    Score Components:
    - Image authenticity (40%)
    - OCR keyword verification (30%)
    - Behavioral signals (30%)
    """

    WEIGHTS = {
        'image':    0.40,
        'ocr':      0.30,
        'behavior': 0.30,
    }

    def score_submission(
        self,
        submission_id:  int,
        image_url:      str = None,
        expected_platform: str = None,
        required_keywords: list = None,
        user_id:        int = None,
        ip_address:     str = None,
    ) -> AIFraudScore:
        """
        Submission এর comprehensive fraud score বের করে।
        """
        cache_key = CACHE_PREFIX_FRAUD.format(submission_id)
        cached    = cache.get(cache_key)
        if cached:
            return AIFraudScore(**cached)

        components  = {}
        fraud_types = []
        evidence    = {}

        # ── 1. Image Analysis ──────────────────────────────────────────────
        if image_url:
            img_score, img_fraud, img_evidence = self._score_image(
                image_url, expected_platform
            )
            components['image'] = img_score
            fraud_types.extend(img_fraud)
            evidence['image'] = img_evidence
        else:
            components['image'] = 0.3   # No image = slight risk

        # ── 2. OCR Keyword Verification ───────────────────────────────────
        if image_url and required_keywords:
            ocr_score, ocr_evidence = self._score_ocr(image_url, required_keywords)
            components['ocr'] = ocr_score
            evidence['ocr']   = ocr_evidence
        else:
            components['ocr'] = 0.1

        # ── 3. Behavioral Scoring ─────────────────────────────────────────
        if user_id:
            beh_score, beh_fraud, beh_evidence = self._score_behavior(user_id, ip_address)
            components['behavior'] = beh_score
            fraud_types.extend(beh_fraud)
            evidence['behavior']   = beh_evidence
        else:
            components['behavior'] = 0.1

        # ── Final weighted score ───────────────────────────────────────────
        overall = sum(
            components.get(k, 0) * w
            for k, w in self.WEIGHTS.items()
        )
        overall = min(1.0, overall)

        risk_level = (
            'critical' if overall >= 0.80 else
            'high'     if overall >= 0.60 else
            'medium'   if overall >= 0.35 else
            'low'
        )
        action = (
            'ban'    if overall >= 0.90 else
            'reject' if overall >= 0.70 else
            'flag'   if overall >= 0.40 else
            'allow'
        )
        confidence = min(1.0, len([c for c in components.values() if c > 0.1]) / 3 + 0.3)

        explanation = self._generate_explanation(overall, components, fraud_types)

        result = AIFraudScore(
            submission_id    = submission_id,
            overall_score    = round(overall, 3),
            risk_level       = risk_level,
            component_scores = {k: round(v, 3) for k, v in components.items()},
            fraud_types      = list(set(fraud_types)),
            evidence         = evidence,
            action           = action,
            confidence       = round(confidence, 3),
            explanation      = explanation,
        )

        cache.set(cache_key, result.__dict__, timeout=CACHE_TTL_FRAUD)
        logger.info(
            f'AI Fraud score: submission={submission_id}, '
            f'score={overall:.3f}, risk={risk_level}, action={action}'
        )
        return result

    def _score_image(self, image_url: str, expected_platform: str) -> tuple[float, list, dict]:
        """Image classifier দিয়ে fraud score করে।"""
        fraud_types = []
        try:
            from .image_classifier import ImageClassifier
            classifier = ImageClassifier()
            result     = classifier.classify(image_url, expected_platform=expected_platform)

            score = 1.0 - result.authenticity_score   # High authenticity = low fraud

            if result.manipulation_detected:
                fraud_types.append('image_manipulation')
                score = max(score, 0.75)
            if result.is_nsfw:
                fraud_types.append('nsfw_content')
                score = max(score, 0.60)
            if result.platform_detected and expected_platform and result.platform_detected != expected_platform:
                fraud_types.append('platform_mismatch')
                score = max(score, 0.50)

            return round(score, 3), fraud_types, {
                'authenticity':    result.authenticity_score,
                'platform':        result.platform_detected,
                'manipulation':    result.manipulation_type,
                'flags':           result.flags,
            }
        except Exception as e:
            logger.warning(f'Image scoring failed: {e}')
            return 0.2, [], {'error': str(e)}

    def _score_ocr(self, image_url: str, required_keywords: list) -> tuple[float, dict]:
        """OCR engine দিয়ে keyword verification করে।"""
        try:
            from .ocr_engine import ProofVerifier
            verifier = ProofVerifier()
            result   = verifier.verify_screenshot_proof(
                image_url, required_keywords=required_keywords
            )
            score = 1.0 - result.confidence  # High verification confidence = low fraud
            return round(score, 3), {
                'matched':  result.matched_keywords,
                'failed':   result.failed_checks,
                'ocr_conf': result.confidence,
            }
        except Exception as e:
            logger.warning(f'OCR scoring failed: {e}')
            return 0.2, {'error': str(e)}

    def _score_behavior(self, user_id: int, ip: str) -> tuple[float, list, dict]:
        """User behavior থেকে fraud signal বের করে।"""
        from api.promotions.models import FraudReport, UserReputation, Blacklist
        fraud_types = []
        score       = 0.0

        # Past fraud reports
        fraud_count = FraudReport.objects.filter(user_id=user_id).count()
        if fraud_count > 0:
            score += min(0.5, fraud_count * 0.15)
            fraud_types.append('repeat_fraudster')

        # Trust score
        try:
            rep = UserReputation.objects.get(user_id=user_id)
            if rep.trust_score < 20:
                score += 0.30; fraud_types.append('very_low_trust')
            elif rep.trust_score < 40:
                score += 0.15
        except UserReputation.DoesNotExist:
            score += 0.10  # New user = slight risk

        # IP blacklist
        if ip and Blacklist.is_blacklisted('ip', ip):
            score += 0.60; fraud_types.append('blacklisted_ip')

        return min(1.0, round(score, 3)), fraud_types, {
            'fraud_reports': fraud_count,
            'ip_blacklisted': bool(ip and Blacklist.is_blacklisted('ip', ip)),
        }

    @staticmethod
    def _generate_explanation(score: float, components: dict, fraud_types: list) -> str:
        parts = []
        if components.get('image', 0) > 0.5:
            parts.append('Image authenticity সন্দেহজনক')
        if components.get('ocr', 0) > 0.5:
            parts.append('Required keywords screenshot এ পাওয়া যায়নি')
        if components.get('behavior', 0) > 0.5:
            parts.append('User behavior সন্দেহজনক')
        if fraud_types:
            parts.append(f'Detected: {", ".join(fraud_types)}')
        return '. '.join(parts) if parts else 'No significant fraud signals.'