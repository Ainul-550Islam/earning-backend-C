# =============================================================================
# INTEGRATION_SYSTEM/webhooks_integration.py
# =============================================================================
"""
Webhook Integration System.

Provides comprehensive webhook functionality for receiving and sending
webhook events with signature validation, retry logic, and event processing.
"""

from __future__ import annotations

import logging
import asyncio
import json
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest, HttpResponse

from .integ_constants import Priority, IntegrationStatus
from .integ_exceptions import (
    WebhookError, WebhookDeliveryError, WebhookValidationError,
    IntegrationConnectionError, IntegrationTimeoutError
)
from .integ_signals import IntegrationSignalManager, SignalType

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Webhook event types."""
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    TRANSACTION_CREATED = "transaction.created"
    TRANSACTION_UPDATED = "transaction.updated"
    TRANSACTION_COMPLETED = "transaction.completed"
    FRAUD_DETECTED = "fraud.detected"
    FRAUD_REVIEWED = "fraud.reviewed"
    SYSTEM_ALERT = "system.alert"
    CUSTOM = "custom"


class WebhookStatus(Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class WebhookEvent:
    """Webhook event structure."""
    event_id: str
    event_type: WebhookEventType
    source: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'source': self.source,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    webhook_id: str
    name: str
    url: str
    secret: str
    events: List[WebhookEventType]
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    signature_algorithm: str = "sha256"
    signature_header: str = "X-Webhook-Signature"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)


@dataclass
class WebhookDelivery:
    """Webhook delivery tracking."""
    delivery_id: str
    webhook_id: str
    event: WebhookEvent
    status: WebhookStatus = WebhookStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    last_attempt: Optional[datetime] = None
    next_retry: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=timezone.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'delivery_id': self.delivery_id,
            'webhook_id': self.webhook_id,
            'event_id': self.event.event_id,
            'event_type': self.event.event_type.value,
            'status': self.status.value,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'next_retry': self.next_retry.isoformat() if self.next_retry else None,
            'response_status': self.response_status,
            'response_body': self.response_body,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'metadata': self.metadata
        }


class WebhookEventHandler(ABC):
    """
    Abstract base class for webhook event handlers.
    """
    
    @abstractmethod
    async def handle_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Handle webhook event."""
        pass
    
    @abstractmethod
    def get_supported_events(self) -> List[WebhookEventType]:
        """Get list of supported event types."""
        pass


