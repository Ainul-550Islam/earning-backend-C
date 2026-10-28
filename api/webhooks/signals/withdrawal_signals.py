"""Withdrawal Signals

This module contains signals related to withdrawal requests and processing.
These signals are triggered when withdrawal-related events occur and can be used
to send webhook notifications to subscribed endpoints.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal
from django.utils import timezone
from django.contrib.auth import get_user_model

import logging

from ..services.core.DispatchService import DispatchService
from ..models import WebhookSubscription

User = get_user_model()

logger = logging.getLogger("ainul.webhooks.signals")


def _resolve_withdrawal_request_model():
    """
    BUG FIX: this previously imported `from apps.wallets.models import
    WithdrawalRequest`, a package (`apps.`) that does not exist in this
    project. There is no single unambiguous owner without the sibling app
    source (WithdrawalRequest could live alongside the wallet models, or in
    a dedicated payout_queue app per the project's directory listing), so
    this tries the most likely candidates in order. Downstream
    (connect_withdrawal_signals) already degrades safely if this raises
    ImportError.
    """
    candidates = (
        "api.wallet.models",
        "api.payout_queue.models",
    )
    last_error = None
    for module_path in candidates:
        try:
            module = __import__(module_path, fromlist=["WithdrawalRequest"])
            return module.WithdrawalRequest
        except (ImportError, AttributeError) as e:
            last_error = e
            continue
    raise ImportError(
        f"Could not locate WithdrawalRequest model in any of {candidates}: {last_error}"
    )


# Signal definitions
withdrawal_requested = Signal()
withdrawal_approved = Signal()
withdrawal_rejected = Signal()
withdrawal_completed = Signal()
withdrawal_failed = Signal()


from ._isolation import isolated_receiver

@isolated_receiver
def on_withdrawal_requested(sender, instance, created, **kwargs):
    """
    Signal handler for withdrawal request creation.
    Emits 'withdrawal.requested' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'withdrawal_id': str(instance.id),
        'user_id': instance.user.id,
        'wallet_id': str(instance.wallet.id),
        'amount': str(instance.amount),
        'currency': instance.currency,
        'method': instance.method,
        'destination': instance.destination or '',
        'status': instance.status,
        'requested_at': instance.created_at.isoformat(),
        'reference': instance.reference or '',
        'notes': instance.notes or '',
        'metadata': instance.metadata or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for withdrawal events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='withdrawal.requested',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filters:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filters,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='withdrawal.requested',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending withdrawal requested webhook: %s", e)


@isolated_receiver
def on_withdrawal_approved(sender, instance, **kwargs):
    """
    Signal handler for withdrawal approval.
    Emits 'withdrawal.approved' webhook event.
    """
    if instance.status != 'approved':
        return
    
    # Prepare webhook payload
    payload = {
        'withdrawal_id': str(instance.id),
        'user_id': instance.user.id,
        'wallet_id': str(instance.wallet.id),
        'amount': str(instance.amount),
        'currency': instance.currency,
        'method': instance.method,
        'destination': instance.destination or '',
        'status': instance.status,
        'approved_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'approved_by': instance.approved_by.username if instance.approved_by else None,
        'approval_notes': instance.approval_notes or '',
        'reference': instance.reference or '',
        'metadata': instance.metadata or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for withdrawal events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='withdrawal.approved',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filters:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filters,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='withdrawal.approved',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending withdrawal approved webhook: %s", e)


@isolated_receiver
def on_withdrawal_rejected(sender, instance, **kwargs):
    """
    Signal handler for withdrawal rejection.
    Emits 'withdrawal.rejected' webhook event.
    """
    if instance.status != 'rejected':
        return
    
    # Prepare webhook payload
    payload = {
        'withdrawal_id': str(instance.id),
        'user_id': instance.user.id,
        'wallet_id': str(instance.wallet.id),
        'amount': str(instance.amount),
        'currency': instance.currency,
        'method': instance.method,
        'destination': instance.destination or '',
        'status': instance.status,
        'rejected_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'rejected_by': instance.rejected_by.username if instance.rejected_by else None,
        'rejection_reason': instance.rejection_reason or '',
        'reference': instance.reference or '',
        'metadata': instance.metadata or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for withdrawal events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='withdrawal.rejected',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filters:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filters,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='withdrawal.rejected',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending withdrawal rejected webhook: %s", e)


@isolated_receiver
def on_withdrawal_completed(sender, instance, **kwargs):
    """
    Signal handler for withdrawal completion.
    Emits 'withdrawal.completed' webhook event.
    """
    if instance.status != 'completed':
        return
    
    # Prepare webhook payload
    payload = {
        'withdrawal_id': str(instance.id),
        'user_id': instance.user.id,
        'wallet_id': str(instance.wallet.id),
        'amount': str(instance.amount),
        'currency': instance.currency,
        'method': instance.method,
        'destination': instance.destination or '',
        'status': instance.status,
        'completed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'transaction_id': instance.transaction_id or '',
        'processed_amount': str(instance.processed_amount) if instance.processed_amount else str(instance.amount),
        'fees': str(instance.fees) if instance.fees else '0',
        'reference': instance.reference or '',
        'metadata': instance.metadata or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for withdrawal events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='withdrawal.completed',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filters:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filters,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='withdrawal.completed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending withdrawal completed webhook: %s", e)


@isolated_receiver
def on_withdrawal_failed(sender, instance, **kwargs):
    """
    Signal handler for withdrawal failure.
    Emits 'withdrawal.failed' webhook event.
    """
    if instance.status != 'failed':
        return
    
    # Prepare webhook payload
    payload = {
        'withdrawal_id': str(instance.id),
        'user_id': instance.user.id,
        'wallet_id': str(instance.wallet.id),
        'amount': str(instance.amount),
        'currency': instance.currency,
        'method': instance.method,
        'destination': instance.destination or '',
        'status': instance.status,
        'failed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'failure_reason': instance.failure_reason or '',
        'error_code': instance.error_code or '',
        'reference': instance.reference or '',
        'retry_count': instance.retry_count or 0,
        'metadata': instance.metadata or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for withdrawal events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='withdrawal.failed',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filters:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filters,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='withdrawal.failed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending withdrawal failed webhook: %s", e)


# Connect signal handlers
# Note: These would be connected in the apps.py ready() method
def connect_withdrawal_signals():
    """
    Connect withdrawal-related signals to their handlers.

    BUG FIX: was catching its own ImportError/Exception and just logging,
    so it always returned normally - silently defeating connector.py's
    _try_connect(), which exists specifically to catch this ImportError
    and report {'withdrawal': False}. System was logging "withdrawal
    signals connected successfully" even when the sibling app genuinely
    wasn't installed and zero handlers got connected. Let exceptions
    propagate to connector.py, the single owner of that decision.
    """
    WithdrawalRequest = _resolve_withdrawal_request_model()

    post_save.connect(on_withdrawal_requested, sender=WithdrawalRequest)
    post_save.connect(on_withdrawal_approved, sender=WithdrawalRequest)
    post_save.connect(on_withdrawal_rejected, sender=WithdrawalRequest)
    post_save.connect(on_withdrawal_completed, sender=WithdrawalRequest)
    post_save.connect(on_withdrawal_failed, sender=WithdrawalRequest)

    logger.info("[Webhooks] %s", "Withdrawal signals connected successfully")


def disconnect_withdrawal_signals():
    """Disconnect withdrawal-related signals."""
    WithdrawalRequest = _resolve_withdrawal_request_model()

    post_save.disconnect(on_withdrawal_requested, sender=WithdrawalRequest)
    post_save.disconnect(on_withdrawal_approved, sender=WithdrawalRequest)
    post_save.disconnect(on_withdrawal_rejected, sender=WithdrawalRequest)
    post_save.disconnect(on_withdrawal_completed, sender=WithdrawalRequest)
    post_save.disconnect(on_withdrawal_failed, sender=WithdrawalRequest)

    logger.info("[Webhooks] %s", "Withdrawal signals disconnected successfully")