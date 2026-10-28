# api/support/tasks_cap.py
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(bind=True, name='support.tasks_cap.verify_offer_dispute', max_retries=3)
    def verify_offer_dispute(self, dispute_id: int):
        try:
            from api.support.models import OfferDispute
            dispute = OfferDispute.objects.select_related('ticket', 'user').get(id=dispute_id)
            from api.support.integrations.integ_handler import integ_handler
            result = integ_handler.verify_and_process_offer_dispute(dispute, dispute.ticket)
            return result
        except Exception as exc:
            raise self.retry(exc=exc, countdown=300)

    @shared_task(bind=True, name='support.tasks_cap.auto_approve_eligible_disputes', max_retries=2)
    def auto_approve_eligible_disputes(self):
        from api.support.models import OfferDispute
        from api.support.integrations.project_specific.auto_approval_engine import auto_approval_engine
        pending = OfferDispute.objects.filter(status='pending', confidence_score__gte=0.6)[:50]
        approved = 0
        for dispute in pending:
            try:
                result = auto_approval_engine.evaluate(dispute)
                if result['decision'] == 'auto_approve':
                    verify_offer_dispute.apply_async(args=[dispute.id])
                    approved += 1
            except Exception:
                pass
        return {'evaluated': len(pending), 'queued': approved}

    @shared_task(bind=True, name='support.tasks_cap.flag_suspicious_patterns', max_retries=1)
    def flag_suspicious_dispute_patterns(self):
        from api.support.models import OfferDispute
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        User = get_user_model()
        week_ago = timezone.now() - timedelta(days=7)
        heavy = (OfferDispute.objects.filter(created_at__gte=week_ago)
                 .values('user').annotate(count=Count('id')).filter(count__gte=5))
        flagged = 0
        for item in heavy:
            try:
                user = User.objects.get(id=item['user'])
                from api.support.integrations.integ_adapter import fraud_adapter
                fraud_adapter.flag_user(user, reason=f'High dispute volume: {item["count"]}/7days')
                flagged += 1
            except Exception:
                pass
        return {'checked': len(heavy), 'flagged': flagged}

except ImportError:
    logger.warning('Celery not installed')