class WebhookProcessor:
    """
    Webhook event processor.
    
    Handles incoming webhook events, validates signatures,
    and processes events through registered handlers.
    """
    
    def __init__(self):
        """Initialize webhook processor."""
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_handlers: Dict[WebhookEventType, List[WebhookEventHandler]] = defaultdict(list)
        self.deliveries: Dict[str, WebhookDelivery] = {}
        
        # Configuration
        self.enable_signature_validation = getattr(settings, 'WEBHOOK_ENABLE_SIGNATURE_VALIDATION', True)
        self.default_timeout = getattr(settings, 'WEBHOOK_DEFAULT_TIMEOUT', 30)
        self.max_event_size = getattr(settings, 'WEBHOOK_MAX_EVENT_SIZE', 1024 * 1024)  # 1MB
        
        # Statistics
        self.events_received = 0
        self.events_processed = 0
        self.events_failed = 0
        self.webhooks_delivered = 0
        self.webhooks_failed = 0
        
        logger.info("WebhookProcessor initialized")
    
    def register_webhook(self, config: WebhookConfig) -> None:
        """Register webhook configuration."""
        self.webhooks[config.webhook_id] = config
        logger.info(f"Registered webhook: {config.name}")
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister webhook."""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info(f"Unregistered webhook: {webhook_id}")
            return True
        return False
    
    def register_event_handler(self, event_type: WebhookEventType, handler: WebhookEventHandler) -> None:
        """Register event handler."""
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered event handler for {event_type.value}")
    
    async def process_incoming_webhook(self, request: HttpRequest) -> HttpResponse:
        """
        Process incoming webhook request.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Parse request body
            body = request.body
            if len(body) > self.max_event_size:
                return HttpResponse("Event too large", status=413)
            
            try:
                event_data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                return HttpResponse("Invalid JSON", status=400)
            
            # Validate event structure
            event = self._parse_incoming_event(event_data, request)
            if not event:
                return HttpResponse("Invalid event structure", status=400)
            
            self.events_received += 1
            
            # Find matching webhooks
            matching_webhooks = [
                webhook for webhook in self.webhooks.values()
                if webhook.enabled and event.event_type in webhook.events
            ]
            
            if not matching_webhooks:
                logger.warning(f"No webhooks configured for event: {event.event_type.value}")
                return HttpResponse("No matching webhooks", status=200)
            
            # Process event through handlers
            handler_results = []
            for handler in self.event_handlers[event.event_type]:
                try:
                    result = await handler.handle_event(event)
                    handler_results.append(result)
                except Exception as e:
                    logger.error(f"Event handler failed: {e}")
            
            # Queue webhook deliveries
            for webhook in matching_webhooks:
                delivery = self._create_webhook_delivery(webhook.webhook_id, event)
                self.deliveries[delivery.delivery_id] = delivery
                asyncio.create_task(self._deliver_webhook(delivery))
            
            self.events_processed += 1
            
            return HttpResponse("Event processed", status=200)
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            self.events_failed += 1
            return HttpResponse("Internal server error", status=500)
    
    def _parse_incoming_event(self, event_data: Dict[str, Any], request: HttpRequest) -> Optional[WebhookEvent]:
        """Parse incoming event data."""
        try:
            # Validate required fields
            required_fields = ['event_id', 'event_type', 'source', 'data']
            for field in required_fields:
                if field not in event_data:
                    return None
            
            # Create event object
            event = WebhookEvent(
                event_id=event_data['event_id'],
                event_type=WebhookEventType(event_data['event_type']),
                source=event_data['source'],
                data=event_data['data'],
                metadata=event_data.get('metadata', {})
            )
            
            # Validate signature if enabled
            if self.enable_signature_validation:
                if not self._validate_webhook_signature(request, event):
                    return None
            
            return event
            
        except (ValueError, KeyError):
            return None
    
    def _validate_webhook_signature(self, request: HttpRequest, event: WebhookEvent) -> bool:
        """Validate webhook signature."""
        # Get signature from header
        signature_header = getattr(settings, 'WEBHOOK_SIGNATURE_HEADER', 'X-Webhook-Signature')
        signature = request.META.get(signature_header)
        
        if not signature:
            logger.warning("Missing webhook signature")
            return False
        
        # Find webhook configuration
        webhook = None
        for config in self.webhooks.values():
            if config.url == request.build_absolute_uri():
                webhook = config
                break
        
        if not webhook:
            logger.warning("No webhook configuration found for URL")
            return False
        
        # Calculate expected signature
        payload = json.dumps(event.to_dict(), sort_keys=True).encode()
        expected_signature = hmac.new(
            webhook.secret.encode(),
            payload,
            getattr(hashlib, webhook.signature_algorithm)
        ).hexdigest()
        
        # Compare signatures
        if not hmac.compare_digest(signature, f"{webhook.signature_algorithm}={expected_signature}"):
            logger.warning("Invalid webhook signature")
            return False
        
        return True
    
    def _create_webhook_delivery(self, webhook_id: str, event: WebhookEvent) -> WebhookDelivery:
        """Create webhook delivery record."""
        import uuid
        
        webhook = self.webhooks[webhook_id]
        
        return WebhookDelivery(
            delivery_id=str(uuid.uuid4()),
            webhook_id=webhook_id,
            event=event,
            max_attempts=webhook.retry_attempts,
            next_retry=timezone.now()
        )
    
    async def _deliver_webhook(self, delivery: WebhookDelivery) -> None:
        """Deliver webhook to endpoint."""
        webhook = self.webhooks[delivery.webhook_id]
        
        while delivery.attempts < delivery.max_attempts and delivery.status == WebhookStatus.PENDING:
            # Check if it's time to retry
            if delivery.next_retry and timezone.now() < delivery.next_retry:
                await asyncio.sleep((delivery.next_retry - timezone.now()).total_seconds())
            
            delivery.attempts += 1
            delivery.last_attempt = timezone.now()
            delivery.status = WebhookStatus.RETRYING
            
            try:
                # Prepare webhook payload
                payload = {
                    'event': delivery.event.to_dict(),
                    'webhook_id': delivery.webhook_id,
                    'delivery_id': delivery.delivery_id,
                    'timestamp': timezone.now().isoformat()
                }
                
                # Prepare headers
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'Integration-System-Webhook/1.0',
                    **webhook.headers
                }
                
                # Add signature
                signature = self._generate_signature(webhook, payload)
                headers[webhook.signature_header] = signature
                
                # Send webhook
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        webhook.url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=webhook.timeout)
                    ) as response:
                        delivery.response_status = response.status
                        delivery.response_body = await response.text()
                        
                        if 200 <= response.status < 300:
                            delivery.status = WebhookStatus.DELIVERED
                            delivery.completed_at = timezone.now()
                            self.webhooks_delivered += 1
                            logger.info(f"Webhook delivered: {delivery.delivery_id}")
                            return
                        else:
                            delivery.error_message = f"HTTP {response.status}: {delivery.response_body}"
                            
            except asyncio.TimeoutError:
                delivery.error_message = "Request timeout"
                delivery.status = WebhookStatus.TIMEOUT
                
            except Exception as e:
                delivery.error_message = str(e)
                delivery.status = WebhookStatus.FAILED
            
            # Schedule retry if needed
            if delivery.attempts < delivery.max_attempts:
                delivery.next_retry = timezone.now() + timedelta(seconds=webhook.retry_delay * (2 ** (delivery.attempts - 1)))
                delivery.status = WebhookStatus.PENDING
            else:
                delivery.status = WebhookStatus.FAILED
                delivery.completed_at = timezone.now()
                self.webhooks_failed += 1
                logger.error(f"Webhook delivery failed: {delivery.delivery_id}")
    
    def _generate_signature(self, webhook: WebhookConfig, payload: Dict[str, Any]) -> str:
        """Generate webhook signature."""
        payload_str = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            webhook.secret.encode(),
            payload_str,
            getattr(hashlib, webhook.signature_algorithm)
        ).hexdigest()
        
        return f"{webhook.signature_algorithm}={signature}"
    
    async def send_webhook_event(self, event_type: WebhookEventType, data: Dict[str, Any],
                                source: str = "integration_system") -> List[WebhookDelivery]:
        """
        Send webhook event to configured endpoints.
        
        Args:
            event_type: Event type
            data: Event data
            source: Event source
            
        Returns:
            List of webhook deliveries
        """
        import uuid
        
        # Create event
        event = WebhookEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            data=data
        )
        
        # Find matching webhooks
        matching_webhooks = [
            webhook for webhook in self.webhooks.values()
            if webhook.enabled and event_type in webhook.events
        ]
        
        if not matching_webhooks:
            logger.warning(f"No webhooks configured for event: {event_type.value}")
            return []
        
        # Create deliveries
        deliveries = []
        for webhook in matching_webhooks:
            delivery = self._create_webhook_delivery(webhook.webhook_id, event)
            self.deliveries[delivery.delivery_id] = delivery
            deliveries.append(delivery)
            
            # Start delivery
            asyncio.create_task(self._deliver_webhook(delivery))
        
        return deliveries
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get webhook configuration."""
        return self.webhooks.get(webhook_id)
    
    def list_webhooks(self, enabled_only: bool = False) -> List[WebhookConfig]:
        """List webhook configurations."""
        webhooks = list(self.webhooks.values())
        
        if enabled_only:
            webhooks = [w for w in webhooks if w.enabled]
        
        return webhooks
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get webhook delivery."""
        return self.deliveries.get(delivery_id)
    
    def list_deliveries(self, webhook_id: Optional[str] = None, 
                       status: Optional[WebhookStatus] = None,
                       limit: int = 100) -> List[WebhookDelivery]:
        """List webhook deliveries."""
        deliveries = list(self.deliveries.values())
        
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        # Sort by creation time (newest first)
        deliveries.sort(key=lambda d: d.created_at, reverse=True)
        
        return deliveries[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get webhook statistics."""
        # Status distribution
        status_counts = defaultdict(int)
        for delivery in self.deliveries.values():
            status_counts[delivery.status.value] += 1
        
        # Event type distribution
        event_counts = defaultdict(int)
        for delivery in self.deliveries.values():
            event_counts[delivery.event.event_type.value] += 1
        
        return {
            'events_received': self.events_received,
            'events_processed': self.events_processed,
            'events_failed': self.events_failed,
            'webhooks_delivered': self.webhooks_delivered,
            'webhooks_failed': self.webhooks_failed,
            'total_webhooks': len(self.webhooks),
            'enabled_webhooks': len([w for w in self.webhooks.values() if w.enabled]),
            'total_deliveries': len(self.deliveries),
            'delivery_status_distribution': dict(status_counts),
            'event_type_distribution': dict(event_counts),
            'success_rate': (self.webhooks_delivered / max(self.webhooks_delivered + self.webhooks_failed, 1)) * 100
        }
    
    def enable_webhook(self, webhook_id: str) -> bool:
        """Enable webhook."""
        webhook = self.webhooks.get(webhook_id)
        if webhook:
            webhook.enabled = True
            webhook.updated_at = timezone.now()
            logger.info(f"Enabled webhook: {webhook_id}")
            return True
        return False
    
    def disable_webhook(self, webhook_id: str) -> bool:
        """Disable webhook."""
        webhook = self.webhooks.get(webhook_id)
        if webhook:
            webhook.enabled = False
            webhook.updated_at = timezone.now()
            logger.info(f"Disabled webhook: {webhook_id}")
            return True
        return False
    
    def retry_delivery(self, delivery_id: str) -> bool:
        """Retry webhook delivery."""
        delivery = self.deliveries.get(delivery_id)
        if delivery and delivery.status in [WebhookStatus.FAILED, WebhookStatus.TIMEOUT]:
            delivery.status = WebhookStatus.PENDING
            delivery.attempts = 0
            delivery.next_retry = timezone.now()
            delivery.error_message = None
            delivery.response_status = None
            delivery.response_body = None
            
            # Start retry
            asyncio.create_task(self._deliver_webhook(delivery))
            
            logger.info(f"Retrying webhook delivery: {delivery_id}")
            return True
        
        return False
    
    def cancel_delivery(self, delivery_id: str) -> bool:
        """Cancel webhook delivery."""
        delivery = self.deliveries.get(delivery_id)
        if delivery and delivery.status in [WebhookStatus.PENDING, WebhookStatus.RETRYING]:
            delivery.status = WebhookStatus.CANCELLED
            delivery.completed_at = timezone.now()
            
            logger.info(f"Cancelled webhook delivery: {delivery_id}")
            return True
        
        return False
    
    def cleanup_old_deliveries(self, days: int = 30) -> int:
        """Clean up old webhook deliveries."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_deliveries = [
            delivery_id for delivery_id, delivery in self.deliveries.items()
            if delivery.created_at < cutoff_date
        ]
        
        for delivery_id in old_deliveries:
            del self.deliveries[delivery_id]
        
        logger.info(f"Cleaned up {len(old_deliveries)} old webhook deliveries")
        return len(old_deliveries)


