"""
webhooks_integration.py – Webhooks integration for postback module.

Provides comprehensive webhook functionality including:
- Webhook sending and receiving
- Webhook signature validation
- Webhook retry logic
- Webhook event management
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import requests
import threading
import queue

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from api.postback.INTEGRATION_SYSTEM.integ_constants import IntegrationStatus, IntegrationProtocol
from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException
from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS.event_bus import publish_event, subscribe_to_events

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    """Webhook status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"


class WebhookEventType(Enum):
    """Webhook event type enumeration."""
    POSTBACK_RECEIVED = "postback_received"
    POSTBACK_PROCESSED = "postback_processed"
    POSTBACK_FAILED = "postback_failed"
    USER_REGISTERED = "user_registered"
    USER_UPDATED = "user_updated"
    PAYMENT_RECEIVED = "payment_received"
    SYSTEM_ALERT = "system_alert"
    CUSTOM = "custom"


@dataclass
class Webhook:
    """Webhook data structure."""
    id: str
    url: str
    event_type: WebhookEventType
    secret: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 60
    status: WebhookStatus = WebhookStatus.ACTIVE
    created_at: datetime = field(default_factory=timezone.now)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'url': self.url,
            'event_type': self.event_type.value,
            'headers': self.headers,
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts,
            'retry_delay': self.retry_delay,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'trigger_count': self.trigger_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'last_error': self.last_error,
            'metadata': self.metadata,
        }


@dataclass
class WebhookEvent:
    """Webhook event data structure."""
    id: str
    webhook_id: str
    event_type: WebhookEventType
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=timezone.now)
    attempt_count: int = 0
    status: str = "pending"
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'webhook_id': self.webhook_id,
            'event_type': self.event_type.value,
            'payload': self.payload,
            'timestamp': self.timestamp.isoformat(),
            'attempt_count': self.attempt_count,
            'status': self.status,
            'response_status': self.response_status,
            'response_body': self.response_body,
            'error_message': self.error_message,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None,
        }


class WebhookSignatureValidator:
    """
    Validator for webhook signatures.
    
    Handles signature generation and validation
    for webhook security.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def generate_signature(self, payload: Dict[str, Any], secret: str, 
                         algorithm: str = 'sha256') -> str:
        """
        Generate webhook signature.
        
        Args:
            payload: Webhook payload
            secret: Webhook secret
            algorithm: Hash algorithm
            
        Returns:
            Generated signature
        """
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        if algorithm == 'sha256':
            return hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
        elif algorithm == 'sha1':
            return hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha1
            ).hexdigest()
        elif algorithm == 'md5':
            return hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.md5
            ).hexdigest()
        else:
            raise IntegrationException(f"Unsupported algorithm: {algorithm}")
    
    def validate_signature(self, payload: Dict[str, Any], secret: str,
                          received_signature: str, algorithm: str = 'sha256') -> bool:
        """
        Validate webhook signature.
        
        Args:
            payload: Webhook payload
            secret: Webhook secret
            received_signature: Received signature
            algorithm: Hash algorithm
            
        Returns:
            True if signature is valid
        """
        try:
            expected_signature = self.generate_signature(payload, secret, algorithm)
            return hmac.compare_digest(expected_signature, received_signature)
        except Exception as e:
            self.logger.error(f"Error validating signature: {str(e)}")
            return False
    
    def extract_signature_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extract signature from headers.
        
        Args:
            headers: HTTP headers
            
        Returns:
            Signature or None
        """
        # Common signature header names
        signature_headers = [
            'X-Webhook-Signature',
            'X-Hub-Signature',
            'X-Signature',
            'Webhook-Signature',
            'Signature',
        ]
        
        for header in signature_headers:
            if header in headers:
                signature = headers[header]
                # Remove algorithm prefix if present (e.g., "sha256=")
                if '=' in signature:
                    signature = signature.split('=', 1)[1]
                return signature
        
        return None


