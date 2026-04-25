"""Payment Signals

This module contains signals related to payment processing and transactions.
These signals are triggered when payment-related events occur and can be used
to send webhook notifications to subscribed endpoints.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..services.core import DispatchService
from ..models import WebhookSubscription

User = get_user_model()


# Signal definitions
payment_succeeded = Signal()
payment_failed = Signal()
payment_initiated = Signal()
payment_cancelled = Signal()
payment_refunded = Signal()
payment_disputed = Signal()


def on_payment_succeeded(sender, instance, **kwargs):
    """
    Signal handler for successful payment.
    Emits 'payment.succeeded' webhook event.
    """
    if instance.status != 'succeeded':
        return
    
    # Prepare webhook payload
    payload = {
        'payment_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'transaction_id': instance.transaction_id or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'payment_method': instance.payment_method if hasattr(instance, 'payment_method') else 'unknown',
        'status': instance.status,
        'processed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'gateway': instance.gateway if hasattr(instance, 'gateway') else 'unknown',
        'gateway_transaction_id': instance.gateway_transaction_id if hasattr(instance, 'gateway_transaction_id') else '',
        'reference': instance.reference or '',
        'description': instance.description or '',
        'fees': str(instance.fees) if hasattr(instance, 'fees') else '0',
        'net_amount': str(instance.net_amount) if hasattr(instance, 'net_amount') else str(instance.amount),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for payment events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='payment.succeeded',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='payment.succeeded',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending payment succeeded webhook: {e}")


def on_payment_failed(sender, instance, **kwargs):
    """
    Signal handler for failed payment.
    Emits 'payment.failed' webhook event.
    """
    if instance.status != 'failed':
        return
    
    # Prepare webhook payload
    payload = {
        'payment_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'transaction_id': instance.transaction_id or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'payment_method': instance.payment_method if hasattr(instance, 'payment_method') else 'unknown',
        'status': instance.status,
        'failed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'gateway': instance.gateway if hasattr(instance, 'gateway') else 'unknown',
        'gateway_transaction_id': instance.gateway_transaction_id if hasattr(instance, 'gateway_transaction_id') else '',
        'failure_reason': instance.failure_reason if hasattr(instance, 'failure_reason') else '',
        'error_code': instance.error_code if hasattr(instance, 'error_code') else '',
        'reference': instance.reference or '',
        'description': instance.description or '',
        'retry_count': instance.retry_count if hasattr(instance, 'retry_count') else 0,
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for payment events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='payment.failed',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='payment.failed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending payment failed webhook: {e}")


def on_payment_initiated(sender, instance, created, **kwargs):
    """
    Signal handler for payment initiation.
    Emits 'payment.initiated' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'payment_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'transaction_id': instance.transaction_id or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'payment_method': instance.payment_method if hasattr(instance, 'payment_method') else 'unknown',
        'status': instance.status,
        'initiated_at': instance.created_at.isoformat(),
        'gateway': instance.gateway if hasattr(instance, 'gateway') else 'unknown',
        'gateway_transaction_id': instance.gateway_transaction_id if hasattr(instance, 'gateway_transaction_id') else '',
        'reference': instance.reference or '',
        'description': instance.description or '',
        'return_url': instance.return_url if hasattr(instance, 'return_url') else '',
        'cancel_url': instance.cancel_url if hasattr(instance, 'cancel_url') else '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for payment events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='payment.initiated',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='payment.initiated',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending payment initiated webhook: {e}")


def on_payment_cancelled(sender, instance, **kwargs):
    """
    Signal handler for payment cancellation.
    Emits 'payment.cancelled' webhook event.
    """
    if instance.status != 'cancelled':
        return
    
    # Prepare webhook payload
    payload = {
        'payment_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'transaction_id': instance.transaction_id or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'payment_method': instance.payment_method if hasattr(instance, 'payment_method') else 'unknown',
        'status': instance.status,
        'cancelled_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'gateway': instance.gateway if hasattr(instance, 'gateway') else 'unknown',
        'gateway_transaction_id': instance.gateway_transaction_id if hasattr(instance, 'gateway_transaction_id') else '',
        'cancellation_reason': instance.cancellation_reason if hasattr(instance, 'cancellation_reason') else '',
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for payment events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='payment.cancelled',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='payment.cancelled',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending payment cancelled webhook: {e}")


def on_payment_refunded(sender, instance, **kwargs):
    """
    Signal handler for payment refund.
    Emits 'payment.refunded' webhook event.
    """
    if instance.status != 'refunded':
        return
    
    # Prepare webhook payload
    payload = {
        'payment_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'transaction_id': instance.transaction_id or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'payment_method': instance.payment_method if hasattr(instance, 'payment_method') else 'unknown',
        'status': instance.status,
        'refunded_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'gateway': instance.gateway if hasattr(instance, 'gateway') else 'unknown',
        'gateway_transaction_id': instance.gateway_transaction_id if hasattr(instance, 'gateway_transaction_id') else '',
        'refund_amount': str(instance.refund_amount) if hasattr(instance, 'refund_amount') else str(instance.amount),
        'refund_reason': instance.refund_reason if hasattr(instance, 'refund_reason') else '',
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for payment events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='payment.refunded',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='payment.refunded',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending payment refunded webhook: {e}")


def on_payment_disputed(sender, instance, **kwargs):
    """
    Signal handler for payment dispute.
    Emits 'payment.disputed' webhook event.
    """
    if instance.status != 'disputed':
        return
    
    # Prepare webhook payload
    payload = {
        'payment_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'transaction_id': instance.transaction_id or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'payment_method': instance.payment_method if hasattr(instance, 'payment_method') else 'unknown',
        'status': instance.status,
        'disputed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'gateway': instance.gateway if hasattr(instance, 'gateway') else 'unknown',
        'gateway_transaction_id': instance.gateway_transaction_id if hasattr(instance, 'gateway_transaction_id') else '',
        'dispute_reason': instance.dispute_reason if hasattr(instance, 'dispute_reason') else '',
        'dispute_category': instance.dispute_category if hasattr(instance, 'dispute_category') else '',
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for payment events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='payment.disputed',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='payment.disputed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending payment disputed webhook: {e}")


# Connect signal handlers
def connect_payment_signals():
    """Connect payment-related signals to their handlers."""
    from apps.payments.models import Payment
    
    try:
        post_save.connect(on_payment_succeeded, sender=Payment)
        post_save.connect(on_payment_failed, sender=Payment)
        post_save.connect(on_payment_initiated, sender=Payment)
        post_save.connect(on_payment_cancelled, sender=Payment)
        post_save.connect(on_payment_refunded, sender=Payment)
        post_save.connect(on_payment_disputed, sender=Payment)
        
        print("Payment signals connected successfully")
    except ImportError:
        # Payment app not available
        print("Payment app not available, skipping signal connections")
    except Exception as e:
        print(f"Error connecting payment signals: {e}")


def disconnect_payment_signals():
    """Disconnect payment-related signals."""
    from apps.payments.models import Payment
    
    try:
        post_save.disconnect(on_payment_succeeded, sender=Payment)
        post_save.disconnect(on_payment_failed, sender=Payment)
        post_save.disconnect(on_payment_initiated, sender=Payment)
        post_save.disconnect(on_payment_cancelled, sender=Payment)
        post_save.disconnect(on_payment_refunded, sender=Payment)
        post_save.disconnect(on_payment_disputed, sender=Payment)
        
        print("Payment signals disconnected successfully")
    except ImportError:
        # Payment app not available
        print("Payment app not available, skipping signal disconnection")
    except Exception as e:
        print(f"Error disconnecting payment signals: {e}")
