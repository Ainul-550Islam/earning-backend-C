"""Offer Signals

This module contains signals related to offer events and crediting.
These signals are triggered when offer-related events occur and can be used
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


def _resolve_offer_model():
    """
    BUG FIX: this previously imported `from apps.offers.models import Offer`,
    a package (`apps.`) that does not exist in this project — the real
    project has no `apps.` namespace; business apps live directly under
    `api.` (per the project's own directory listing: offer_inventory/,
    offer_routing/, offerwall/ — there is no single "offer" app).

    There isn't a single unambiguous "offer" app to point at without the
    sibling app source, so this tries the most likely candidates in order
    and uses whichever actually defines Offer. If neither matches your
    project, update this list with the correct path — everything downstream
    (connect_offer_signals) already degrades safely (logs a warning, does
    not crash) if this raises ImportError.
    """
    candidates = (
        "api.offer_inventory.models",
        "api.offer_routing.models",
    )
    last_error = None
    for module_path in candidates:
        try:
            module = __import__(module_path, fromlist=["Offer"])
            return module.Offer
        except (ImportError, AttributeError) as e:
            last_error = e
            continue
    raise ImportError(
        f"Could not locate Offer model in any of {candidates}: {last_error}"
    )


# Signal definitions
offer_credited = Signal()
offer_completed = Signal()
offer_expired = Signal()
offer_cancelled = Signal()
offer_updated = Signal()


from ._isolation import isolated_receiver

@isolated_receiver
def on_offer_credited(sender, instance, created, **kwargs):
    """
    Signal handler for offer crediting.
    Emits 'offer.credited' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'offer_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'offer_type': instance.offer_type,
        'offer_name': instance.name or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'status': instance.status if hasattr(instance, 'status') else 'credited',
        'credited_at': instance.created_at.isoformat(),
        'expires_at': instance.expires_at.isoformat() if hasattr(instance, 'expires_at') and instance.expires_at else None,
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for offer events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='offer.credited',
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
                event_type='offer.credited',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending offer credited webhook: %s", e)


@isolated_receiver
def on_offer_completed(sender, instance, **kwargs):
    """
    Signal handler for offer completion.
    Emits 'offer.completed' webhook event.
    """
    if instance.status != 'completed':
        return
    
    # Prepare webhook payload
    payload = {
        'offer_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'offer_type': instance.offer_type,
        'offer_name': instance.name or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'status': instance.status,
        'completed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'completed_by': getattr(instance, 'completed_by', {}).get('username') if hasattr(instance, 'completed_by') else None,
        'completion_notes': getattr(instance, 'completion_notes', ''),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for offer events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='offer.completed',
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
                event_type='offer.completed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending offer completed webhook: %s", e)


@isolated_receiver
def on_offer_expired(sender, instance, **kwargs):
    """
    Signal handler for offer expiration.
    Emits 'offer.expired' webhook event.
    """
    if instance.status != 'expired':
        return
    
    # Prepare webhook payload
    payload = {
        'offer_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'offer_type': instance.offer_type,
        'offer_name': instance.name or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'status': instance.status,
        'expired_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'expires_at': instance.expires_at.isoformat() if hasattr(instance, 'expires_at') and instance.expires_at else None,
        'reason': getattr(instance, 'expiration_reason', ''),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for offer events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='offer.expired',
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
                event_type='offer.expired',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending offer expired webhook: %s", e)


@isolated_receiver
def on_offer_cancelled(sender, instance, **kwargs):
    """
    Signal handler for offer cancellation.
    Emits 'offer.cancelled' webhook event.
    """
    if instance.status != 'cancelled':
        return
    
    # Prepare webhook payload
    payload = {
        'offer_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'offer_type': instance.offer_type,
        'offer_name': instance.name or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'status': instance.status,
        'cancelled_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'cancelled_by': getattr(instance, 'cancelled_by', {}).get('username') if hasattr(instance, 'cancelled_by') else None,
        'cancellation_reason': getattr(instance, 'cancellation_reason', ''),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for offer events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='offer.cancelled',
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
                event_type='offer.cancelled',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending offer cancelled webhook: %s", e)


@isolated_receiver
def on_offer_updated(sender, instance, **kwargs):
    """
    Signal handler for offer updates.
    Emits 'offer.updated' webhook event.
    """
    # Get previous state if available
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        changes = {}
        
        # Check for changes in key fields
        if hasattr(instance, 'name') and old_instance.name != instance.name:
            changes['name'] = {'old': old_instance.name, 'new': instance.name}
        
        if hasattr(instance, 'status') and old_instance.status != instance.status:
            changes['status'] = {'old': old_instance.status, 'new': instance.status}
        
        if hasattr(instance, 'amount') and old_instance.amount != instance.amount:
            changes['amount'] = {'old': str(old_instance.amount), 'new': str(instance.amount)}
        
        if hasattr(instance, 'expires_at') and old_instance.expires_at != instance.expires_at:
            changes['expires_at'] = {
                'old': old_instance.expires_at.isoformat() if old_instance.expires_at else None,
                'new': instance.expires_at.isoformat() if instance.expires_at else None
            }
        
        if not changes:
            return  # No significant changes
        
    except sender.DoesNotExist:
        # Offer is being created, not updated
        return
    
    # Prepare webhook payload
    payload = {
        'offer_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'offer_type': instance.offer_type,
        'offer_name': instance.name or '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'status': instance.status,
        'changes': changes,
        'updated_at': timezone.now().isoformat(),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for offer events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='offer.updated',
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
                event_type='offer.updated',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            logger.error("sending offer updated webhook: %s", e)


# Connect signal handlers
def connect_offer_signals():
    """
    Connect offer-related signals to their handlers.

    BUG FIX: this used to catch its own ImportError (and any other
    Exception) and just log a warning, so it always returned normally.
    That silently defeated connector.py's _try_connect(), whose whole job
    is to catch exactly that ImportError and report {'offer': False} - the
    system was logging "offer signals connected successfully" even when
    the sibling app genuinely wasn't installed and zero handlers got
    connected. Single owner for this decision is connector.py; let
    exceptions propagate there instead of swallowing them here too.
    """
    Offer = _resolve_offer_model()

    post_save.connect(on_offer_credited, sender=Offer)
    post_save.connect(on_offer_completed, sender=Offer)
    post_save.connect(on_offer_expired, sender=Offer)
    post_save.connect(on_offer_cancelled, sender=Offer)
    post_save.connect(on_offer_updated, sender=Offer)

    logger.info("[Webhooks] %s", "Offer signals connected successfully")


def disconnect_offer_signals():
    """Disconnect offer-related signals."""
    Offer = _resolve_offer_model()

    post_save.disconnect(on_offer_credited, sender=Offer)
    post_save.disconnect(on_offer_completed, sender=Offer)
    post_save.disconnect(on_offer_expired, sender=Offer)
    post_save.disconnect(on_offer_cancelled, sender=Offer)
    post_save.disconnect(on_offer_updated, sender=Offer)

    logger.info("[Webhooks] %s", "Offer signals disconnected successfully")