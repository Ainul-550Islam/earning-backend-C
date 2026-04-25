# api/payment_gateways/signals.py
# Full Django signals for payment_gateways — all model and business signals

import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import Signal, receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Custom business signals ────────────────────────────────────────────────────
# Payment lifecycle
payment_initiated        = Signal()  # args: user, amount, gateway, reference_id
payment_completed        = Signal()  # args: user, amount, gateway, reference_id
payment_failed           = Signal()  # args: user, amount, gateway, error
payment_refunded         = Signal()  # args: user, amount, original_reference_id

# Withdrawal lifecycle
withdrawal_requested     = Signal()  # args: user, amount, method
withdrawal_approved      = Signal()  # args: user, payout_request, approved_by
withdrawal_rejected      = Signal()  # args: user, payout_request, reason
withdrawal_completed     = Signal()  # args: user, payout_request
withdrawal_failed        = Signal()  # args: user, payout_request, error

# Conversion lifecycle
conversion_received      = Signal()  # args: conversion, click, offer
conversion_approved      = Signal()  # args: conversion, publisher
conversion_rejected      = Signal()  # args: conversion, publisher, reason
conversion_reversed      = Signal()  # args: conversion, publisher, amount

# Gateway health
gateway_went_down        = Signal()  # args: gateway_name, error
gateway_came_back        = Signal()  # args: gateway_name
gateway_degraded         = Signal()  # args: gateway_name, response_ms

# Publisher events
publisher_approved       = Signal()  # args: publisher_profile
publisher_suspended      = Signal()  # args: publisher_profile, reason
publisher_tier_changed   = Signal()  # args: user, old_tier, new_tier

# Fraud events
fraud_detected           = Signal()  # args: user, risk_score, reasons, action
fraud_blocked            = Signal()  # args: user, amount, gateway


# ── Model-level signal receivers ───────────────────────────────────────────────
@receiver(post_save, sender='payment_gateways.GatewayTransaction')
def on_transaction_saved(sender, instance, created, **kwargs):
    """Log all transaction events and fire business signals."""
    if created:
        logger.info(
            f'New transaction: id={instance.id} ref={instance.reference_id} '
            f'type={instance.transaction_type} gateway={instance.gateway} '
            f'amount={instance.amount} user={instance.user_id}'
        )
        payment_initiated.send(
            sender=sender,
            user=instance.user,
            amount=instance.amount,
            gateway=instance.gateway,
            reference_id=instance.reference_id,
        )
    else:
        if instance.status == 'completed':
            logger.info(
                f'Transaction completed: ref={instance.reference_id} '
                f'net={instance.net_amount}'
            )
            payment_completed.send(
                sender=sender,
                user=instance.user,
                amount=instance.net_amount,
                gateway=instance.gateway,
                reference_id=instance.reference_id,
            )
            # Broadcast to WebSocket
            _broadcast_transaction_completed(instance)

        elif instance.status == 'failed':
            logger.warning(
                f'Transaction failed: ref={instance.reference_id}'
            )
            payment_failed.send(
                sender=sender,
                user=instance.user,
                amount=instance.amount,
                gateway=instance.gateway,
                error=instance.notes or 'Transaction failed',
            )


@receiver(post_save, sender='payment_gateways.DepositRequest')
def on_deposit_saved(sender, instance, created, **kwargs):
    """Fire deposit lifecycle signals."""
    if not created:
        update_fields = kwargs.get('update_fields')
        status_changed = update_fields is None or 'status' in (update_fields or [])
        if status_changed and instance.status == 'completed':
            logger.info(f'Deposit completed: {instance.reference_id} net={instance.net_amount}')
            # Fire integration event
            try:
                from api.payment_gateways.events import emit_deposit_completed
                emit_deposit_completed(instance.user, instance)
            except Exception as e:
                logger.error(f'emit_deposit_completed failed: {e}')
            # Fire Django signal
            payment_completed.send(
                sender=sender,
                user=instance.user,
                amount=instance.net_amount,
                gateway=instance.gateway,
                reference_id=instance.reference_id,
            )