class WebhookSender:
    """
    Webhook sender implementation.
    
    Handles webhook delivery with retry logic
    and error handling.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.signature_validator = WebhookSignatureValidator()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PostbackWebhook/1.0',
            'Content-Type': 'application/json',
        })
    
    def send_webhook(self, webhook: Webhook, payload: Dict[str, Any],
                    context: Dict[str, Any] = None) -> WebhookEvent:
        """
        Send webhook.
        
        Args:
            webhook: Webhook configuration
            payload: Webhook payload
            context: Additional context
            
        Returns:
            Webhook event result
        """
        context = context or {}
        import uuid
        
        webhook_event = WebhookEvent(
            id=f"event_{uuid.uuid4().hex[:12]}",
            webhook_id=webhook.id,
            event_type=webhook.event_type,
            payload=payload
        )
        
        try:
            # Update webhook stats
            webhook.trigger_count += 1
            webhook.last_triggered = timezone.now()
            
            # Prepare request
            headers = webhook.headers.copy()
            
            # Add signature if secret is provided
            if webhook.secret:
                signature = self.signature_validator.generate_signature(
                    payload, webhook.secret
                )
                headers['X-Webhook-Signature'] = f"sha256={signature}"
            
            # Add event metadata
            payload_with_metadata = {
                'event': webhook.event_type.value,
                'timestamp': timezone.now().isoformat(),
                'webhook_id': webhook.id,
                'data': payload,
                **context.get('additional_data', {})
            }
            
            # Send webhook
            response = self.session.post(
                webhook.url,
                json=payload_with_metadata,
                headers=headers,
                timeout=webhook.timeout
            )
            
            # Update event with response
            webhook_event.response_status = response.status_code
            webhook_event.response_body = response.text
            
            # Check response
            if 200 <= response.status_code < 300:
                webhook_event.status = 'success'
                webhook.success_count += 1
                self.logger.info(f"Webhook sent successfully: {webhook.id}")
            else:
                webhook_event.status = 'failed'
                webhook.failure_count += 1
                webhook.last_error = f"HTTP {response.status_code}: {response.text}"
                
                # Schedule retry if needed
                if webhook_event.attempt_count < webhook.retry_attempts:
                    webhook_event.next_retry_at = timezone.now() + timedelta(seconds=webhook.retry_delay)
                    webhook_event.attempt_count += 1
                
                self.logger.error(f"Webhook failed: {webhook.id} - {response.status_code}")
            
            return webhook_event
        
        except requests.exceptions.Timeout:
            webhook_event.status = 'timeout'
            webhook.failure_count += 1
            webhook.last_error = "Request timeout"
            
            # Schedule retry
            if webhook_event.attempt_count < webhook.retry_attempts:
                webhook_event.next_retry_at = timezone.now() + timedelta(seconds=webhook.retry_delay)
                webhook_event.attempt_count += 1
            
            self.logger.error(f"Webhook timeout: {webhook.id}")
            return webhook_event
        
        except requests.exceptions.RequestException as e:
            webhook_event.status = 'error'
            webhook.failure_count += 1
            webhook.last_error = str(e)
            
            # Schedule retry
            if webhook_event.attempt_count < webhook.retry_attempts:
                webhook_event.next_retry_at = timezone.now() + timedelta(seconds=webhook.retry_delay)
                webhook_event.attempt_count += 1
            
            self.logger.error(f"Webhook error: {webhook.id} - {str(e)}")
            return webhook_event
        
        except Exception as e:
            webhook_event.status = 'error'
            webhook.failure_count += 1
            webhook.last_error = str(e)
            
            self.logger.error(f"Unexpected webhook error: {webhook.id} - {str(e)}")
            return webhook_event


class WebhookReceiver:
    """
    Webhook receiver implementation.
    
    Handles incoming webhook requests with
    signature validation and processing.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.signature_validator = WebhookSignatureValidator()
        self.handlers: Dict[WebhookEventType, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
    
    def register_handler(self, event_type: WebhookEventType, handler: Callable):
        """
        Register webhook handler.
        
        Args:
            event_type: Event type
            handler: Handler function
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
        self.logger.info(f"Webhook handler registered: {event_type.value}")
    
    def register_global_handler(self, handler: Callable):
        """
        Register global webhook handler.
        
        Args:
            handler: Handler function
        """
        self.global_handlers.append(handler)
        self.logger.info("Global webhook handler registered")
    
    def receive_webhook(self, event_type: str, payload: Dict[str, Any],
                        headers: Dict[str, Any] = None, secret: str = None) -> Dict[str, Any]:
        """
        Receive and process webhook.
        
        Args:
            event_type: Event type string
            payload: Webhook payload
            headers: HTTP headers
            secret: Expected secret for validation
            
        Returns:
            Processing result
        """
        headers = headers or {}
        result = {
            'success': False,
            'message': '',
            'processed_by': [],
            'errors': [],
        }
        
        try:
            # Validate event type
            try:
                webhook_event_type = WebhookEventType(event_type)
            except ValueError:
                result['errors'].append(f"Invalid event type: {event_type}")
                return result
            
            # Validate signature if secret is provided
            if secret:
                received_signature = self.signature_validator.extract_signature_from_headers(headers)
                if not received_signature:
                    result['errors'].append("Missing signature header")
                    return result
                
                if not self.signature_validator.validate_signature(
                    payload, secret, received_signature
                ):
                    result['errors'].append("Invalid signature")
                    return result
            
            # Process with global handlers
            for handler in self.global_handlers:
                try:
                    handler_result = handler(webhook_event_type, payload, headers)
                    if handler_result:
                        result['processed_by'].append('global')
                except Exception as e:
                    result['errors'].append(f"Global handler error: {str(e)}")
            
            # Process with specific handlers
            if webhook_event_type in self.handlers:
                for handler in self.handlers[webhook_event_type]:
                    try:
                        handler_result = handler(webhook_event_type, payload, headers)
                        if handler_result:
                            result['processed_by'].append(webhook_event_type.value)
                    except Exception as e:
                        result['errors'].append(f"Handler error: {str(e)}")
            
            # Check if processed successfully
            if result['processed_by']:
                result['success'] = True
                result['message'] = f"Webhook processed by: {', '.join(result['processed_by'])}"
            else:
                result['message'] = "No handlers found for event type"
            
            return result
        
        except Exception as e:
            result['errors'].append(f"Processing error: {str(e)}")
            self.logger.error(f"Error receiving webhook: {str(e)}")
            return result


class WebhookManager:
    """
    Manager for webhook operations.
    
    Handles webhook registration, sending,
    receiving, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.webhooks: Dict[str, Webhook] = {}
        self.webhook_events: Dict[str, WebhookEvent] = []
        self.sender = WebhookSender()
        self.receiver = WebhookReceiver()
        self.retry_queue = queue.Queue()
        self.retry_worker_thread = None
        self.running = False
        self._setup_event_subscriptions()
    
    def _setup_event_subscriptions(self):
        """Setup event subscriptions for automatic webhook triggering."""
        subscribe_to_events(
            subscriber="webhook_manager",
            event_type="postback_processed",
            handler=self._handle_postback_event
        )
        
        subscribe_to_events(
            subscriber="webhook_manager",
            event_type="postback_failed",
            handler=self._handle_postback_event
        )
    
    def _handle_postback_event(self, event):
        """Handle postback events."""
        try:
            # Extract event data
            event_data = event.data
            event_type = event.event_type
            
            # Convert to webhook event type
            if event_type == "postback_processed":
                webhook_event_type = WebhookEventType.POSTBACK_PROCESSED
            elif event_type == "postback_failed":
                webhook_event_type = WebhookEventType.POSTBACK_FAILED
            else:
                return
            
            # Trigger webhooks for this event type
            self.trigger_webhooks(webhook_event_type, event_data)
        
        except Exception as e:
            self.logger.error(f"Error handling postback event: {str(e)}")
    
    def register_webhook(self, url: str, event_type: WebhookEventType,
                        secret: str = None, headers: Dict[str, str] = None,
                        timeout: int = 30, retry_attempts: int = 3,
                        retry_delay: int = 60, metadata: Dict[str, Any] = None) -> str:
        """
        Register webhook.
        
        Args:
            url: Webhook URL
            event_type: Event type
            secret: Webhook secret
            headers: Additional headers
            timeout: Request timeout
            retry_attempts: Number of retry attempts
            retry_delay: Delay between retries
            metadata: Additional metadata
            
        Returns:
            Webhook ID
        """
        import uuid
        
        webhook = Webhook(
            id=f"webhook_{uuid.uuid4().hex[:12]}",
            url=url,
            event_type=event_type,
            secret=secret or '',
            headers=headers or {},
            timeout=timeout,
            retry_attempts=retry_attempts,
            retry_delay=retry_delay,
            metadata=metadata or {}
        )
        
        self.webhooks[webhook.id] = webhook
        self.logger.info(f"Webhook registered: {webhook.id} - {event_type.value}")
        
        return webhook.id
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister webhook.
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            True if unregistered
        """
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            self.logger.info(f"Webhook unregistered: {webhook_id}")
            return True
        return False
    
    def trigger_webhooks(self, event_type: WebhookEventType, payload: Dict[str, Any],
                        context: Dict[str, Any] = None) -> List[WebhookEvent]:
        """
        Trigger webhooks for event type.
        
        Args:
            event_type: Event type
            payload: Event payload
            context: Additional context
            
        Returns:
            List of webhook events
        """
        context = context or {}
        events = []
        
        # Find webhooks for this event type
        matching_webhooks = [
            webhook for webhook in self.webhooks.values()
            if webhook.event_type == event_type and webhook.status == WebhookStatus.ACTIVE
        ]
        
        # Send webhooks
        for webhook in matching_webhooks:
            try:
                event = self.sender.send_webhook(webhook, payload, context)
                events.append(event)
                self.webhook_events.append(event)
                
                # Add to retry queue if needed
                if event.status in ['failed', 'timeout'] and event.next_retry_at:
                    self.retry_queue.put(event)
            
            except Exception as e:
                self.logger.error(f"Error triggering webhook {webhook.id}: {str(e)}")
        
        return events
    
    def receive_webhook(self, event_type: str, payload: Dict[str, Any],
                        headers: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Receive webhook.
        
        Args:
            event_type: Event type string
            payload: Webhook payload
            headers: HTTP headers
            
        Returns:
            Processing result
        """
        # Find webhook by URL or event type
        webhook = None
        if 'webhook_id' in payload:
            webhook = self.webhooks.get(payload['webhook_id'])
        
        secret = webhook.secret if webhook else None
        
        return self.receiver.receive_webhook(event_type, payload, headers, secret)
    
    def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        """
        Get webhook by ID.
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            Webhook or None
        """
        return self.webhooks.get(webhook_id)
    
    def get_webhooks_by_event_type(self, event_type: WebhookEventType) -> List[Webhook]:
        """
        Get webhooks by event type.
        
        Args:
            event_type: Event type
            
        Returns:
            List of webhooks
        """
        return [
            webhook for webhook in self.webhooks.values()
            if webhook.event_type == event_type
        ]
    
    def enable_webhook(self, webhook_id: str) -> bool:
        """
        Enable webhook.
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            True if enabled
        """
        webhook = self.get_webhook(webhook_id)
        if webhook:
            webhook.status = WebhookStatus.ACTIVE
            self.logger.info(f"Webhook enabled: {webhook_id}")
            return True
        return False
    
    def disable_webhook(self, webhook_id: str) -> bool:
        """
        Disable webhook.
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            True if disabled
        """
        webhook = self.get_webhook(webhook_id)
        if webhook:
            webhook.status = WebhookStatus.DISABLED
            self.logger.info(f"Webhook disabled: {webhook_id}")
            return True
        return False
    
    def start_retry_worker(self):
        """Start retry worker thread."""
        if self.running:
            return
        
        self.running = True
        self.retry_worker_thread = threading.Thread(target=self._retry_worker_loop, daemon=True)
        self.retry_worker_thread.start()
        self.logger.info("Webhook retry worker started")
    
    def stop_retry_worker(self):
        """Stop retry worker thread."""
        if not self.running:
            return
        
        self.running = False
        if self.retry_worker_thread:
            self.retry_worker_thread.join(timeout=5)
        self.logger.info("Webhook retry worker stopped")
    
    def _retry_worker_loop(self):
        """Retry worker loop."""
        while self.running:
            try:
                # Get webhook event from queue
                try:
                    event = self.retry_queue.get(timeout=60)
                except queue.Empty:
                    continue
                
                # Check if it's time to retry
                if event.next_retry_at and timezone.now() >= event.next_retry_at:
                    webhook = self.get_webhook(event.webhook_id)
                    if webhook and webhook.status == WebhookStatus.ACTIVE:
                        # Retry webhook
                        retry_event = self.sender.send_webhook(webhook, event.payload)
                        self.webhook_events.append(retry_event)
                        
                        # Add back to queue if still failed
                        if retry_event.status in ['failed', 'timeout'] and retry_event.next_retry_at:
                            self.retry_queue.put(retry_event)
                
            except Exception as e:
                self.logger.error(f"Error in retry worker: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get webhook statistics."""
        total_webhooks = len(self.webhooks)
        active_webhooks = len([w for w in self.webhooks.values() if w.status == WebhookStatus.ACTIVE])
        
        # Event statistics
        total_events = len(self.webhook_events)
        successful_events = len([e for e in self.webhook_events if e.status == 'success'])
        failed_events = len([e for e in self.webhook_events if e.status == 'failed'])
        timeout_events = len([e for e in self.webhook_events if e.status == 'timeout'])
        
        # Webhook type distribution
        event_types = {}
        for webhook in self.webhooks.values():
            event_type = webhook.event_type.value
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        return {
            'total_webhooks': total_webhooks,
            'active_webhooks': active_webhooks,
            'total_events': total_events,
            'successful_events': successful_events,
            'failed_events': failed_events,
            'timeout_events': timeout_events,
            'success_rate': (successful_events / total_events * 100) if total_events > 0 else 0,
            'event_types': event_types,
            'retry_queue_size': self.retry_queue.qsize(),
            'retry_worker_running': self.running,
        }


# Global webhook manager instance
webhook_manager = WebhookManager()


# Convenience functions
def register_webhook(url: str, event_type: WebhookEventType, secret: str = None,
                    headers: Dict[str, str] = None, timeout: int = 30,
                    retry_attempts: int = 3, retry_delay: int = 60,
                    metadata: Dict[str, Any] = None) -> str:
    """Register webhook."""
    return webhook_manager.register_webhook(
        url, event_type, secret, headers, timeout, retry_attempts, retry_delay, metadata
    )


def trigger_webhooks(event_type: WebhookEventType, payload: Dict[str, Any],
                    context: Dict[str, Any] = None) -> List[WebhookEvent]:
    """Trigger webhooks for event."""
    return webhook_manager.trigger_webhooks(event_type, payload, context)


def receive_webhook(event_type: str, payload: Dict[str, Any],
                    headers: Dict[str, Any] = None) -> Dict[str, Any]:
    """Receive webhook."""
    return webhook_manager.receive_webhook(event_type, payload, headers)


def get_webhook_statistics() -> Dict[str, Any]:
    """Get webhook statistics."""
    return webhook_manager.get_statistics()


def start_webhook_retry_worker():
    """Start webhook retry worker."""
    webhook_manager.start_retry_worker()


def stop_webhook_retry_worker():
    """Stop webhook retry worker."""
    webhook_manager.stop_retry_worker()
