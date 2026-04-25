# api/payment_gateways/integration_system/integ_signals.py
# Django signals that bridge payment_gateways models to the integration system

from django.dispatch import Signal, receiver
from django.db.models.signals import post_save
import logging

logger = logging.getLogger(__name__)

# ── Custom signals ─────────────────────────────────────────────────────────────
deposit_completed   = Signal()   # args: user, deposit
deposit_failed      = Signal()   # args: user, deposit, error
withdrawal_done     = Signal()   # args: user, payout_request
conversion_approved = Signal()   # args: conversion
conversion_reversed = Signal()   # args: conversion
fraud_detected      = Signal()   # args: user, transaction, result
gateway_health_changed = Signal()# args: gateway, old_status, new_status


# ── Signal receivers (fire integration handler) ───────────────────────────────
@receiver(deposit_completed)
def handle_deposit_completed(sender, user, deposit, **kwargs):
    """Fire integration handler when deposit completes."""
    from .integ_handler import handler
    try:
        handler.on_deposit_completed(user, deposit)
    except Exception as e:
        logger.error(f'integ_signals.deposit_completed failed: {e}')


@receiver(deposit_failed)
def handle_deposit_failed(sender, user, deposit, error='', **kwargs):
    from .integ_handler import handler
    try:
        handler.on_deposit_failed(user, deposit, error)
    except Exception as e:
        logger.error(f'integ_signals.deposit_failed handler error: {e}')


@receiver(withdrawal_done)
def handle_withdrawal_done(sender, user, payout_request, **kwargs):
    from .integ_handler import handler
    try:
        handler.on_withdrawal_processed(user, payout_request)
    except Exception as e:
        logger.error(f'integ_signals.withdrawal_done handler error: {e}')


@receiver(conversion_approved)
def handle_conversion_approved(sender, conversion, **kwargs):
    from .integ_handler import handler
    try:
        handler.on_conversion_approved(conversion)
    except Exception as e:
        logger.error(f'integ_signals.conversion_approved handler error: {e}')


@receiver(conversion_reversed)
def handle_conversion_reversed(sender, conversion, **kwargs):
    from .integ_handler import handler
    try:
        handler.on_conversion_reversed(conversion)
    except Exception as e:
        logger.error(f'integ_signals.conversion_reversed handler error: {e}')


@receiver(fraud_detected)
def handle_fraud_detected(sender, user, transaction, result, **kwargs):
    from .integ_handler import handler
    try:
        handler.on_fraud_detected(user, transaction, result)
    except Exception as e:
        logger.error(f'integ_signals.fraud_detected handler error: {e}')


# ── Django model signals → integration signals ────────────────────────────────
def connect_model_signals():
    """
    Connect Django model post_save signals to integration signals.
    Call this from AppConfig.ready().
    """
    try:
        from api.payment_gateways.models.deposit import DepositRequest

        @receiver(post_save, sender=DepositRequest)
        def on_deposit_save(sender, instance, created, **kwargs):
            if not created and instance.status == 'completed':
                old_status = kwargs.get('update_fields', [])
                if 'status' in (old_status or []) or True:
                    deposit_completed.send(
                        sender=sender,
                        user=instance.user,
                        deposit=instance,
                    )

        logger.debug('Model signals connected for DepositRequest')
    except Exception as e:
        logger.warning(f'Could not connect model signals: {e}')
