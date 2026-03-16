# api/promotions/governance/dispute_resolver.py
# Dispute Resolver — Submission disputes, evidence review, auto-resolution
import logging
from dataclasses import dataclass, field
from enum import Enum
from django.core.cache import cache
logger = logging.getLogger('governance.dispute')

class DisputeStatus(str, Enum):
    OPEN           = 'open'
    UNDER_REVIEW   = 'under_review'
    RESOLVED_WORKER = 'resolved_worker'   # Worker wins
    RESOLVED_ADVERTISER = 'resolved_advertiser'  # Advertiser wins
    AUTO_RESOLVED  = 'auto_resolved'
    ESCALATED      = 'escalated'

@dataclass
class DisputeResolution:
    dispute_id:   int
    decision:     str
    winner:       str         # 'worker' or 'advertiser'
    reason:       str
    evidence_used: list
    auto_resolved: bool
    refund_usd:   float = 0.0

class DisputeResolver:
    """
    Automated dispute resolution.
    High-confidence auto-resolve → otherwise escalate to admin.

    Auto-resolution rules:
    - Fraud score > 0.8 → Advertiser wins
    - OCR confidence > 0.8 + keywords matched → Worker wins
    - Multiple prior disputes from same user → Advertiser wins
    - Advertiser abuse pattern → Worker wins
    """

    AUTO_RESOLVE_FRAUD_THRESHOLD = 0.75

    def resolve(self, dispute_id: int) -> DisputeResolution:
        """Dispute auto-resolve করার চেষ্টা করে।"""
        try:
            from api.promotions.models import Dispute, TaskSubmission, FraudReport
            dispute    = Dispute.objects.select_related('submission__worker', 'submission__campaign').get(pk=dispute_id)
            submission = dispute.submission
        except Exception as e:
            logger.error(f'Dispute resolve failed: {e}')
            return DisputeResolution(dispute_id, 'error', '', str(e), [], False)

        evidence = []

        # Check fraud score
        fraud_reports  = FraudReport.objects.filter(user=submission.worker).count()
        if fraud_reports >= 3:
            evidence.append(f'prior_fraud_reports:{fraud_reports}')
            return self._close(dispute_id, 'advertiser', 'Multiple fraud reports', evidence, auto=True)

        # Check OCR proof
        ocr_confidence = getattr(submission, 'proof_ocr_confidence', 0)
        if ocr_confidence and ocr_confidence > 0.8:
            evidence.append(f'ocr_confidence:{ocr_confidence}')
            return self._close(dispute_id, 'worker', 'Screenshot proof verified by OCR', evidence, auto=True)

        # Check advertiser abuse (many disputes filed against many workers)
        adv_dispute_count = Dispute.objects.filter(
            submission__campaign__advertiser=submission.campaign.advertiser
        ).count()
        if adv_dispute_count > 20:
            evidence.append(f'advertiser_dispute_abuse:{adv_dispute_count}')
            return self._close(dispute_id, 'worker', 'Advertiser dispute abuse pattern', evidence, auto=True)

        # Cannot auto-resolve
        self._escalate(dispute_id)
        return DisputeResolution(dispute_id, 'escalated', '', 'Requires manual review', evidence, False)

    def _close(self, dispute_id, winner, reason, evidence, auto=False) -> DisputeResolution:
        status = DisputeStatus.AUTO_RESOLVED if auto else (
            DisputeStatus.RESOLVED_WORKER if winner == 'worker' else DisputeStatus.RESOLVED_ADVERTISER
        )
        try:
            from api.promotions.models import Dispute
            Dispute.objects.filter(pk=dispute_id).update(status=status.value, resolution_reason=reason)
        except Exception as e:
            logger.error(f'Dispute close DB update failed: {e}')
        return DisputeResolution(dispute_id, status.value, winner, reason, evidence, auto)

    def _escalate(self, dispute_id):
        try:
            from api.promotions.models import Dispute
            Dispute.objects.filter(pk=dispute_id).update(status=DisputeStatus.ESCALATED.value)
        except Exception:
            pass
