# api/promotions/auditing/task_audit.py
# Task Audit — Submission lifecycle audit trail
import logging
from .transaction_audit import TransactionAuditor, AuditEntry
logger = logging.getLogger('auditing.task')
auditor = TransactionAuditor()

class TaskAuditor:
    """Task submission state change এর audit trail।"""

    def log_submission_created(self, submission_id: int, worker_id: int, campaign_id: int) -> str:
        return auditor.log(AuditEntry('submission', submission_id, 'create', worker_id, {},
            {'campaign_id': campaign_id, 'worker_id': worker_id, 'status': 'pending'}))

    def log_submission_reviewed(self, submission_id: int, reviewer_id: int,
                                 old_status: str, new_status: str, reason: str = '') -> str:
        return auditor.log(AuditEntry('submission', submission_id, f'review_{new_status}', reviewer_id,
            {'status': old_status}, {'status': new_status, 'reason': reason}))

    def log_reward_paid(self, submission_id: int, worker_id: int, amount_usd: float) -> str:
        return auditor.log(AuditEntry('submission', submission_id, 'reward_paid', worker_id,
            {}, {'reward_usd': amount_usd, 'paid': True}))

    def log_fraud_flagged(self, submission_id: int, flagged_by: int, score: float, reasons: list) -> str:
        return auditor.log(AuditEntry('submission', submission_id, 'fraud_flagged', flagged_by,
            {}, {'fraud_score': score, 'reasons': reasons}))

    def get_submission_history(self, submission_id: int) -> list:
        return auditor.get_history('submission', submission_id)
