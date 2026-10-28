"""Wallet Signals

This module contains signals related to wallet transactions and balance updates.
These signals are triggered when wallet-related events occur and can be used
to send webhook notifications to subscribed endpoints.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import Signal
from django.utils import timezone
from django.contrib.auth import get_user_model

import logging

from ..services.core.DispatchService import DispatchService
from ..models import WebhookSubscription

User = get_user_model()

logger = logging.getLogger("ainul.webhooks.signals")


# Signal definitions
wallet_transaction_created = Signal()
wallet_balance_updated = Signal()
wallet_transaction_failed = Signal()


from ._isolation import isolated_receiver

@isolated_receiver
def on_wallet_transaction_created(sender, instance, created, **kwargs):
    """
    Signal handler for wallet transaction creation.
    Emits 'wallet.transaction.created' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'transaction_id': str(instance.id),
        'user_id': instance.user.id,
        'wallet_id': str(instance.wallet.id),
        'transaction_type': instance.transaction_type,
        'amount': str(instance.amount),
        'currency': instance.currency,
        'balance_before': str(instance.balance_before),
        'balance_after': str(instance.balance_after),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'status': instance.status,
        'created_at': instance.created_at.isoformat(),
        'metadata': getattr(instance, 'metadata', None) or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for wallet events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='wallet.transaction.created',
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
                event_type='wallet.transaction.created',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending wallet transaction webhook: %s", e)


@isolated_receiver
def on_wallet_balance_updated(sender, instance, **kwargs):
    """
    Signal handler for wallet balance updates.
    Emits 'wallet.balance.updated' webhook event.
    """
    # Prepare webhook payload
    payload = {
        'wallet_id': str(instance.id),
        'user_id': instance.user.id,
        'current_balance': str(instance.current_balance),
        'currency': instance.currency,
        'last_updated': instance.updated_at.isoformat() if instance.updated_at else None,
        'available_balance': str(instance.available_balance),
        'frozen_balance': str(instance.frozen_balance),
        'metadata': getattr(instance, 'metadata', None) or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for wallet events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='wallet.balance.updated',
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
                event_type='wallet.balance.updated',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending wallet balance webhook: %s", e)


@isolated_receiver
def on_wallet_transaction_failed(sender, instance, **kwargs):
    """
    Signal handler for failed wallet transactions.
    Emits 'wallet.transaction.failed' webhook event.
    """
    if instance.status != 'failed':
        return
    
    # Prepare webhook payload
    payload = {
        'transaction_id': str(instance.id),
        'user_id': instance.user.id,
        'wallet_id': str(instance.wallet.id),
        'transaction_type': instance.transaction_type,
        'amount': str(instance.amount),
        'currency': instance.currency,
        'balance_before': str(instance.balance_before),
        'balance_after': str(instance.balance_after),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'status': instance.status,
        'failure_reason': instance.failure_reason or '',
        'error_code': instance.error_code or '',
        'failed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'metadata': getattr(instance, 'metadata', None) or {}
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for wallet events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='wallet.transaction.failed',
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
                event_type='wallet.transaction.failed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending wallet transaction failed webhook: %s", e)


# Connect signal handlers
# Note: These would be connected in the apps.py ready() method
# Example:
# from api.wallet.models import WalletTransaction, Wallet
# post_save.connect(on_wallet_transaction_created, sender=WalletTransaction)
# post_save.connect(on_wallet_balance_updated, sender=Wallet)

# For demonstration, we'll define the connection function
def connect_wallet_signals():
    """Connect wallet-related signals to their handlers."""
    from api.wallet.models import WalletTransaction, Wallet
    
    try:
        post_save.connect(on_wallet_transaction_created, sender=WalletTransaction)
        post_save.connect(on_wallet_balance_updated, sender=Wallet)
        
        # For failed transactions, we need to check status in the handler
        post_save.connect(on_wallet_transaction_failed, sender=WalletTransaction)
        
        logger.info("[Webhooks] %s", "Wallet signals connected successfully")
    except ImportError:
        # Wallet app not available
        logger.warning("Wallet app not available, skipping signal connections")
    except Exception as e:
        logger.error("connecting wallet signals: %s", e)


def disconnect_wallet_signals():
    """Disconnect wallet-related signals."""
    from api.wallet.models import WalletTransaction, Wallet
    
    try:
        post_save.disconnect(on_wallet_transaction_created, sender=WalletTransaction)
        post_save.disconnect(on_wallet_balance_updated, sender=Wallet)
        post_save.disconnect(on_wallet_transaction_failed, sender=WalletTransaction)
        
        logger.info("[Webhooks] %s", "Wallet signals disconnected successfully")
    except ImportError:
        # Wallet app not available
        logger.warning("Wallet app not available, skipping signal disconnection")
    except Exception as e:
        logger.error("disconnecting wallet signals: %s", e)