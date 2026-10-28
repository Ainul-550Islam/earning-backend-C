# api/rate_limit/webhooks_integration.py
"""
Webhooks integration system for rate limit module.

Provides webhook management and delivery capabilities.
"""

import logging
import hashlib
import hmac
import json
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.contrib.auth import get_user_model
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from api.rate_limit.integ_constants import IntegrationStatus, IntegrationEvent
from api.rate_limit.integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)
User = get_user_model()


class WebhookEvent:
    """Represents a webhook event."""
    
    def __init__(self, event_type: str, data: Dict[str, Any], webhook_url: str,
                 secret_key: str = None, headers: Dict[str, Any] = None,
                 timeout: int = 30, retry_attempts: int = 3):
        self.event_id = f"webhook_{timezone.now().timestamp()}_{id(self)}"
        self.event_type = event_type
        self.data = data
        self.webhook_url = webhook_url
        self.secret_key = secret_key
        self.headers = headers or {}
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.created_at = timezone.now()
        self.delivered_at = None
        self.delivery_attempts = 0
        self.status = 'pending'
        self.error_message = None
        self.response_status = None
        self.response_body = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert webhook event to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'data': self.data,
            'webhook_url': self.webhook_url,
            'created_at': self.created_at.isoformat(),
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'delivery_attempts': self.delivery_attempts,
            'status': self.status,
            'error_message': self.error_message,
            'response_status': self.response_status,
            'response_body': self.response_body
        }


class WebhookSignature:
    """Handles webhook signature generation and verification."""
    
    @staticmethod
    def generate_signature(payload: str, secret_key: str, algorithm: str = 'sha256') -> str:
        """
        Generate webhook signature.
        
        Args:
            payload: Payload to sign
            secret_key: Secret key for signing
            algorithm: Hash algorithm
            
        Returns:
            Hexadecimal signature
        """
        try:
            if algorithm == 'sha256':
                digestmod = hashlib.sha256
            elif algorithm == 'sha1':
                digestmod = hashlib.sha1
            elif algorithm == 'md5':
                digestmod = hashlib.md5
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            signature = hmac.new(
                secret_key.encode(),
                payload.encode(),
                digestmod
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logger.error("Failed to generate webhook signature: %s", e, exc_info=True)
            raise
    
    @staticmethod
    def verify_signature(payload: str, signature: str, secret_key: str, 
                        algorithm: str = 'sha256') -> bool:
        """
        Verify webhook signature.
        
        Args:
            payload: Original payload
            signature: Received signature
            secret_key: Secret key
            algorithm: Hash algorithm
            
        Returns:
            True if signature is valid
        """
        try:
            expected_signature = WebhookSignature.generate_signature(
                payload, secret_key, algorithm
            )
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error("Failed to verify webhook signature: %s", e, exc_info=True)
            return False


class WebhookDelivery:
    """Handles webhook delivery with retry logic."""
    
    def __init__(self, timeout: int = 30, retry_attempts: int = 3,
                 retry_delay: float = 1.0, backoff_factor: float = 2.0):
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        
        # Configure session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=retry_attempts,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def deliver(self, webhook_event: WebhookEvent) -> Dict[str, Any]:
        """
        Deliver webhook event.
        
        Args:
            webhook_event: Webhook event to deliver
            
        Returns:
            Delivery result
        """
        try:
            # Prepare payload
            payload = self._prepare_payload(webhook_event)
            
            # Generate signature if secret key is provided
            signature = None
            if webhook_event.secret_key:
                signature = WebhookSignature.generate_signature(
                    payload, webhook_event.secret_key
                )
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'RateLimit-Webhooks/1.0',
                'X-Webhook-Event': webhook_event.event_type,
                'X-Webhook-ID': webhook_event.event_id,
                'X-Webhook-Timestamp': webhook_event.created_at.isoformat()
            }
            
            # Add custom headers
            headers.update(webhook_event.headers)
            
            # Add signature header
            if signature:
                headers['X-Webhook-Signature'] = f"sha256={signature}"
            
            # Make request
            response = self.session.post(
                webhook_event.webhook_url,
                data=payload,
                headers=headers,
                timeout=webhook_event.timeout
            )
            
            # Update webhook event
            webhook_event.response_status = response.status_code
            webhook_event.response_body = response.text
            webhook_event.delivery_attempts += 1
            
            if response.status_code >= 200 and response.status_code < 300:
                webhook_event.status = 'delivered'
                webhook_event.delivered_at = timezone.now()
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds(),
                    'attempts': webhook_event.delivery_attempts
                }
            else:
                webhook_event.status = 'failed'
                webhook_event.error_message = f"HTTP {response.status_code}: {response.text}"
                
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': webhook_event.error_message,
                    'attempts': webhook_event.delivery_attempts
                }
                
        except requests.exceptions.Timeout:
            webhook_event.status = 'failed'
            webhook_event.error_message = 'Request timeout'
            webhook_event.delivery_attempts += 1
            
            return {
                'success': False,
                'error': 'Request timeout',
                'attempts': webhook_event.delivery_attempts
            }
            
        except requests.exceptions.ConnectionError:
            webhook_event.status = 'failed'
            webhook_event.error_message = 'Connection error'
            webhook_event.delivery_attempts += 1
            
            return {
                'success': False,
                'error': 'Connection error',
                'attempts': webhook_event.delivery_attempts
            }
            
        except Exception as e:
            webhook_event.status = 'failed'
            webhook_event.error_message = str(e)
            webhook_event.delivery_attempts += 1
            
            return {
                'success': False,
                'error': str(e),
                'attempts': webhook_event.delivery_attempts
            }
    
    def _prepare_payload(self, webhook_event: WebhookEvent) -> str:
        """Prepare webhook payload."""
        payload = {
            'event_id': webhook_event.event_id,
            'event_type': webhook_event.event_type,
            'timestamp': webhook_event.created_at.isoformat(),
            'data': webhook_event.data
        }
        
        return json.dumps(payload, cls=CustomJSONEncoder)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for webhook payloads."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


