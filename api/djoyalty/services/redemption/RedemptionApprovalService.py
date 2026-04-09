# api/djoyalty/services/redemption/RedemptionApprovalService.py
import logging
from .RedemptionService import RedemptionService
from ...constants import REDEMPTION_AUTO_APPROVE_THRESHOLD

logger = logging.getLogger(__name__)

class RedemptionApprovalService:
    @staticmethod
    def auto_approve_pending():
        from ...models.redemption import RedemptionRequest
        pending = RedemptionRequest.pending.filter(points_used__lte=REDEMPTION_AUTO_APPROVE_THRESHOLD)
        count = 0
        for req in pending:
            try:
                RedemptionService.approve(req.id, reviewed_by='auto-approve')
                count += 1
            except Exception as e:
                logger.error('Auto-approve error %s: %s', req.id, e)
        return count
