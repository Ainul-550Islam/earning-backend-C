# api/promotions/utils/screenshot_validator.py
import logging
from dataclasses import dataclass
from typing import Optional
logger = logging.getLogger('utils.screenshot')

@dataclass
class ValidationResult:
    valid: bool; confidence: float; platform: str; issues: list; recommendation: str

class ScreenshotValidator:
    """Unified screenshot proof validation — combines AI modules。"""

    def validate(self, image_bytes: bytes, expected_platform: str,
                 required_keywords: list, campaign_url: str = None) -> ValidationResult:
        issues = []; confidence = 0.0; platform = ''

        # OCR verification
        try:
            from api.promotions.ai.ocr_engine import ProofVerifier
            ocr = ProofVerifier().verify_screenshot_proof(
                image_bytes=image_bytes,
                required_keywords=required_keywords,
                campaign_url=campaign_url or '',
                task_type=expected_platform + '_general',
            )
            confidence += ocr.confidence * 0.4
            if ocr.recommendation == 'reject':
                issues.append('keywords_not_found')
        except Exception as e:
            issues.append(f'ocr_failed:{str(e)[:50]}')

        # Image classification
        try:
            from api.promotions.ai.image_classifier import ImageClassifier
            img = ImageClassifier().classify(image_bytes=image_bytes, expected_platform=expected_platform)
            platform = img.detected_platform or ''
            confidence += img.authenticity_score * 0.4
            if img.is_manipulated: issues.append('manipulation_detected')
            if img.is_nsfw:        issues.append('nsfw_content')
        except Exception as e:
            issues.append(f'classifier_failed:{str(e)[:50]}')

        # Fraud score
        try:
            from api.promotions.ai.fraud_score import AIFraudScorer
            fraud = AIFraudScorer().score_from_image(image_bytes, expected_platform, required_keywords)
            confidence += (1 - fraud.overall_score) * 0.2
            if fraud.action == 'ban':    issues.append('fraud_critical')
            elif fraud.action == 'reject': issues.append('fraud_high')
        except Exception:
            confidence += 0.1   # Neutral if fraud checker unavailable

        rec = 'approve' if confidence >= 0.65 and not issues else ('review' if confidence >= 0.4 else 'reject')
        return ValidationResult(valid=confidence >= 0.65, confidence=round(confidence,3),
                                platform=platform, issues=issues, recommendation=rec)