# Global webhook processor instance
_webhook_processor = None


def get_webhook_processor() -> WebhookProcessor:
    """Get global webhook processor instance."""
    global _webhook_processor
    if _webhook_processor is None:
        _webhook_processor = WebhookProcessor()
    return _webhook_processor


# Convenience functions
async def send_webhook(event_type: WebhookEventType, data: Dict[str, Any],
                      source: str = "integration_system") -> List[WebhookDelivery]:
    """
    Convenience function for sending webhook events.
    
    Args:
        event_type: Event type
        data: Event data
        source: Event source
        
    Returns:
        List of webhook deliveries
    """
    processor = get_webhook_processor()
    return await processor.send_webhook_event(event_type, data, source)


def register_webhook(name: str, url: str, secret: str, events: List[WebhookEventType],
                   **kwargs) -> WebhookConfig:
    """
    Convenience function for registering webhooks.
    
    Args:
        name: Webhook name
        url: Webhook URL
        secret: Webhook secret
        events: List of event types
        **kwargs: Additional configuration
        
    Returns:
        Webhook configuration
    """
    import uuid
    
    config = WebhookConfig(
        webhook_id=str(uuid.uuid4()),
        name=name,
        url=url,
        secret=secret,
        events=events,
        **kwargs
    )
    
    processor = get_webhook_processor()
    processor.register_webhook(config)
    
    return config


