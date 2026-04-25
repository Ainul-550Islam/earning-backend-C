"""Dispatch Event Task

This module contains the background task for dispatching webhook events.
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import WebhookEndpoint, WebhookSubscription
from ..services.core import DispatchService
from ..choices import WebhookStatus

User = get_user_model()


@shared_task(bind=True, max_retries=3)
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
        
        # Check rate limiting
        if endpoint.rate_limit_per_min:
            from ..services.analytics import RateLimiterService
            rate_limiter = RateLimiterService()
            
            if not rate_limiter.is_allowed(endpoint.id, endpoint.rate_limit_per_min):
                return {
                    'success': False,
                    'reason': 'Rate limit exceeded',
                    'endpoint_id': str(endpoint_id),
                    'rate_limit': endpoint.rate_limit_per_min
                }
        
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
        
        # Dispatch the webhook
        dispatch_service = DispatchService()
        
        if async_emit:
            result = dispatch_service.emit_async(
                endpoint=endpoint,
                event_type=event_type,
                payload=payload
            )
        else:
            result = dispatch_service.emit(
                endpoint=endpoint,
                event_type=event_type,
                payload=payload
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
    
    dispatch_count = 0
    success_count = 0
    failed_count = 0
    
    for endpoint in endpoints:
        try:
            # Queue individual dispatch task
            dispatch_event.delay(str(endpoint.id), event_type, payload)
            dispatch_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Failed to queue dispatch for endpoint {endpoint.id}: {e}")
    
    return {
        'total_endpoints': endpoints.count(),
        'dispatched_count': dispatch_count,
        'success_count': success_count,
        'failed_count': failed_count
    }


@shared_task
def broadcast_event(event_type, payload, user_id=None):
    """
    Broadcast a webhook event to all relevant endpoints.
    
    Args:
        event_type: The type of event being broadcast
        payload: The event payload data
        user_id: Optional user ID for user-specific broadcasts
        
    Returns:
        dict: Summary of broadcast operations
    """
    # Get subscriptions for this event type
    subscriptions = WebhookSubscription.objects.filter(
        event_type=event_type,
        is_active=True,
        endpoint__status=WebhookStatus.ACTIVE
    ).select_related('endpoint')
    
    # Apply user filtering if specified
    if user_id:
        subscriptions = subscriptions.filter(endpoint__owner_id=user_id)
    
    broadcast_count = 0
    success_count = 0
    failed_count = 0
    
    for subscription in subscriptions:
        try:
            # Apply subscription filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Queue individual dispatch task
            dispatch_event.delay(
                str(subscription.endpoint.id),
                event_type,
                payload
            )
            broadcast_count += 1
            
        except Exception as e:
            failed_count += 1
            print(f"Failed to queue broadcast for subscription {subscription.id}: {e}")
    
    return {
        'total_subscriptions': subscriptions.count(),
        'broadcasted_count': broadcast_count,
        'success_count': success_count,
        'failed_count': failed_count
    }


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
