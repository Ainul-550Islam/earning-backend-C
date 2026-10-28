# api/support/integrations/integ_signals.py  — WORLD #1
"""
Integration Signals — তোমার project-এর other apps থেকে আসা Django signals।
OTHER APP signals → Support system reacts.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(post_save, sender='fraud_detection.FraudAlert')
def on_fraud_alert(sender, instance, created, **kwargs):
    """
    When fraud_detection creates FraudAlert → auto-create support ticket.
    High/Critical fraud alerts get tickets for manual review.
    """
    if not created:
        return
    try:
        priority = getattr(instance, 'priority', 'medium')
        if priority not in ('high', 'critical'):
            return
        user = getattr(instance, 'user', None)
        if not user:
            return
        from api.support.models import SupportTicket
        # Avoid duplicate tickets
        recent = SupportTicket.objects.filter(
            user=user, category='fraud', status__in=['open','in_progress'],
            created_at__gte=timezone.now() - __import__('datetime').timedelta(hours=1)
        )
        if recent.exists():
            return
        ticket = SupportTicket.objects.create(
            user        = user,
            category    = 'fraud',
            subject     = f'Fraud Alert: {getattr(instance,"alert_type","")}',
            description = (
                f"AUTOMATED: Fraud detection alert triggered.\n"
                f"Alert Type: {getattr(instance,'alert_type','')}\n"
                f"Priority: {priority}\n"
                f"Alert ID: {getattr(instance,'alert_id','')}\n"
                f"Agent review required."
            ),
            priority    = 'urgent' if priority == 'critical' else 'high',
            status      = 'open',
            channel     = 'api',
            tenant      = getattr(user, 'tenant', None),
        )
        logger.warning(f"Auto-ticket created from fraud alert: {ticket.ticket_id}")
    except Exception as e:
        logger.error(f"on_fraud_alert signal failed: {e}")


@receiver(post_save, sender='kyc.KYC')
def on_kyc_status_change(sender, instance, created, **kwargs):
    """
    When KYC is rejected → notify user via notifications app.
    """
    if created:
        return
    try:
        status = getattr(instance, 'status', None)
        if status != 'rejected':
            return
        user = getattr(instance, 'user', None)
        if not user:
            return
        from .integ_adapter import notifications_adapter
        notifications_adapter.send(
            user,
            'KYC Verification Rejected',
            'Your KYC verification was not approved. '
            'Please submit a support ticket to appeal or re-submit with clearer documents.',
            notification_type='kyc_rejected',
        )
        logger.info(f"KYC rejection notification sent to user {user.id}")
    except Exception as e:
        logger.debug(f"on_kyc_status_change signal failed: {e}")


@receiver(post_save, sender='wallet.WithdrawalRequest')
def on_withdrawal_status_change(sender, instance, created, **kwargs):
    """
    When withdrawal is rejected → offer auto-ticket creation.
    """
    if created:
        return
    try:
        status = getattr(instance, 'status', None)
        if status not in ('rejected', 'failed'):
            return
        user = getattr(instance, 'user', None)
        if not user:
            return
        from .integ_adapter import notifications_adapter
        notifications_adapter.send(
            user,
            'Withdrawal Request Issue',
            f'Your withdrawal request has a status issue ({status}). '
            'Please create a support ticket if you need assistance.',
            notification_type='withdrawal_issue',
        )
    except Exception as e:
        logger.debug(f"on_withdrawal_status_change signal failed: {e}")


def connect_all_signals():
    """Explicitly connect signals (call from apps.py ready())."""
    logger.debug("Integration signals connected.")