@receiver(post_save, sender='payment_gateways.PayoutRequest')
def on_payout_saved(sender, instance, created, **kwargs):
    """Fire payout lifecycle signals."""
    if created:
        withdrawal_requested.send(
            sender=sender,
            user=instance.user,
            amount=instance.amount,
            method=instance.payout_method,
        )
        logger.info(f'Payout requested: {instance.reference_id} {instance.amount}')
    else:
        if instance.status == 'approved':
            withdrawal_approved.send(
                sender=sender,
                user=instance.user,
                payout_request=instance,
                approved_by=instance.processed_by,
            )
        elif instance.status == 'processing':
            try:
                from api.payment_gateways.events import emit_withdrawal_processed
                emit_withdrawal_processed(instance.user, instance)
            except Exception as e:
                logger.error(f'emit_withdrawal_processed failed: {e}')
        elif instance.status == 'completed':
            withdrawal_completed.send(
                sender=sender,
                user=instance.user,
                payout_request=instance,
            )
            logger.info(f'Payout completed: {instance.reference_id}')
        elif instance.status == 'rejected':
            withdrawal_rejected.send(
                sender=sender,
                user=instance.user,
                payout_request=instance,
                reason=instance.admin_notes,
            )
        elif instance.status == 'failed':
            withdrawal_failed.send(
                sender=sender,
                user=instance.user,
                payout_request=instance,
                error='Gateway processing failed',
            )


@receiver(post_save, sender='payment_gateways.GatewayHealthLog')
def on_health_log_saved(sender, instance, created, **kwargs):
    """Fire gateway health signals and broadcast WebSocket updates."""
    if not created:
        return

    gateway_name = instance.gateway.name if instance.gateway_id else ''
    status       = instance.status

    if status == 'down' or status == 'error':
        gateway_went_down.send(
            sender=sender,
            gateway_name=gateway_name,
            error=instance.error,
        )
    elif status == 'healthy':
        gateway_came_back.send(
            sender=sender,
            gateway_name=gateway_name,
        )
    elif status == 'degraded':
        gateway_degraded.send(
            sender=sender,
            gateway_name=gateway_name,
            response_ms=instance.response_time_ms,
        )

    # Broadcast to admin WebSocket
    try:
        from api.payment_gateways.routing import broadcast_gateway_health
        broadcast_gateway_health(
            gateway_name, status,
            {'response_ms': instance.response_time_ms, 'error': instance.error}
        )
    except Exception:
        pass


# ── Business signal receivers ──────────────────────────────────────────────────
@receiver(gateway_went_down)
def handle_gateway_down(sender, gateway_name, error='', **kwargs):
    """Alert admin when gateway goes down."""
    logger.critical(f'GATEWAY DOWN: {gateway_name} — {error}')
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject=f'[ALERT] Gateway DOWN: {gateway_name}',
            message=f'Gateway {gateway_name} is DOWN.\nError: {error}\n\nCheck immediately.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)],
            fail_silently=True,
        )
    except Exception:
        pass


@receiver(gateway_came_back)
def handle_gateway_back(sender, gateway_name, **kwargs):
    """Log when gateway recovers."""
    logger.info(f'Gateway RECOVERED: {gateway_name}')


@receiver(withdrawal_approved)
def handle_withdrawal_approved(sender, user, payout_request, approved_by=None, **kwargs):
    """Trigger automatic processing after approval."""
    logger.info(f'Withdrawal approved: {payout_request.reference_id} — queuing for processing')
    try:
        from api.payment_gateways.tasks.withdrawal_processing_tasks import retry_failed_payout
        retry_failed_payout.apply_async(args=[payout_request.id], countdown=5)
    except Exception as e:
        logger.error(f'Could not queue withdrawal processing: {e}')


@receiver(fraud_blocked)
def handle_fraud_blocked(sender, user, amount, gateway, **kwargs):
    """Log and alert on fraud block."""
    logger.warning(f'FRAUD BLOCKED: user={user.id} amount={amount} gateway={gateway}')


# ── Helper functions ───────────────────────────────────────────────────────────
def _broadcast_transaction_completed(transaction):
    """Broadcast transaction completed event to user's WebSocket."""
    try:
        from api.payment_gateways.routing import broadcast_payment_event
        broadcast_payment_event(
            user_id=transaction.user_id,
            event_type=f'{transaction.transaction_type}_completed',
            data={
                'amount':       float(transaction.net_amount),
                'currency':     transaction.currency,
                'gateway':      transaction.gateway,
                'reference_id': transaction.reference_id,
                'type':         transaction.transaction_type,
            }
        )
    except Exception:
        pass  # WebSocket not available — non-critical
