"""Dispatch Service

This module provides webhook dispatch functionality with retry logic and scheduling.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
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
        
        Args:
            endpoint: The webhook endpoint to emit to
            event_type: The type of event being emitted
            payload: The event payload
            
        Returns:
            True if emission was queued successfully, False otherwise
        """
        try:
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
            
            # Queue async task
            from ..tasks.dispatch_event import dispatch_event
            dispatch_event.delay(
                endpoint_id=str(endpoint.id),
                event_type=event_type,
                payload=payload,
                async_emit=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error in asynchronous emit: {str(e)}")
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
                url=endpoint.url,
                method=endpoint.http_method or 'POST',
                headers=headers,
                payload=payload_json,
                timeout=endpoint.timeout_seconds or self.default_timeout,
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
            delivery_log.save()
            
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
            if endpoint.headers:
                headers.update(endpoint.headers)
            
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
            if endpoint.payload_template:
                from .TemplateEngine import TemplateEngine
                template_engine = TemplateEngine()
                payload = template_engine.render_template(endpoint.payload_template, payload)
            
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
                verify=verify_ssl
            )
            end_time = time.time()
            
            return {
                'status_code': response.status_code,
                'response_body': response.text,
                'response_headers': dict(response.headers),
                'duration_ms': int((end_time - start_time) * 1000),
                'success': response.status_code < 400
            }
            
        except requests.exceptions.Timeout:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'duration_ms': 0,
                'success': False,
                'error': 'Request timeout'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'duration_ms': 0,
                'success': False,
                'error': 'Connection error'
            }
        except Exception as e:
            return {
                'status_code': 0,
                'response_body': '',
                'response_headers': {},
                'duration_ms': 0,
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
            delivery_log.duration_ms = response['duration_ms']
            delivery_log.completed_at = timezone.now()
            
            if response['success']:
                delivery_log.status = DeliveryStatus.SUCCESS
            else:
                delivery_log.status = DeliveryStatus.FAILED
                delivery_log.error_message = response.get('error', 'HTTP request failed')
            
            delivery_log.save()
            
        except Exception as e:
            logger.error(f"Error updating delivery log: {str(e)}")
    
    def retry_delivery(self, delivery_log: WebhookDeliveryLog) -> bool:
        """
        Retry a failed webhook delivery.
        
        Args:
            delivery_log: The delivery log to retry
            
        Returns:
            True if retry was successful, False otherwise
        """
        try:
            # Check if retry is allowed
            if delivery_log.attempt_number >= delivery_log.max_attempts:
                delivery_log.status = DeliveryStatus.EXHAUSTED
                delivery_log.save()
                return False
            
            # Check if it's time to retry
            if delivery_log.next_retry_at and delivery_log.next_retry_at > timezone.now():
                return False
            
            # Increment attempt number
            delivery_log.attempt_number += 1
            delivery_log.status = DeliveryStatus.RETRYING
            delivery_log.save()
            
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
            next_retry_at = timezone.now() + timezone.timedelta(seconds=retry_delay)
            
            # Update delivery log
            delivery_log.next_retry_at = next_retry_at
            delivery_log.status = DeliveryStatus.PENDING
            delivery_log.save()
            
            # Queue retry task
            from ..tasks.dispatch_event import dispatch_event
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
            # Get relevant subscriptions
            subscriptions = WebhookSubscription.objects.filter(
                event_type=event_type,
                is_active=True,
                endpoint__status=WebhookStatus.ACTIVE
            ).select_related('endpoint')
            
            if user_id:
                subscriptions = subscriptions.filter(endpoint__owner_id=user_id)
            
            # Apply filters
            filtered_subscriptions = []
            for subscription in subscriptions:
                if self._should_emit_to_subscription(subscription, payload):
                    filtered_subscriptions.append(subscription)
            
            # Emit to each subscription
            results = {
                'total_subscriptions': subscriptions.count(),
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
            if not subscription.filter_config:
                return True
            
            # Apply filters
            from ..services.filtering import FilterService
            filter_service = FilterService()
            
            return filter_service.evaluate_filter(subscription.filter_config, payload)
            
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
            from datetime import timedelta
            
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
                avg_time=Avg('duration_ms')
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
