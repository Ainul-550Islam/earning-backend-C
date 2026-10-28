from ...exceptions import WebhookDispatchError, WebhookTimeoutError
"""Dispatch Service

This module provides webhook dispatch functionality with retry logic and scheduling.
"""

import logging
import time
from datetime import timedelta
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q
from django.conf import settings
from celery import current_app

from ...models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ...choices import DeliveryStatus, WebhookStatus
from .SignatureEngine import SignatureEngine

logger = logging.getLogger(__name__)


class DispatchService:
    """Service for dispatching webhook events to endpoints."""
    
    def __init__(self):
        """Initialize the dispatch service."""
        self.signature_engine = SignatureEngine()
        self.default_timeout = getattr(settings, 'WEBHOOK_DEFAULT_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'WEBHOOK_MAX_RETRIES', 3)
        self.retry_delay = getattr(settings, 'WEBHOOK_RETRY_DELAY', 60)

    def generate_signature(self, endpoint: WebhookEndpoint, payload: Dict[str, Any]) -> str:
        """Generate a signature for payload using endpoint's secret_key."""
        return self.signature_engine.sign_with_endpoint(payload, endpoint)

    def verify_signature(self, endpoint: WebhookEndpoint, payload: Dict[str, Any], signature: str) -> bool:
        """Verify a payload signature using endpoint's secret_key."""
        return self.signature_engine.verify_with_endpoint(payload, signature, endpoint)
    
    def emit(self, endpoint: WebhookEndpoint, event_type: str, payload: Dict[str, Any], async_emit: bool = False) -> bool:
        """
        Emit a webhook event to an endpoint.
        
        Args:
            endpoint: The webhook endpoint to emit to
            event_type: The type of event being emitted
            payload: The event payload
            async_emit: Whether to emit asynchronously
            
        Returns:
            True if emission was successful, False otherwise
        """
        try:
            if async_emit:
                return self._emit_async(endpoint, event_type, payload)
            else:
                return self._emit_sync(endpoint, event_type, payload)
        except Exception as e:
            logger.error(f"Error emitting webhook: {str(e)}")
            return False
    
    def _emit_sync(self, endpoint: WebhookEndpoint, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Emit webhook synchronously.
        
        Args:
            endpoint: The webhook endpoint to emit to
            event_type: The type of event being emitted
            payload: The event payload
            
        Returns:
            True if emission was successful, False otherwise
        """
        try:
            # Non-active endpoints must never receive dispatches - this was
            # previously unchecked anywhere in the emit path.
            if not endpoint.is_active_status():
                logger.info(
                    "Skipping dispatch to non-active endpoint %s (status=%s)",
                    endpoint.id, endpoint.status,
                )
                return False

            # Create delivery log
            delivery_log = WebhookDeliveryLog.objects.create(
                endpoint=endpoint,
                event_type=event_type,
                payload=payload,
                status=DeliveryStatus.PENDING,
                attempt_number=1,
                max_attempts=endpoint.max_retries or self.max_retries,
                dispatched_at=timezone.now()
            )
            
            # Perform dispatch
            result = self._dispatch(delivery_log)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in synchronous emit: {str(e)}")
            return False
    
    def _emit_async(self, endpoint: WebhookEndpoint, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Emit webhook asynchronously.

        BUG FIX: Removed duplicate delivery_log creation from this method.
        The delivery log is created inside _emit_sync(), which the Celery
        task calls after being dequeued. Creating it here AND in the task
        produced two delivery log rows per dispatch.

        Args:
            endpoint: The webhook endpoint to emit to
            event_type: The type of event being emitted
            payload: The event payload

        Returns:
            True if successfully queued, False otherwise
        """
        try:
            from ...tasks.dispatch_event import dispatch_event
            dispatch_event.delay(
                endpoint_id=str(endpoint.id),
                event_type=event_type,
                payload=payload,
                async_emit=False,   # task is already async; dispatch synchronously inside worker
            )
            return True
        except Exception as e:
            logger.error("Error queuing async webhook dispatch for endpoint %s: %s", endpoint.id, e)
            return False
    
    def _dispatch(self, delivery_log: WebhookDeliveryLog) -> bool:
        """
        Dispatch a webhook delivery.
        
        Args:
            delivery_log: The delivery log to dispatch
            
        Returns:
            True if dispatch was successful, False otherwise
        """
        try:
            endpoint = delivery_log.endpoint
            
            # Prepare request data
            headers = self._prepare_headers(endpoint, delivery_log)
            payload_json = self._prepare_payload(endpoint, delivery_log.payload)
            
            # Make HTTP request
            response = self._make_http_request(
                url=endpoint.target_url,
                method=endpoint.http_method or 'POST',
                headers=headers,
                payload=payload_json,
                timeout=self.default_timeout,  # BUG FIX: WebhookEndpoint has no timeout_seconds field
                verify_ssl=endpoint.verify_ssl
            )
            
            # Update delivery log with response
            self._update_delivery_log(delivery_log, response)
            
            # Return success status
            return delivery_log.status == DeliveryStatus.SUCCESS
            
        except Exception as e:
            logger.error(f"Error dispatching webhook: {str(e)}")
            
            # Update delivery log with error
            delivery_log.status = DeliveryStatus.FAILED
            delivery_log.error_message = str(e)
            delivery_log.completed_at = timezone.now()
            # BUG FIX: was an unscoped .save() - this method is called from
            # retry_delivery() too (via _dispatch()), sometimes with a
            # delivery_log fetched slightly before this point in time. An
            # unscoped save would rewrite every column from this possibly-
            # stale in-memory copy, including attempt_number - silently
            # undoing a concurrent retry's atomic claim (see retry_delivery()'s
            # docstring). Scoped to just the fields this branch actually sets.
            delivery_log.save(update_fields=['status', 'error_message', 'completed_at'])
            
            return False
    
    def _prepare_headers(self, endpoint: WebhookEndpoint, delivery_log: WebhookDeliveryLog) -> Dict[str, str]:
        """
        Prepare HTTP headers for webhook request.
        
        Args:
            endpoint: The webhook endpoint
            delivery_log: The delivery log
            
        Returns:
            Dictionary of HTTP headers
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Webhook-Client/1.0'
            }
            
            # Add custom headers
            if endpoint.custom_headers:
                headers.update(endpoint.custom_headers)
            
            # Add webhook-specific headers
            headers.update({
                'X-Webhook-Event': delivery_log.event_type,
                'X-Webhook-ID': str(delivery_log.id),
                'X-Webhook-Attempt': str(delivery_log.attempt_number)
            })
            
            # Add signature
            signature_headers = self.signature_engine.get_signature_headers(
                delivery_log.payload,
                endpoint.secret_key
            )
            headers.update(signature_headers)
            
            return headers
            
        except Exception as e:
            logger.error(f"Error preparing headers: {str(e)}")
            return {}
    
    def _prepare_payload(self, endpoint: WebhookEndpoint, payload: Dict[str, Any]) -> str:
        """
        Prepare payload for webhook request.
        
        Args:
            endpoint: The webhook endpoint
            payload: The original payload
            
        Returns:
            JSON string payload
        """
        try:
            import json
            
            # Apply template if configured
            if endpoint.payload_template and endpoint.payload_template.is_active:
                from .TemplateEngine import TemplateEngine
                template_engine = TemplateEngine()
                # render_template() already returns rendered JSON text (see
                # its own docstring) - return it directly. Passing it through
                # json.dumps() below would double-encode it into a JSON
                # string literal instead of the intended object.
                return template_engine.render_template(endpoint.payload_template, payload)
            
            # Convert to JSON
            return json.dumps(payload, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error preparing payload: {str(e)}")
            return json.dumps(payload)
    
    def _make_http_request(self, url: str, method: str, headers: Dict[str, str], payload: str, timeout: int, verify_ssl: bool) -> Dict[str, Any]:
        """
        Make HTTP request to webhook endpoint.
        
        Args:
            url: The webhook URL
            method: HTTP method
            headers: HTTP headers
            payload: Request payload
            timeout: Request timeout
            verify_ssl: Whether to verify SSL
            
        Returns:
            Response data dictionary
        """
        try:
            import requests
            
            # Make request
            start_time = time.time()
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=payload,
                timeout=timeout,
                verify=verify_ssl,
                # SECURITY FIX (SSRF): do not follow redirects. A validated,
                # safe-looking target_url could otherwise 302 to an internal
                # address at request time and bypass validate_webhook_url()
                # entirely, since that only ever sees the registered URL.
                allow_redirects=False,
            )
            end_time = time.time()
            
            return {
                'status_code': response.status_code,
                'response_body': response.text,
                'response_headers': dict(response.headers),
                'response_time_ms': int((end_time - start_time) * 1000),
                # Was `< 400` (treated 3xx as success). Now that redirects
                # are not followed, a 3xx means the payload never reached a
                # final destination, so only 2xx counts as success.
                'success': 200 <= response.status_code < 300
            }
            
        except requests.exceptions.Timeout:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'response_time_ms': 0,
                'success': False,
                'error': 'Request timeout'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'response_time_ms': 0,
                'success': False,
                'error': 'Connection error'
            }
        except Exception as e:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'response_time_ms': 0,
                'success': False,
                'error': str(e)
            }
    
    def _update_delivery_log(self, delivery_log: WebhookDeliveryLog, response: Dict[str, Any]) -> None:
        """
        Update delivery log with response data.
        
        Args:
            delivery_log: The delivery log to update
            response: The response data
        """
        try:
            delivery_log.http_status_code = response['status_code']
            delivery_log.response_body = response['response_body']
            delivery_log.response_time_ms = response['response_time_ms']
            delivery_log.completed_at = timezone.now()
            
            if response['success']:
                delivery_log.status = DeliveryStatus.SUCCESS
            else:
                delivery_log.status = DeliveryStatus.FAILED
                delivery_log.error_message = response.get('error', 'HTTP request failed')
            
            # BUG FIX: was an unscoped .save(). This is the last step of a
            # retry_delivery() call (via _dispatch()); by this point
            # delivery_log.attempt_number already reflects that retry's own
            # atomic claim, but an unscoped save here would rewrite every
            # column, including attempt_number - if a second concurrent
            # retry claimed a further increment while THIS dispatch's HTTP
            # call was in flight, this save would silently overwrite it
            # with the stale value read before that second claim happened.
            # Scoped to just the fields this method actually sets, so a
            # concurrent claim (see retry_delivery()'s docstring) survives.
            delivery_log.save(update_fields=[
                'http_status_code', 'response_body', 'response_time_ms',
                'completed_at', 'status', 'error_message',
            ])

            # BUG FIX: endpoint-level delivery counters were never updated
            # anywhere, so total_deliveries/success_deliveries/failed_deliveries
            # (and the success_rate property built on them) stayed at 0
            # forever regardless of real traffic. F() keeps this atomic
            # across concurrent deliveries to the same endpoint.
            if response['success']:
                WebhookEndpoint.objects.filter(pk=delivery_log.endpoint_id).update(
                    total_deliveries=F('total_deliveries') + 1,
                    success_deliveries=F('success_deliveries') + 1,
                    last_triggered_at=timezone.now(),
                )
            else:
                WebhookEndpoint.objects.filter(pk=delivery_log.endpoint_id).update(
                    total_deliveries=F('total_deliveries') + 1,
                    failed_deliveries=F('failed_deliveries') + 1,
                    last_triggered_at=timezone.now(),
                )
            
        except Exception as e:
            logger.error(f"Error updating delivery log: {str(e)}")
    
    def retry_delivery(self, delivery_log: WebhookDeliveryLog) -> bool:
        """
        Retry a failed webhook delivery.
        
        Args:
            delivery_log: The delivery log to retry
            
        Returns:
            True if retry was successful, False otherwise

        BUG FIX: the gating checks and the attempt_number increment used to
        run against delivery_log's in-memory snapshot, with a plain
        `attempt_number += 1` then `.save()` - a read-modify-write race.
        Two real callers can hit the same delivery log at nearly the same
        time (tasks/retry_failed_dispatch.py's scheduled beat-task retry,
        and views.py's manual API retry action), each with its own
        independently-loaded copy; both could read the same pre-increment
        attempt_number and each save the same post-increment value,
        silently losing an increment (confirmed empirically: 8 concurrent
        callers starting from attempt_number=1 landed on 5, not 9).

        Fixed with a single conditional UPDATE that re-checks both gating
        conditions (attempt budget + retry timing) against the current DB
        row and performs the increment as part of that same statement, via
        F() - matching this class's own established pattern for atomic
        counters (see the endpoint delivery counters in
        _update_delivery_log()). Confirmed empirically this closes the
        race (0 lost updates across 8 concurrent callers).

        select_for_update() was tried first, matching the pattern used
        elsewhere in this codebase (SecretRotationService) - but confirmed
        empirically unreliable for this on the project's SQLite test
        backend (intermittent "database table is locked" errors, and
        still lost an update even when it didn't error), so it was not
        used here. The F()-based conditional UPDATE has no such
        dependency on row-level locking support and was confirmed correct
        on this backend.

        delivery_log is refreshed from the DB after a successful claim (or
        after being marked exhausted) rather than having its fields set by
        hand, so it carries the real, DB-computed values - _dispatch()
        reads attempt_number for the X-Webhook-Attempt header, and
        tasks/retry_failed_dispatch.py reads delivery_log.attempt_number
        back off this same object afterward without its own refresh.
        """
        try:
            now = timezone.now()

            # Atomically claim this retry attempt. The WHERE clause folds
            # in both original gating checks; the increment happens in the
            # same statement via F(), so concurrent callers on the same
            # log serialize at the database level instead of racing on a
            # Python-side read-modify-write.
            claimed = WebhookDeliveryLog.objects.filter(
                pk=delivery_log.pk,
                attempt_number__lt=F('max_attempts'),
            ).filter(
                Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now)
            ).update(
                attempt_number=F('attempt_number') + 1,
                status=DeliveryStatus.RETRYING,
            )

            if not claimed:
                # Didn't get the claim - exhausted, not due yet, or a
                # concurrent retry just took it. Refresh to see which, and
                # mark exhausted explicitly if the budget is now used up
                # (matching the original exhausted-transition behavior).
                delivery_log.refresh_from_db()
                if delivery_log.attempt_number >= delivery_log.max_attempts:
                    delivery_log.status = DeliveryStatus.EXHAUSTED
                    delivery_log.save(update_fields=['status'])
                return False

            delivery_log.refresh_from_db()

            # Perform retry
            result = self._dispatch(delivery_log)
            
            return result
            
        except Exception as e:
            logger.error(f"Error retrying delivery: {str(e)}")
            return False
    
    def schedule_retry(self, delivery_log: WebhookDeliveryLog) -> bool:
        """
        Schedule a retry for a failed webhook delivery.
        
        Args:
            delivery_log: The delivery log to schedule retry for
            
        Returns:
            True if retry was scheduled successfully, False otherwise
        """
        try:
            # Check if retry is allowed
            if delivery_log.attempt_number >= delivery_log.max_attempts:
                delivery_log.status = DeliveryStatus.EXHAUSTED
                delivery_log.save()
                return False
            
            # Calculate retry delay (exponential backoff)
            retry_delay = self.retry_delay * (2 ** (delivery_log.attempt_number - 1))
            next_retry_at = timezone.now() + timedelta(seconds=retry_delay)  # BUG FIX: timezone has no .timedelta
            
            # Update delivery log
            delivery_log.next_retry_at = next_retry_at
            delivery_log.status = DeliveryStatus.PENDING
            delivery_log.save()
            
            # Queue retry task
            # BUG FIX: was `from ..tasks...` (2 dots) — this file is at
            # services/core/, two levels below webhooks/, so it needs 3 dots.
            # The 2-dot version raised ImportError: No module named
            # 'api.webhooks.services.tasks' on every call, silently caught
            # below, so next_retry_at got set but the actual retry was never queued.
            from ...tasks.dispatch_event import dispatch_event
            dispatch_event.apply_async(
                args=[str(delivery_log.endpoint.id), delivery_log.event_type, delivery_log.payload],
                eta=next_retry_at
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling retry: {str(e)}")
            return False
    
    def emit_to_subscribers(self, event_type: str, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Emit webhook event to all relevant subscribers.
        
        Args:
            event_type: The type of event being emitted
            payload: The event payload
            user_id: Optional user ID to filter subscribers
            
        Returns:
            Dictionary with emission results
        """
        try:
            # FIX: Use EventRouter.route_event() for subscription resolution.
            # Previously the ORM query was done inline; EventRouter centralises
            # routing logic (filter evaluation, orphan detection, statistics).
            try:
                from ..filtering.EventRouter import EventRouter
                router = EventRouter()
                filtered_subscriptions = router.route_event(
                    event_type=event_type,
                    payload=payload,
                    user_id=str(user_id) if user_id else None,
                )
                subscriptions = filtered_subscriptions  # router returns final list
            except ImportError:
                # Graceful fallback if EventRouter is unavailable
                subscriptions = WebhookSubscription.objects.filter(
                    event_type=event_type,
                    is_active=True,
                    endpoint__status=WebhookStatus.ACTIVE
                ).select_related('endpoint')
                if user_id:
                    subscriptions = subscriptions.filter(endpoint__owner_id=user_id)
                filtered_subscriptions = [
                    s for s in subscriptions
                    if self._should_emit_to_subscription(s, payload)
                ]
            
            # Emit to each subscription
            # NOTE: subscriptions is a plain list (not a QuerySet) whenever
            # EventRouter imports successfully - i.e. always, in practice.
            # .count() requires an argument on a list (it counts
            # occurrences of a value, unlike a QuerySet's zero-arg
            # .count()), so it raised TypeError on every real call here,
            # silently caught by this method's own except clause below.
            # len() works correctly on both a list and a QuerySet.
            results = {
                'total_subscriptions': len(subscriptions),
                'filtered_subscriptions': len(filtered_subscriptions),
                'successful_emits': 0,
                'failed_emits': 0,
                'emissions': []
            }
            
            for subscription in filtered_subscriptions:
                try:
                    success = self.emit(subscription.endpoint, event_type, payload, async_emit=True)
                    
                    if success:
                        results['successful_emits'] += 1
                    else:
                        results['failed_emits'] += 1
                    
                    results['emissions'].append({
                        'subscription_id': str(subscription.id),
                        'endpoint_id': str(subscription.endpoint.id),
                        'success': success
                    })
                    
                except Exception as e:
                    logger.error(f"Error emitting to subscription {subscription.id}: {str(e)}")
                    results['failed_emits'] += 1
                    results['emissions'].append({
                        'subscription_id': str(subscription.id),
                        'endpoint_id': str(subscription.endpoint.id),
                        'success': False,
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error emitting to subscribers: {str(e)}")
            return {
                'total_subscriptions': 0,
                'filtered_subscriptions': 0,
                'successful_emits': 0,
                'failed_emits': 0,
                'emissions': [],
                'error': str(e)
            }
    
    def _should_emit_to_subscription(self, subscription: WebhookSubscription, payload: Dict[str, Any]) -> bool:
        """
        Check if webhook should be emitted to subscription based on filters.
        
        Args:
            subscription: The subscription to check
            payload: The event payload
            
        Returns:
            True if webhook should be emitted, False otherwise
        """
        try:
            # If no filter config, emit to all
            if not subscription.filters:
                return True
            
            # Apply filters
            from ..filtering import FilterService  # BUG FIX: was ..services.filtering (wrong path)
            filter_service = FilterService()
            
            return filter_service.evaluate_subscription_filters(subscription.filters, payload)
            
        except Exception as e:
            logger.error(f"Error evaluating subscription filter: {str(e)}")
            # If filter evaluation fails, emit to be safe
            return True
    
    def get_delivery_statistics(self, endpoint_id: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
        """
        Get delivery statistics.
        
        Args:
            endpoint_id: Optional endpoint ID to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with delivery statistics
        """
        try:
            from django.db.models import Count, Avg, Q
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query
            query = WebhookDeliveryLog.objects.filter(created_at__gte=since)
            if endpoint_id:
                query = query.filter(endpoint_id=endpoint_id)
            
            # Get overall statistics
            total_deliveries = query.count()
            successful_deliveries = query.filter(status=DeliveryStatus.SUCCESS).count()
            failed_deliveries = query.filter(status=DeliveryStatus.FAILED).count()
            success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
            
            # Get performance statistics
            successful_logs = query.filter(status=DeliveryStatus.SUCCESS)
            avg_response_time = successful_logs.aggregate(
                avg_time=Avg('response_time_ms')
            )['avg_time'] or 0
            
            # Get status breakdown
            status_breakdown = query.values('status').annotate(
                count=Count('id')
            ).order_by('status')
            
            return {
                'total_deliveries': total_deliveries,
                'successful_deliveries': successful_deliveries,
                'failed_deliveries': failed_deliveries,
                'success_rate': round(success_rate, 2),
                'avg_response_time_ms': round(avg_response_time, 2),
                'status_breakdown': list(status_breakdown),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting delivery statistics: {str(e)}")
            return {
                'total_deliveries': 0,
                'successful_deliveries': 0,
                'failed_deliveries': 0,
                'success_rate': 0,
                'avg_response_time_ms': 0,
                'status_breakdown': [],
                'period_days': days,
                'error': str(e)
            }