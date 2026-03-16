# api/promotions/services/task_service.py
import logging
from django.db import transaction
logger = logging.getLogger('services.task')

class TaskService:
    def submit(self, worker_id: int, campaign_id: int, proof_data: dict) -> dict:
        from api.promotions.models import Campaign, TaskSubmission
        from api.promotions.choices import CampaignStatus, SubmissionStatus
        from api.promotions.governance.penalty_manager import PenaltyManager
        if PenaltyManager().check_suspended(worker_id):
            return {'error': 'Account suspended'}
        try:
            camp = Campaign.objects.get(pk=campaign_id, status=CampaignStatus.ACTIVE)
        except Campaign.DoesNotExist:
            return {'error': 'Campaign not found or inactive'}
        if camp.filled_slots >= camp.total_slots:
            return {'error': 'Campaign slots full'}
        if TaskSubmission.objects.filter(campaign_id=campaign_id, worker_id=worker_id, status__in=[SubmissionStatus.PENDING,SubmissionStatus.APPROVED]).exists():
            return {'error': 'Already submitted'}
        with transaction.atomic():
            sub = TaskSubmission.objects.create(
                campaign_id=campaign_id, worker_id=worker_id,
                status=SubmissionStatus.PENDING, **proof_data)
            from api.promotions.auditing.task_audit import TaskAuditor
            TaskAuditor().log_submission_created(sub.id, worker_id, campaign_id)
        return {'submission_id': sub.id, 'status': 'pending'}

    def auto_review(self, submission_id: int) -> dict:
        """AI-powered auto review।"""
        from api.promotions.utils.verification_engine import VerificationEngine
        decision = VerificationEngine().verify(submission_id)
        if decision.approved and decision.confidence >= 0.7:
            return self.approve(submission_id, actor_id=0, note='auto_approved_ai')
        elif not decision.approved and decision.confidence <= 0.2:
            return self.reject(submission_id, actor_id=0, reason='auto_rejected_ai')
        return {'status': 'manual_review_required', 'confidence': decision.confidence}

    def approve(self, submission_id: int, actor_id: int, note: str = '') -> dict:
        from api.promotions.models import TaskSubmission
        from api.promotions.choices import SubmissionStatus
        with transaction.atomic():
            sub = TaskSubmission.objects.select_for_update().get(pk=submission_id)
            if sub.status != SubmissionStatus.PENDING:
                return {'error': 'Not pending'}
            sub.status = SubmissionStatus.APPROVED
            sub.save(update_fields=['status'])
            self._credit_worker(sub)
            from api.promotions.auditing.task_audit import TaskAuditor
            TaskAuditor().log_submission_reviewed(submission_id, actor_id, 'pending', 'approved', note)
        return {'status': 'approved', 'reward_usd': float(sub.reward_usd)}

    def reject(self, submission_id: int, actor_id: int, reason: str = '') -> dict:
        from api.promotions.models import TaskSubmission
        from api.promotions.choices import SubmissionStatus
        TaskSubmission.objects.filter(pk=submission_id, status=SubmissionStatus.PENDING).update(status=SubmissionStatus.REJECTED, reject_reason=reason)
        return {'status': 'rejected', 'reason': reason}

    def _credit_worker(self, submission):
        try:
            from api.promotions.models import Wallet
            Wallet.objects.filter(user_id=submission.worker_id).update(balance_usd=models.F('balance_usd') + submission.reward_usd)
        except Exception as e:
            logger.error(f'Worker credit failed: {e}')
