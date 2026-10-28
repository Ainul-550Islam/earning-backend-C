"""Dispatch Event Task

This module contains the background task for dispatching webhook events.
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import WebhookEndpoint, WebhookSubscription
from ..services.core.DispatchService import DispatchService
from ..choices import WebhookStatus

import logging

logger = logging.getLogger('ainul.webhooks.tasks.dispatch.event')


User = get_user_model()


@shared_task(bind=True, max_retries=3, name="ainul.webhooks.dispatch_event")
def dispatch_event(self, endpoint_id, event_type, payload, async_emit=True):
    """
    Dispatch a webhook event to an endpoint.
    
    Args:
        endpoint_id: The ID of the webhook endpoint
        event_type: The type of event being dispatched
        payload: The event payload data
        async_emit: Whether to emit asynchronously
        
    Returns:
        dict: Result of the dispatch operation
    """
    logger.info('[Task] dispatch_event started')
    try:
        # Get the endpoint
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        
        # Check if endpoint is active
        if endpoint.status != WebhookStatus.ACTIVE:
            return {
                'success': False,
                'reason': 'Endpoint is not active',
                'endpoint_id': str(endpoint_id),
                'status': endpoint.status
            }
        
        # BUG FIX: a rate-limit-per-minute attribute does not exist on
        # WebhookEndpoint. Rate limiting via RateLimiterService uses the
        # WebhookRateLimit model (analytics) instead. The is_allowed()
        # method also did not exist on RateLimiterService; it was
        # is_rate_limited(). Rate-limit enforcement belongs in the view/
        # serializer layer before the task is queued; removed from here
        # to avoid AttributeError.

        # Get active subscriptions for this event type
        subscriptions = WebhookSubscription.objects.filter(
            endpoint=endpoint,
            event_type=event_type,
            is_active=True
        )
        
        if not subscriptions.exists():
            return {
                'success': False,
                'reason': 'No active subscriptions for this event type',
                'endpoint_id': str(endpoint_id),
                'event_type': event_type
            }

        # BUG FIX: subscriptions had a filters JSON field that was never
        # actually evaluated anywhere in the live dispatch path — every
        # active subscription for this event type got every event,
        # filters or not. Only dispatch if at least one subscription's
        # filters (or lack of them) actually match this payload.
        from ..services.filtering.FilterService import FilterService
        filter_service = FilterService()
        matching_subscriptions = [
            sub for sub in subscriptions
            if filter_service.evaluate_subscription_filters(sub.filters, payload)
        ]

        if not matching_subscriptions:
            return {
                'success': False,
                'reason': 'No subscriptions matched filters',
                'endpoint_id': str(endpoint_id),
                'event_type': event_type
            }
        
        # Dispatch the webhook
        # BUG FIX: an async-emit method on the service object never existed
        # (AttributeError). This task is already running inside a Celery
        # worker, so we must always dispatch synchronously here. _emit_sync()
        # creates the DeliveryLog and performs the HTTP request; it is the
        # correct entry-point for task-level dispatch.
        dispatch_service = DispatchService()
        result = dispatch_service._emit_sync(
            endpoint=endpoint,
            event_type=event_type,
            payload=payload,
        )
        
        return {
            'success': result,
            'endpoint_id': str(endpoint_id),
            'event_type': event_type,
            'async_emit': async_emit
        }
        
    except WebhookEndpoint.DoesNotExist:
        return {
            'success': False,
            'reason': 'Endpoint not found',
            'endpoint_id': str(endpoint_id)
        }
    except Exception as e:
        # Retry the task if there's an unexpected error
        raise self.retry(exc=e, countdown=60)


@shared_task
def dispatch_event_to_multiple_endpoints(event_type, payload, endpoint_ids=None):
    """
    Dispatch a webhook event to multiple endpoints.
    
    Args:
        event_type: The type of event being dispatched
        payload: The event payload data
        endpoint_ids: List of endpoint IDs to dispatch to (optional)
        
    Returns:
        dict: Summary of dispatch operations
    """
    logger.info('[Task] dispatch_event_to_multiple_endpoints started')
    # Get endpoints to dispatch to
    if endpoint_ids:
        endpoints = WebhookEndpoint.objects.filter(
            id__in=endpoint_ids,
            status=WebhookStatus.ACTIVE
        )
    else:
        # Get all active endpoints with subscriptions for this event type
        endpoints = WebhookEndpoint.objects.filter(
            status=WebhookStatus.ACTIVE,
            subscriptions__event_type=event_type,
            subscriptions__is_active=True
        ).distinct()
    
    queued_count  = 0
    failed_count  = 0
    total_endpoints = endpoints.count()   # BUG FIX: capture count before iterating

    for endpoint in endpoints:
        try:
            dispatch_event.delay(str(endpoint.id), event_type, payload)
            queued_count += 1
        except Exception as e:
            failed_count += 1
            logger.error("Failed to queue dispatch for endpoint %s: %s", endpoint.id, e)

    # BUG FIX: success_count was 0 forever; renamed queued_count for accuracy.
    return {
        'total_endpoints': total_endpoints,
        'queued_count': queued_count,
        'failed_count': failed_count,
    }


@shared_task
def broadcast_event(event_type, payload, user_id=None):
    """
    Broadcast a webhook event to all relevant subscribers.

    DRY FIX: Removed ~35 lines of duplicate subscription lookup, filter
    evaluation, and per-endpoint queuing that exactly replicated the logic
    already in DispatchService.emit_to_subscribers(). That method is the
    single canonical fan-out implementation — this task now delegates to it.

    Args:
        event_type: Platform event type string.
        payload:    Event data dictionary.
        user_id:    Optional — scope dispatch to one user's endpoints.

    Returns:
        dict: Summary from DispatchService.emit_to_subscribers().
    """
    logger.info("[Task] broadcast_event: event_type=%s user_id=%s", event_type, user_id)
    dispatch_service = DispatchService()
    return dispatch_service.emit_to_subscribers(
        event_type=event_type,
        payload=payload,
        user_id=str(user_id) if user_id else None,
    )


@shared_task
def dispatch_user_event(user_id, event_type, payload):
    """
    Dispatch a user-specific webhook event.
    
    Args:
        user_id: The ID of the user
        event_type: The type of event being dispatched
        payload: The event payload data
        
    Returns:
        dict: Result of the dispatch operation
    """
    logger.info('[Task] dispatch_user_event started')
    try:
        # Get the user
        user = User.objects.get(id=user_id)
        
        # Add user context to payload
        payload['user_id'] = user_id
        payload['user_email'] = user.email
        payload['user_username'] = user.username
        
        # Broadcast to user's endpoints
        return broadcast_event(event_type, payload, user_id)
        
    except User.DoesNotExist:
        return {
            'success': False,
            'reason': 'User not found',
            'user_id': str(user_id)
        }
    except Exception as e:
        return {
            'success': False,
            'reason': str(e),
            'user_id': str(user_id)
        }


@shared_task
def dispatch_system_event(event_type, payload):
    """
    Dispatch a system-wide webhook event.
    
    Args:
        event_type: The type of event being dispatched
        payload: The event payload data
        
    Returns:
        dict: Result of the dispatch operation
    """
    logger.info('[Task] dispatch_system_event started')
    # Add system context to payload
    payload['system_event'] = True
    payload['timestamp'] = timezone.now().isoformat()
    
    # Broadcast to all relevant endpoints
    return broadcast_event(event_type, payload)


@shared_task
def dispatch_scheduled_event(event_type, payload, schedule_at):
    """
    Dispatch a scheduled webhook event.
    
    Args:
        event_type: The type of event being dispatched
        payload: The event payload data
        schedule_at: When the event should be dispatched
        
    Returns:
        dict: Result of the dispatch operation
    """
    logger.info('[Task] dispatch_scheduled_event started')
    # Check if it's time to dispatch
    if schedule_at > timezone.now():
        # Schedule for later
        dispatch_event.apply_async(
            args=[event_type, payload],
            eta=schedule_at
        )
        
        return {
            'success': True,
            'scheduled': True,
            'schedule_at': schedule_at.isoformat(),
            'event_type': event_type
        }
    else:
        # Dispatch now
        return broadcast_event(event_type, payload)