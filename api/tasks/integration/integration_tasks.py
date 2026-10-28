"""
tasks/integration/integration_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Integration Layer Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
These tasks are the glue between the EventBus, DataBridge, and all domain tasks.
They receive events and dispatch to the right handlers.

Every time a domain event fires, these tasks ensure:
- DataBridge is updated with latest state
- All downstream tasks are triggered
- Audit trail is maintained
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.integration.on_task_completed')
def on_task_completed(self, event: str, payload: dict) -> dict:
    """
    Handle 'task.completed' event.
    Dispatches to: gamification, fraud detection, analytics, leaderboard.
    """
    try:
        user_id = payload.get('user_id')
        task_id = payload.get('task_id')
        amount  = payload.get('reward_amount', 0)

        if not user_id:
            return {'status': 'skipped', 'reason': 'no_user_id'}

        from celery import current_app

        # 1. Update streak + badges
        current_app.send_task('tasks.gamification_tasks.update_streak_status',
                              kwargs={'user_id': user_id}, queue='default')
        current_app.send_task('tasks.gamification_tasks.award_badges',
                              kwargs={'user_id': user_id}, queue='default')
        # 2. Check milestones
        current_app.send_task('tasks.gamification_tasks.process_milestone_rewards',
                              kwargs={'user_id': user_id}, queue='default')
        # 3. Award XP (5 XP per task)
        current_app.send_task('tasks.gamification_tasks.award_xp_points',
                              kwargs={'user_id': user_id, 'xp': 5, 'reason': 'task_completion'},
                              queue='default')
        # 4. Affiliate commission
        if amount:
            current_app.send_task('tasks.affiliate_tasks.process_affiliate_commission',
                                  kwargs={'user_id': user_id, 'conversion_amount': str(amount),
                                          'conversion_type': 'task_completion'}, queue='default')
        # 5. Update DataBridge
        current_app.send_task('tasks.data_pipeline_tasks.sync_user_data_bridge',
                              kwargs={'user_ids': [user_id]}, queue='low')

        # 6. Email drip - pause if user is active
        current_app.send_task('tasks.email_drip_tasks.pause_drip',
                              kwargs={'user_id': user_id, 'sequence': 'reengagement', 'hours': 168},
                              queue='low')

        return {
            'status': 'success',
            'event': event,
            'user_id': user_id,
            'dispatched': ['gamification', 'milestones', 'xp', 'affiliate', 'data_bridge', 'drip_pause'],
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] on_task_completed handler: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.integration.on_user_registered')
def on_user_registered(self, event: str, payload: dict) -> dict:
    """
    Handle 'user.registered' event.
    Dispatches to: welcome drip, onboarding, referral check.
    """
    try:
        user_id = payload.get('user_id')
        ref_code = payload.get('referral_code', '')

        if not user_id:
            return {'status': 'skipped'}

        from celery import current_app

        # 1. Welcome email drip
        current_app.send_task('tasks.email_drip_tasks.enroll_user_in_drip',
                              kwargs={'user_id': user_id, 'sequence': 'welcome'}, queue='emails')
        # 2. Assign onboarding tasks
        current_app.send_task('tasks.user_lifecycle_tasks.assign_onboarding_tasks',
                              kwargs={'user_id': user_id}, queue='default')
        # 3. Detect locale
        ip = payload.get('ip_address', '')
        if ip:
            current_app.send_task('tasks.localization_tasks.detect_user_locale',
                                  kwargs={'user_id': user_id, 'ip_address': ip}, queue='default')
        # 4. Initial DataBridge sync
        current_app.send_task('tasks.data_pipeline_tasks.sync_user_data_bridge',
                              kwargs={'user_ids': [user_id]}, queue='low')
        # 5. ML recommendations
        current_app.send_task('tasks.ml_tasks.run_task_recommendation',
                              kwargs={'user_id': user_id}, queue='ml')

        return {
            'status': 'success',
            'event': event,
            'user_id': user_id,
            'dispatched': ['welcome_drip', 'onboarding', 'locale', 'data_bridge', 'ml_recommend'],
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.integration.on_offer_converted')
def on_offer_converted(self, event: str, payload: dict) -> dict:
    """
    Handle 'offer.converted' event (CPA/CPI/CPC conversion).
    Dispatches to: publisher credit, stats update, fraud scan, RTB.
    """
    try:
        user_id        = payload.get('user_id') or payload.get('publisher_id')
        offer_id       = payload.get('offer_id', '')
        transaction_id = payload.get('transaction_id', '')
        payout         = payload.get('payout', '0')
        status         = payload.get('status', 'approved')

        from celery import current_app

        if status == 'approved' and user_id:
            # Credit publisher
            current_app.send_task('tasks.cpalead_tasks.cpalead_credit_publisher',
                                  kwargs={
                                      'user_id': user_id,
                                      'payout': str(payout),
                                      'offer_id': offer_id,
                                      'conversion_id': transaction_id,
                                      'transaction_id': transaction_id,
                                  }, queue='payments')

        # Update offer stats
        current_app.send_task('tasks.cpalead_tasks.cpalead_update_offer_stats',
                              kwargs={'offer_id': offer_id, 'payout': str(payout), 'status': status},
                              queue='default')
        # Fraud scan
        current_app.send_task('tasks.cpalead_tasks.cpalead_fraud_scan_conversions',
                              kwargs={'lookback_hours': 1}, queue='high')
        # Update offer DataBridge
        current_app.send_task('tasks.data_pipeline_tasks.sync_offer_data_bridge',
                              queue='low')

        return {
            'status': 'success',
            'event': event,
            'offer_id': offer_id,
            'dispatched': ['credit_publisher', 'update_stats', 'fraud_scan', 'data_bridge'],
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.integration.on_fraud_detected')
def on_fraud_detected(self, event: str, payload: dict) -> dict:
    """
    Handle 'fraud.detected' event.
    Dispatches to: account suspend, alert admin, reverse transactions if needed.
    """
    try:
        user_id     = payload.get('user_id')
        fraud_score = payload.get('fraud_score', 0)
        reason      = payload.get('reason', 'unknown')

        if not user_id:
            return {'status': 'skipped'}

        from celery import current_app

        # Notify admin
        current_app.send_task('tasks.notification_tasks.dispatch_in_app_notification',
                              kwargs={
                                  'user_id': user_id,
                                  'title': '⚠️ Account Flagged',
                                  'message': f'Your account has been flagged for review. Score: {fraud_score}',
                                  'notification_type': 'warning',
                              }, queue='emails')

        # Flag in DataBridge
        from api.tasks.integration.data_bridge import DataBridge
        DataBridge.set_user(user_id, 'fraud_score', fraud_score, ttl=86400)

        # ATO detection
        current_app.send_task('tasks.fraud_detection_tasks.detect_account_takeover',
                              queue='high')

        return {
            'status': 'success',
            'event': event,
            'user_id': user_id,
            'fraud_score': fraud_score,
            'reason': reason,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.integration.on_payment_withdrawal_requested')
def on_payment_withdrawal_requested(self, event: str, payload: dict) -> dict:
    """
    Handle 'payment.withdrawal_requested' event.
    Dispatches to: fraud check, gateway processing, notification.
    """
    try:
        user_id       = payload.get('user_id')
        amount        = payload.get('amount', '0')
        withdrawal_id = payload.get('withdrawal_id')

        from celery import current_app

        # Fraud check first
        current_app.send_task('tasks.fraud_detection_tasks.flag_suspicious_withdrawal',
                              kwargs={'lookback_hours': 1}, queue='high')
        # Queue for processing
        current_app.send_task('tasks.payment_tasks.process_withdrawal_requests',
                              kwargs={'batch_size': 1}, queue='payments')

        return {
            'status': 'success',
            'event': event,
            'user_id': user_id,
            'amount': amount,
            'dispatched': ['fraud_check', 'process_withdrawal'],
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)
