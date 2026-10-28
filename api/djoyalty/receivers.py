# api/djoyalty/receivers.py
"""
Djoyalty Signal Receivers -- All Django signal handlers।
Called from signals.py after model saves।
"""
import logging
logger = logging.getLogger(__name__)


def on_customer_created(sender, instance, created, **kwargs):
    """New customer created -> create points account + send welcome."""
    if not created:
        return
    try:
        from .models.points import LoyaltyPoints
        from decimal import Decimal
        LoyaltyPoints.objects.get_or_create(
            customer=instance,
            defaults={'tenant': instance.tenant, 'balance': Decimal('0')},
        )
        logger.debug('receivers: LoyaltyPoints created for %s', instance.code)
    except Exception as e:
        logger.error('on_customer_created error: %s', e)

    # Welcome notification (async)
    try:
        from .services.NotificationService import NotificationService
        from .integrations.email import EmailService
        NotificationService.send(
            instance, 'campaign_active',
            title='🎉 Loyalty Program এ স্বাগতম!',
            body=f'প্রিয় {instance.firstname or instance.code}, আপনার Loyalty account তৈরি হয়েছে!',
            icon='🎉',
        )
        if instance.email:
            EmailService.send_welcome(instance)
    except Exception as e:
        logger.debug('Welcome notification error: %s', e)


def on_txn_created(sender, instance, created, **kwargs):
    """New transaction -> trigger earn rules evaluation."""
    if not created:
        return
    try:
        from .tasks.earn_rule_tasks import evaluate_earn_rules_task
        evaluate_earn_rules_task.delay(
            customer_id=instance.customer_id,
            txn_id=instance.id,
        )
    except Exception as e:
        logger.debug('on_txn_created earn eval error: %s', e)


def on_redemption_approved(sender, instance, **kwargs):
    """Redemption approved -> notify customer."""
    if instance.status != 'approved':
        return
    try:
        from .services.NotificationService import NotificationService
        NotificationService.send(
            instance.customer, 'offer_available',
            title='✅ Redemption Approved!',
            body=f'আপনার redemption #{instance.id} approved হয়েছে।',
            icon='✅',
        )
    except Exception as e:
        logger.debug('on_redemption_approved error: %s', e)


def on_cashout_status_changed(sender, instance, **kwargs):
    """CashoutRequest status changed -> notify + process payment."""
    try:
        if instance.status == 'approved':
            from .tasks.earn_rule_tasks import evaluate_earn_rules_task
            # Process payment via integration
            from .integration_system.bridge import loyalty_bridge
            loyalty_bridge.initiate_cashout_payment(instance)
        elif instance.status == 'completed':
            from .services.NotificationService import NotificationService
            NotificationService.notify_cashout_complete(
                instance.customer,
                instance.cash_amount,
                instance.cashout_method,
            )
    except Exception as e:
        logger.debug('on_cashout_status_changed error: %s', e)
