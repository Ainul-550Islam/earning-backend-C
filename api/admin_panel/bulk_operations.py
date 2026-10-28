# api/admin_panel/bulk_operations.py
"""Bulk admin operations — ban 5000, approve 1000, etc. with progress tracking."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class BulkOperationsManager:
    """Execute and track bulk admin operations."""

    @classmethod
    def bulk_ban_users(cls, user_ids: List[Any], reason: str, actor) -> str:
        """Bulk ban — returns job_id for progress tracking."""
        from api.admin_panel.background_jobs import tracker
        job_id = tracker.create('bulk_ban', actor=actor.username)
        from api.admin_panel.tasks_cap import task_bulk_ban_users
        task_bulk_ban_users.delay(user_ids, reason, actor.pk)
        return job_id

    @classmethod
    def bulk_approve_payouts(cls, item_ids: List[Any], actor) -> str:
        """Bulk approve payouts — returns job_id."""
        from api.admin_panel.background_jobs import tracker
        job_id = tracker.create('bulk_approve_payouts', actor=actor.username)
        from celery import current_app
        current_app.send_task(
            'api.admin_panel.tasks.bulk_approve_payouts_task',
            args=[item_ids, actor.pk, job_id], queue='admin_panel.bulk'
        )
        return job_id

    @classmethod
    def bulk_send_notification(cls, user_ids: List[Any], title: str,
                                body: str, actor) -> Dict:
        """Bulk send notification to users."""
        try:
            from api.notifications.models import Notification
            notifications = [
                Notification(user_id=uid, title=title, message=body,
                              notification_type='admin_broadcast')
                for uid in user_ids
            ]
            Notification.objects.bulk_create(notifications, batch_size=500, ignore_conflicts=True)
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='bulk_notification',
                              changes={'count': len(user_ids), 'title': title})
            return {'success': True, 'sent': len(notifications)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def bulk_adjust_wallet(cls, user_ids: List[Any], amount: float,
                            reason: str, actor) -> Dict:
        """Bulk wallet adjustment."""
        from api.admin_panel.background_jobs import message_queue
        items = [{'user_id': uid, 'amount': amount} for uid in user_ids]
        ids = message_queue.enqueue_bulk('adjust_wallet', items)
        message_queue.process_all('bulk', max_messages=len(ids))
        return {'success': True, 'queued': len(ids), 'reason': reason}

    @classmethod
    def bulk_kyc_approve(cls, kyc_ids: List[Any], actor) -> Dict:
        """Bulk KYC approval."""
        from api.admin_panel.use_cases import ApproveKYCUseCase
        approved = failed = 0
        uc = ApproveKYCUseCase()
        for kyc_id in kyc_ids:
            r = uc.execute(kyc_id, actor)
            if r.success: approved += 1
            else: failed += 1
        return {'approved': approved, 'failed': failed, 'total': len(kyc_ids)}

    @classmethod
    def bulk_offer_pause(cls, offer_ids: List[Any], reason: str, actor) -> Dict:
        """Bulk pause offers."""
        try:
            from api.promotions.models import Campaign
            count = Campaign.objects.filter(pk__in=offer_ids, status='active').update(status='paused')
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='bulk_pause_offers',
                              changes={'count': count, 'reason': reason})
            return {'success': True, 'paused': count}
        except Exception as e:
            return {'success': False, 'error': str(e)}


bulk_ops = BulkOperationsManager()