def get_webhook_statistics() -> Dict[str, Any]:
    """
    Convenience function for getting webhook statistics.
    
    Returns:
        Webhook statistics
    """
    processor = get_webhook_processor()
    return processor.get_statistics()


# Built-in event handlers
class UserEventHandler(WebhookEventHandler):
    """User event handler."""
    
    async def handle_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Handle user events."""
        logger.info(f"Processing user event: {event.event_type.value}")
        
        # Process user event logic here
        # For now, just return success
        return {
            'status': 'success',
            'event_id': event.event_id,
            'processed_at': timezone.now().isoformat()
        }
    
    def get_supported_events(self) -> List[WebhookEventType]:
        """Get supported event types."""
        return [
            WebhookEventType.USER_CREATED,
            WebhookEventType.USER_UPDATED,
            WebhookEventType.USER_DELETED
        ]


class TransactionEventHandler(WebhookEventHandler):
    """Transaction event handler."""
    
    async def handle_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Handle transaction events."""
        logger.info(f"Processing transaction event: {event.event_type.value}")
        
        # Process transaction event logic here
        return {
            'status': 'success',
            'event_id': event.event_id,
            'processed_at': timezone.now().isoformat()
        }
    
    def get_supported_events(self) -> List[WebhookEventType]:
        """Get supported event types."""
        return [
            WebhookEventType.TRANSACTION_CREATED,
            WebhookEventType.TRANSACTION_UPDATED,
            WebhookEventType.TRANSACTION_COMPLETED
        ]


class FraudEventHandler(WebhookEventHandler):
    """Fraud event handler."""
    
    async def handle_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Handle fraud events."""
        logger.warning(f"Processing fraud event: {event.event_type.value}")
        
        # Process fraud event logic here
        return {
            'status': 'success',
            'event_id': event.event_id,
            'processed_at': timezone.now().isoformat(),
            'priority': 'high'
        }
    
    def get_supported_events(self) -> List[WebhookEventType]:
        """Get supported event types."""
        return [
            WebhookEventType.FRAUD_DETECTED,
            WebhookEventType.FRAUD_REVIEWED
        ]


# Initialize built-in handlers
def initialize_builtin_handlers():
    """Initialize built-in event handlers."""
    processor = get_webhook_processor()
    
    user_handler = UserEventHandler()
    transaction_handler = TransactionEventHandler()
    fraud_handler = FraudEventHandler()
    
    for event_type in user_handler.get_supported_events():
        processor.register_event_handler(event_type, user_handler)
    
    for event_type in transaction_handler.get_supported_events():
        processor.register_event_handler(event_type, transaction_handler)
    
    for event_type in fraud_handler.get_supported_events():
        processor.register_event_handler(event_type, fraud_handler)
