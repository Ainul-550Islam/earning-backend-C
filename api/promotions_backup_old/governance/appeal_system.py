# api/promotions/governance/appeal_system.py
# Appeal System — Rejected submissions, suspensions, penalties এর appeal
import logging
from dataclasses import dataclass
from enum import Enum
logger = logging.getLogger('governance.appeal')

class AppealStatus(str, Enum):
    SUBMITTED   = 'submitted'
    REVIEWING   = 'reviewing'
    APPROVED    = 'approved'
    REJECTED    = 'rejected'
    WITHDRAWN   = 'withdrawn'

@dataclass
class AppealResult:
    appeal_id:    int
    status:       str
    decision:     str
    refund_usd:   float = 0.0

class AppealSystem:
    """User appeals for rejected submissions, suspensions, penalties।"""

    def submit_appeal(self, user_id: int, subject_type: str, subject_id: int, reason: str, evidence: list = None) -> dict:
        """Appeal submit করে।"""
        try:
            from api.promotions.models import Appeal
            appeal = Appeal.objects.create(
                user_id=user_id, subject_type=subject_type, subject_id=subject_id,
                reason=reason[:1000], evidence=evidence or [], status=AppealStatus.SUBMITTED.value,
            )
            logger.info(f'Appeal submitted: user={user_id} type={subject_type} id={subject_id}')
            return {'appeal_id': appeal.id, 'status': AppealStatus.SUBMITTED.value, 'message': 'Appeal submitted successfully'}
        except Exception as e:
            return {'error': str(e)}

    def auto_review(self, appeal_id: int) -> AppealResult:
        """Simple appeals auto-resolve।"""
        try:
            from api.promotions.models import Appeal
            appeal = Appeal.objects.select_related().get(pk=appeal_id)

            # First appeal + subject is submission → give benefit of doubt
            if appeal.subject_type == 'submission':
                prior_appeals = Appeal.objects.filter(user=appeal.user, status='rejected').count()
                if prior_appeals == 0:
                    self._approve(appeal_id, 'First appeal — benefit of doubt')
                    return AppealResult(appeal_id, 'approved', 'first_appeal_benefit_of_doubt')

            # Flag for admin review
            Appeal.objects.filter(pk=appeal_id).update(status=AppealStatus.REVIEWING.value)
            return AppealResult(appeal_id, AppealStatus.REVIEWING.value, 'manual_review_required')
        except Exception as e:
            return AppealResult(appeal_id, 'error', str(e))

    def admin_decide(self, appeal_id: int, admin_id: int, approved: bool, reason: str, refund_usd: float = 0) -> AppealResult:
        status = AppealStatus.APPROVED.value if approved else AppealStatus.REJECTED.value
        try:
            from api.promotions.models import Appeal
            Appeal.objects.filter(pk=appeal_id).update(status=status, admin_note=reason, reviewed_by_id=admin_id)
            if approved and refund_usd > 0:
                appeal = Appeal.objects.get(pk=appeal_id)
                self._process_refund(appeal.user_id, refund_usd)
        except Exception as e:
            logger.error(f'Appeal decision failed: {e}')
        return AppealResult(appeal_id, status, reason, refund_usd)

    def _approve(self, appeal_id: int, reason: str):
        try:
            from api.promotions.models import Appeal
            Appeal.objects.filter(pk=appeal_id).update(status=AppealStatus.APPROVED.value, admin_note=reason)
        except Exception: pass

    def _process_refund(self, user_id: int, amount_usd: float):
        logger.info(f'Appeal refund: user={user_id} amount=${amount_usd}')