class WebhookManager:
    """
    Manager for webhook operations.
    """
    
    def __init__(self):
        self.webhooks: Dict[str, Dict[str, Any]] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.delivery_service = WebhookDelivery()
        self.delivery_queue: List[WebhookEvent] = []
        self.max_queue_size = 1000
        self._load_default_webhooks()
    
    def _load_default_webhooks(self):
        """Load default webhook configurations."""
        # Default analytics webhook
        self.register_webhook(
            webhook_id='analytics',
            url=getattr(settings, 'RATE_LIMIT_ANALYTICS_WEBHOOK_URL', ''),
            secret_key=getattr(settings, 'RATE_LIMIT_ANALYTICS_WEBHOOK_SECRET', ''),
            events=[IntegrationEvent.RATE_LIMIT_EXCEEDED, IntegrationEvent.ABUSE_DETECTED],
            enabled=True
        )
        
        # Default security webhook
        self.register_webhook(
            webhook_id='security',
            url=getattr(settings, 'RATE_LIMIT_SECURITY_WEBHOOK_URL', ''),
            secret_key=getattr(settings, 'RATE_LIMIT_SECURITY_WEBHOOK_SECRET', ''),
            events=[IntegrationEvent.ABUSE_DETECTED, IntegrationEvent.IP_BLOCKED],
            enabled=True
        )
        
        # Default notification webhook
        self.register_webhook(
            webhook_id='notifications',
            url=getattr(settings, 'RATE_LIMIT_NOTIFICATION_WEBHOOK_URL', ''),
            secret_key=getattr(settings, 'RATE_LIMIT_NOTIFICATION_WEBHOOK_SECRET', ''),
            events=[IntegrationEvent.RATE_LIMIT_EXCEEDED, IntegrationEvent.SYSTEM_ALERT],
            enabled=True
        )
    
    def register_webhook(self, webhook_id: str, url: str, secret_key: str = '',
                        events: List[str] = None, enabled: bool = True,
                        headers: Dict[str, Any] = None, timeout: int = 30,
                        retry_attempts: int = 3):
        """
        Register a webhook.
        
        Args:
            webhook_id: Webhook identifier
            url: Webhook URL
            secret_key: Secret key for signing
            events: Events to subscribe to
            enabled: Whether webhook is enabled
            headers: Custom headers
            timeout: Request timeout
            retry_attempts: Number of retry attempts
        """
        webhook_config = {
            'webhook_id': webhook_id,
            'url': url,
            'secret_key': secret_key,
            'events': events or [],
            'enabled': enabled,
            'headers': headers or {},
            'timeout': timeout,
            'retry_attempts': retry_attempts,
            'created_at': timezone.now(),
            'delivery_count': 0,
            'success_count': 0,
            'failure_count': 0
        }
        
        self.webhooks[webhook_id] = webhook_config
        logger.info("Registered webhook: %s", webhook_id)
    
    def unregister_webhook(self, webhook_id: str):
        """
        Unregister a webhook.
        
        Args:
            webhook_id: Webhook identifier
        """
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info("Unregistered webhook: %s", webhook_id)
    
    def update_webhook(self, webhook_id: str, **kwargs):
        """
        Update webhook configuration.
        
        Args:
            webhook_id: Webhook identifier
            **kwargs: Fields to update
        """
        if webhook_id not in self.webhooks:
            raise ValueError(f"Webhook not found: {webhook_id}")
        
        webhook_config = self.webhooks[webhook_id]
        
        for field, value in kwargs.items():
            if field in webhook_config:
                webhook_config[field] = value
        
        logger.info("Updated webhook: %s", webhook_id)
    
    def enable_webhook(self, webhook_id: str):
        """Enable a webhook."""
        self.update_webhook(webhook_id, enabled=True)
    
    def disable_webhook(self, webhook_id: str):
        """Disable a webhook."""
        self.update_webhook(webhook_id, enabled=False)
    
    def trigger_event(self, event_type: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Trigger a webhook event.
        
        Args:
            event_type: Event type
            data: Event data
            
        Returns:
            Trigger result
        """
        try:
            event_data = data or {}
            
            # Find webhooks that handle this event
            target_webhooks = []
            
            for webhook_id, webhook_config in self.webhooks.items():
                if (webhook_config['enabled'] and 
                    webhook_config['url'] and
                    (not webhook_config['events'] or event_type in webhook_config['events'])):
                    target_webhooks.append(webhook_config)
            
            if not target_webhooks:
                return {
                    'success': True,
                    'message': 'No webhooks configured for this event',
                    'webhook_count': 0
                }
            
            # Create webhook events
            webhook_events = []
            
            for webhook_config in target_webhooks:
                webhook_event = WebhookEvent(
                    event_type=event_type,
                    data=event_data,
                    webhook_url=webhook_config['url'],
                    secret_key=webhook_config['secret_key'],
                    headers=webhook_config['headers'],
                    timeout=webhook_config['timeout'],
                    retry_attempts=webhook_config['retry_attempts']
                )
                
                webhook_events.append(webhook_event)
            
            # Add to delivery queue
            self.delivery_queue.extend(webhook_events)
            
            # Maintain queue size
            if len(self.delivery_queue) > self.max_queue_size:
                self.delivery_queue = self.delivery_queue[-self.max_queue_size:]
            
            # Process delivery queue
            results = self._process_delivery_queue()
            
            return {
                'success': True,
                'webhook_count': len(target_webhooks),
                'delivery_results': results
            }
            
        except Exception as e:
            logger.error("Failed to trigger webhook event: %s", e, exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _process_delivery_queue(self) -> List[Dict[str, Any]]:
        """Process webhook delivery queue."""
        results = []
        
        # Process events in queue
        for webhook_event in self.delivery_queue:
            if webhook_event.status == 'pending':
                result = self.delivery_service.deliver(webhook_event)
                
                # Update webhook statistics
                webhook_id = self._get_webhook_id_by_url(webhook_event.webhook_url)
                if webhook_id:
                    webhook_config = self.webhooks[webhook_id]
                    webhook_config['delivery_count'] += 1
                    
                    if result['success']:
                        webhook_config['success_count'] += 1
                    else:
                        webhook_config['failure_count'] += 1
                
                results.append({
                    'webhook_id': webhook_id,
                    'event_id': webhook_event.event_id,
                    'event_type': webhook_event.event_type,
                    'result': result
                })
        
        # Remove delivered events from queue
        self.delivery_queue = [
            event for event in self.delivery_queue
            if event.status == 'pending' or event.status == 'failed'
        ]
        
        return results
    
    def _get_webhook_id_by_url(self, url: str) -> Optional[str]:
        """Get webhook ID by URL."""
        for webhook_id, webhook_config in self.webhooks.items():
            if webhook_config['url'] == url:
                return webhook_id
        return None
    
    def get_webhook_statistics(self, webhook_id: str = None) -> Dict[str, Any]:
        """Get webhook delivery statistics."""
        if webhook_id:
            if webhook_id not in self.webhooks:
                raise ValueError(f"Webhook not found: {webhook_id}")
            
            webhook_config = self.webhooks[webhook_id]
            total_deliveries = webhook_config['delivery_count']
            success_rate = (
                webhook_config['success_count'] / max(total_deliveries, 1)
            ) * 100
            
            return {
                'webhook_id': webhook_id,
                'url': webhook_config['url'],
                'enabled': webhook_config['enabled'],
                'events': webhook_config['events'],
                'total_deliveries': total_deliveries,
                'success_count': webhook_config['success_count'],
                'failure_count': webhook_config['failure_count'],
                'success_rate': success_rate,
                'created_at': webhook_config['created_at'].isoformat()
            }
        else:
            # Return statistics for all webhooks
            all_stats = {}
            
            for webhook_id in self.webhooks:
                all_stats[webhook_id] = self.get_webhook_statistics(webhook_id)
            
            return all_stats
    
    def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Test a webhook delivery.
        
        Args:
            webhook_id: Webhook identifier
            
        Returns:
            Test result
        """
        try:
            if webhook_id not in self.webhooks:
                raise ValueError(f"Webhook not found: {webhook_id}")
            
            webhook_config = self.webhooks[webhook_id]
            
            if not webhook_config['url']:
                return {
                    'success': False,
                    'error': 'Webhook URL not configured'
                }
            
            # Create test event
            test_event = WebhookEvent(
                event_type='webhook_test',
                data={
                    'test': True,
                    'timestamp': timezone.now().isoformat(),
                    'webhook_id': webhook_id
                },
                webhook_url=webhook_config['url'],
                secret_key=webhook_config['secret_key'],
                headers=webhook_config['headers'],
                timeout=webhook_config['timeout'],
                retry_attempts=1  # Only one attempt for test
            )
            
            # Deliver test event
            result = self.delivery_service.deliver(test_event)
            
            return {
                'success': result['success'],
                'webhook_id': webhook_id,
                'test_result': result,
                'test_event_id': test_event.event_id
            }
            
        except Exception as e:
            logger.error("Failed to test webhook %s: %s", webhook_id, e, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'webhook_id': webhook_id
            }
    
    def retry_failed_deliveries(self) -> Dict[str, Any]:
        """Retry failed webhook deliveries."""
        try:
            retry_count = 0
            success_count = 0
            
            # Get failed events
            failed_events = [
                event for event in self.delivery_queue
                if event.status == 'failed' and event.delivery_attempts < event.retry_attempts
            ]
            
            for event in failed_events:
                # Reset status for retry
                event.status = 'pending'
                event.error_message = None
                retry_count += 1
            
            # Process queue
            results = self._process_delivery_queue()
            
            # Count successful retries
            for result in results:
                if result['result']['success']:
                    success_count += 1
            
            return {
                'success': True,
                'retry_count': retry_count,
                'success_count': success_count,
                'failed_count': retry_count - success_count
            }
            
        except Exception as e:
            logger.error("Failed to retry webhook deliveries: %s", e, exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_delivery_queue_status(self) -> Dict[str, Any]:
        """Get delivery queue status."""
        pending_count = len([
            event for event in self.delivery_queue
            if event.status == 'pending'
        ])
        
        failed_count = len([
            event for event in self.delivery_queue
            if event.status == 'failed'
        ])
        
        return {
            'queue_size': len(self.delivery_queue),
            'max_queue_size': self.max_queue_size,
            'pending_deliveries': pending_count,
            'failed_deliveries': failed_count,
            'oldest_event': min(self.delivery_queue, key=lambda e: e.created_at).created_at.isoformat() if self.delivery_queue else None,
            'newest_event': max(self.delivery_queue, key=lambda e: e.created_at).created_at.isoformat() if self.delivery_queue else None
        }


# Global webhook manager instance
webhook_manager = WebhookManager()


# Export classes and functions
__all__ = [
    'WebhookEvent',
    'WebhookSignature',
    'WebhookDelivery',
    'CustomJSONEncoder',
    'WebhookManager',
    'webhook_manager'
]
