"""
Webhooks Integration — Comprehensive webhook handling system.

This module provides webhook integration capabilities for receiving,
processing, and delivering webhook events to external systems.
"""

from __future__ import annotations

import logging
import hashlib
import hmac
import json
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Set
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

from .integ_constants import Priority, MessageType, DEFAULT_TIMEOUT, DEFAULT_RETRY_ATTEMPTS
from .integ_exceptions import (
    IntegrationError, ValidationError, AuthenticationError,
    TimeoutError, ConnectionError
)
from .integ_signals import (
    webhook_received, webhook_processed, webhook_processing_failed,
    webhook_delivered, webhook_delivery_failed
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Webhook Types
# ---------------------------------------------------------------------------

class WebhookEventType(Enum):
    """Webhook event type enumeration."""
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    ACHIEVEMENT_EARNED = "achievement.earned"
    CONPLETED_CHALLENGE = "challenge.completed"
    LEVEL_UP = "user.level_up"
    STREAK_UPDATED = "streak.updated"
    CONTEST_STARTED = "contest.started"
    CONTEST_ENDED = "contest.ended"
    REWARD_CLAIMED = "reward.claimed"
    CUSTOM = "custom"


class WebhookStatus(Enum):
    """Webhook status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    ERROR = "error"


class DeliveryStatus(Enum):
    """Delivery status enumeration."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Webhook Data Classes
# ---------------------------------------------------------------------------

@dataclass
class WebhookEvent:
    """Webhook event data."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: WebhookEventType = WebhookEventType.CUSTOM
    source: str = ""
    target: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signature: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "source": self.source,
            "target": self.target,
            "payload": self.payload,
            "headers": self.headers,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }


@dataclass
class WebhookSubscription:
    """Webhook subscription configuration."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    target_url: str = ""
    event_types: List[WebhookEventType] = field(default_factory=list)
    secret: Optional[str] = None
    signature_algorithm: str = "sha256"
    active: bool = True
    timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_delivery: Optional[datetime] = None
    delivery_count: int = 0
    failure_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "target_url": self.target_url,
            "event_types": [et.value for et in self.event_types],
            "signature_algorithm": self.signature_algorithm,
            "active": self.active,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay,
            "headers": self.headers,
            "filters": self.filters,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_delivery": self.last_delivery.isoformat() if self.last_delivery else None,
            "delivery_count": self.delivery_count,
            "failure_count": self.failure_count
        }


@dataclass
class WebhookDelivery:
    """Webhook delivery attempt."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscription_id: str = ""
    event_id: str = ""
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempt_count: int = 0
    max_attempts: int = 3
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "event_id": self.event_id,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "response_status": self.response_status,
            "response_body": self.response_body,
            "response_headers": self.response_headers,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None
        }


@dataclass
class WebhookMetrics:
    """Webhook metrics."""
    
    total_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    average_delivery_time: float = 0.0
    active_subscriptions: int = 0
    last_event_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_events == 0:
            return 1.0
        return self.processed_events / self.total_events
    
    @property
    def delivery_success_rate(self) -> float:
        """Calculate delivery success rate."""
        if self.total_deliveries == 0:
            return 1.0
        return self.successful_deliveries / self.total_deliveries
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_events": self.total_events,
            "processed_events": self.processed_events,
            "failed_events": self.failed_events,
            "total_deliveries": self.total_deliveries,
            "successful_deliveries": self.successful_deliveries,
            "failed_deliveries": self.failed_deliveries,
            "success_rate": self.success_rate,
            "delivery_success_rate": self.delivery_success_rate,
            "average_delivery_time": self.average_delivery_time,
            "active_subscriptions": self.active_subscriptions,
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None
        }


# ---------------------------------------------------------------------------
# Abstract Webhook Handler
# ---------------------------------------------------------------------------

class BaseWebhookHandler(ABC):
    """Abstract base class for webhook handlers."""
    
    @abstractmethod
    def handle_event(self, event: WebhookEvent) -> bool:
        """Handle a webhook event."""
        pass
    
    @abstractmethod
    def validate_event(self, event: WebhookEvent) -> List[str]:
        """Validate a webhook event."""
        pass


# ---------------------------------------------------------------------------
# Webhook Processor
# ---------------------------------------------------------------------------

class WebhookProcessor:
    """Processor for webhook events."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.handlers: Dict[WebhookEventType, List[BaseWebhookHandler]] = defaultdict(list)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.metrics = WebhookMetrics()
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def register_handler(self, event_type: WebhookEventType, handler: BaseWebhookHandler) -> None:
        """Register a webhook handler."""
        with self._lock:
            self.handlers[event_type].append(handler)
            self.logger.info(f"Registered handler for event type: {event_type.value}")
    
    def unregister_handler(self, event_type: WebhookEventType, handler: BaseWebhookHandler) -> bool:
        """Unregister a webhook handler."""
        with self._lock:
            if event_type in self.handlers:
                try:
                    self.handlers[event_type].remove(handler)
                    self.logger.info(f"Unregistered handler for event type: {event_type.value}")
                    return True
                except ValueError:
                    pass
            return False
    
    def process_event(self, event: WebhookEvent) -> Future:
        """Process a webhook event asynchronously."""
        return self.executor.submit(self._process_event_sync, event)
    
    def _process_event_sync(self, event: WebhookEvent) -> bool:
        """Process a webhook event synchronously."""
        start_time = time.time()
        
        try:
            # Validate event
            validation_errors = self.validate_event(event)
            if validation_errors:
                self.logger.error(f"Event validation failed: {validation_errors}")
                self.metrics.failed_events += 1
                return False
            
            # Get handlers for this event type
            handlers = self.handlers.get(event.event_type, [])
            wildcard_handlers = self.handlers.get(WebhookEventType.CUSTOM, [])
            all_handlers = handlers + wildcard_handlers
            
            if not all_handlers:
                self.logger.warning(f"No handlers for event type: {event.event_type.value}")
                self.metrics.processed_events += 1
                return True
            
            # Process with all handlers
            success = True
            for handler in all_handlers:
                try:
                    if not handler.handle_event(event):
                        success = False
                        self.logger.warning(f"Handler failed for event: {event.id}")
                except Exception as e:
                    success = False
                    self.logger.error(f"Handler error for event {event.id}: {e}")
            
            # Update metrics
            processing_time = time.time() - start_time
            self.metrics.total_events += 1
            self.metrics.processed_events += 1
            self.metrics.last_event_time = datetime.now(timezone.utc)
            
            # Update average processing time
            total_time = self.metrics.average_delivery_time * (self.metrics.processed_events - 1) + processing_time
            self.metrics.average_delivery_time = total_time / self.metrics.processed_events
            
            # Emit signal
            if success:
                webhook_processed.send(
                    sender=self,
                    webhook_id=event.id,
                    integration_id=event.source,
                    event_type=event.event_type.value,
                    processing_result={"success": True, "processing_time": processing_time}
                )
            else:
                webhook_processing_failed.send(
                    sender=self,
                    webhook_id=event.id,
                    integration_id=event.source,
                    event_type=event.event_type.value,
                    error="Handler processing failed"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing event {event.id}: {e}")
            self.metrics.failed_events += 1
            self.metrics.total_events += 1
            
            webhook_processing_failed.send(
                sender=self,
                webhook_id=event.id,
                integration_id=event.source,
                event_type=event.event_type.value,
                error=str(e)
            )
            
            return False
    
    def validate_event(self, event: WebhookEvent) -> List[str]:
        """Validate a webhook event."""
        errors = []
        
        if not event.id:
            errors.append("Event ID is required")
        
        if not event.source:
            errors.append("Event source is required")
        
        if not event.payload:
            errors.append("Event payload is required")
        
        # Validate signature if present
        if event.signature:
            # This would implement signature validation
            pass
        
        return errors
    
    def get_metrics(self) -> WebhookMetrics:
        """Get webhook metrics."""
        with self._lock:
            return self.metrics


# ---------------------------------------------------------------------------
# Webhook Delivery Service
# ---------------------------------------------------------------------------

class WebhookDeliveryService:
    """Service for delivering webhooks to subscribers."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.subscriptions: Dict[str, WebhookSubscription] = {}
        self.delivery_queue: deque[WebhookDelivery] = deque()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.metrics = WebhookMetrics()
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._running = False
        self._delivery_thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the delivery service."""
        if self._running:
            return
        
        self._running = True
        self._delivery_thread = threading.Thread(target=self._delivery_loop, daemon=True)
        self._delivery_thread.start()
        
        self.logger.info("Webhook delivery service started")
    
    def stop(self) -> None:
        """Stop the delivery service."""
        self._running = False
        
        if self._delivery_thread:
            self._delivery_thread.join(timeout=5.0)
        
        self.executor.shutdown(wait=True)
        self.logger.info("Webhook delivery service stopped")
    
    def subscribe(self, subscription: WebhookSubscription) -> str:
        """Add a webhook subscription."""
        with self._lock:
            self.subscriptions[subscription.id] = subscription
            self.metrics.active_subscriptions = len(self.subscriptions)
            self.logger.info(f"Added webhook subscription: {subscription.id}")
            return subscription.id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a webhook subscription."""
        with self._lock:
            if subscription_id in self.subscriptions:
                del self.subscriptions[subscription_id]
                self.metrics.active_subscriptions = len(self.subscriptions)
                self.logger.info(f"Removed webhook subscription: {subscription_id}")
                return True
            return False
    
    def deliver_event(self, event: WebhookEvent) -> List[Future]:
        """Deliver event to all matching subscriptions."""
        futures = []
        
        with self._lock:
            matching_subscriptions = [
                sub for sub in self.subscriptions.values()
                if sub.active and self._subscription_matches_event(sub, event)
            ]
        
        for subscription in matching_subscriptions:
            delivery = WebhookDelivery(
                subscription_id=subscription.id,
                event_id=event.id,
                max_attempts=subscription.retry_attempts
            )
            
            with self._lock:
                self.delivery_queue.append(delivery)
            
            future = self.executor.submit(self._process_delivery, delivery, event, subscription)
            futures.append(future)
        
        return futures
    
    def _subscription_matches_event(self, subscription: WebhookSubscription, event: WebhookEvent) -> bool:
        """Check if subscription matches event."""
        # Check event type
        if subscription.event_types and event.event_type not in subscription.event_types:
            return False
        
        # Apply filters
        for filter_key, filter_value in subscription.filters.items():
            if filter_key == "source":
                if event.source != filter_value:
                    return False
            elif filter_key == "target":
                if event.target != filter_value:
                    return False
            elif filter_key in event.metadata:
                if event.metadata[filter_key] != filter_value:
                    return False
        
        return True
    
    def _delivery_loop(self) -> None:
        """Main delivery loop."""
        while self._running:
            try:
                delivery = None
                
                with self._lock:
                    if self.delivery_queue:
                        delivery = self.delivery_queue.popleft()
                
                if delivery:
                    # Get event and subscription
                    event = self._get_event(delivery.event_id)
                    subscription = self.subscriptions.get(delivery.subscription_id)
                    
                    if event and subscription:
                        self._process_delivery(delivery, event, subscription)
                else:
                    # No deliveries, wait a bit
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"Error in delivery loop: {e}")
    
    def _process_delivery(
        self,
        delivery: WebhookDelivery,
        event: WebhookEvent,
        subscription: WebhookSubscription
    ) -> bool:
        """Process a webhook delivery."""
        start_time = time.time()
        
        try:
            # Prepare webhook payload
            webhook_data = {
                "id": event.id,
                "event": event.event_type.value,
                "source": event.source,
                "target": event.target,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat(),
                "signature": self._generate_signature(event, subscription)
            }
            
            # Prepare headers
            headers = subscription.headers.copy()
            headers.update({
                "Content-Type": "application/json",
                "User-Agent": "Gamification-Webhook/1.0",
                "X-Webhook-ID": event.id,
                "X-Event-Type": event.event_type.value,
                "X-Timestamp": event.timestamp.isoformat()
            })
            
            if event.signature:
                headers["X-Webhook-Signature"] = event.signature
            
            # Send webhook
            import requests
            
            response = requests.post(
                subscription.target_url,
                json=webhook_data,
                headers=headers,
                timeout=subscription.timeout
            )
            
            # Update delivery record
            delivery.status = DeliveryStatus.DELIVERED if response.status_code < 400 else DeliveryStatus.FAILED
            delivery.response_status = response.status_code
            delivery.response_body = response.text
            delivery.response_headers = dict(response.headers)
            delivery.delivered_at = datetime.now(timezone.utc)
            delivery.attempt_count += 1
            
            # Update subscription metrics
            with self._lock:
                subscription.delivery_count += 1
                subscription.last_delivery = delivery.delivered_at
                
                if delivery.status == DeliveryStatus.FAILED:
                    subscription.failure_count += 1
            
            # Update global metrics
            self.metrics.total_deliveries += 1
            if delivery.status == DeliveryStatus.DELIVERED:
                self.metrics.successful_deliveries += 1
            else:
                self.metrics.failed_deliveries += 1
            
            # Emit signal
            if delivery.status == DeliveryStatus.DELIVERED:
                webhook_delivered.send(
                    sender=self,
                    webhook_id=event.id,
                    integration_id=event.source,
                    target_url=subscription.target_url,
                    delivery_result={"status_code": response.status_code}
                )
            else:
                webhook_delivery_failed.send(
                    sender=self,
                    webhook_id=event.id,
                    integration_id=event.source,
                    target_url=subscription.target_url,
                    error=f"HTTP {response.status_code}"
                )
            
            self.logger.info(f"Webhook delivered: {event.id} to {subscription.target_url}")
            return delivery.status == DeliveryStatus.DELIVERED
            
        except Exception as e:
            # Update delivery record
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)
            delivery.attempt_count += 1
            
            # Schedule retry if needed
            if delivery.attempt_count < delivery.max_attempts:
                delivery.status = DeliveryStatus.RETRYING
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=subscription.retry_delay ** delivery.attempt_count)
                
                with self._lock:
                    self.delivery_queue.append(delivery)
            else:
                delivery.status = DeliveryStatus.EXPIRED
            
            # Update metrics
            self.metrics.total_deliveries += 1
            self.metrics.failed_deliveries += 1
            
            webhook_delivery_failed.send(
                sender=self,
                webhook_id=event.id,
                integration_id=event.source,
                target_url=subscription.target_url,
                error=str(e)
            )
            
            self.logger.error(f"Webhook delivery failed: {event.id} to {subscription.target_url}: {e}")
            return False
    
    def _generate_signature(self, event: WebhookEvent, subscription: WebhookSubscription) -> str:
        """Generate webhook signature."""
        if not subscription.secret:
            return ""
        
        # Create payload string
        payload_str = json.dumps(event.payload, sort_keys=True, separators=(',', ':'))
        
        # Generate signature
        if subscription.signature_algorithm == "sha256":
            signature = hmac.new(
                subscription.secret.encode('utf-8'),
                payload_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
        else:
            signature = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
        
        return f"{subscription.signature_algorithm}={signature}"
    
    def _get_event(self, event_id: str) -> Optional[WebhookEvent]:
        """Get event by ID (placeholder implementation)."""
        # This would retrieve the event from storage
        # For now, return a mock event
        return WebhookEvent(id=event_id)
    
    def get_subscription(self, subscription_id: str) -> Optional[WebhookSubscription]:
        """Get subscription by ID."""
        with self._lock:
            return self.subscriptions.get(subscription_id)
    
    def list_subscriptions(self) -> List[WebhookSubscription]:
        """List all subscriptions."""
        with self._lock:
            return list(self.subscriptions.values())
    
    def get_metrics(self) -> WebhookMetrics:
        """Get delivery metrics."""
        with self._lock:
            return self.metrics


# ---------------------------------------------------------------------------
# Webhook Manager
# ---------------------------------------------------------------------------

class WebhookManager:
    """Manager for webhook processing and delivery."""
    
    def __init__(self, max_workers: int = 4):
        self.processor = WebhookProcessor(max_workers=max_workers)
        self.delivery_service = WebhookDeliveryService(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)
    
    def start(self) -> None:
        """Start webhook services."""
        self.delivery_service.start()
        self.logger.info("Webhook manager started")
    
    def stop(self) -> None:
        """Stop webhook services."""
        self.delivery_service.stop()
        self.logger.info("Webhook manager stopped")
    
    def receive_webhook(
        self,
        event_type: WebhookEventType,
        source: str,
        payload: Dict[str, Any],
        **kwargs: Any
    ) -> str:
        """Receive and process a webhook event."""
        event = WebhookEvent(
            event_type=event_type,
            source=source,
            payload=payload,
            target=kwargs.get("target"),
            headers=kwargs.get("headers", {}),
            metadata=kwargs.get("metadata", {}),
            signature=kwargs.get("signature")
        )
        
        # Emit signal
        webhook_received.send(
            sender=self,
            webhook_id=event.id,
            integration_id=source,
            event_type=event_type.value,
            payload=payload,
            headers=kwargs.get("headers", {})
        )
        
        # Process event
        future = self.processor.process_event(event)
        
        # Deliver to subscribers
        delivery_futures = self.delivery_service.deliver_event(event)
        
        return event.id
    
    def register_handler(self, event_type: WebhookEventType, handler: BaseWebhookHandler) -> None:
        """Register a webhook handler."""
        self.processor.register_handler(event_type, handler)
    
    def subscribe(self, subscription: WebhookSubscription) -> str:
        """Add a webhook subscription."""
        return self.delivery_service.subscribe(subscription)
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a webhook subscription."""
        return self.delivery_service.unsubscribe(subscription_id)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics from all services."""
        return {
            "processor_metrics": self.processor.get_metrics().to_dict(),
            "delivery_metrics": self.delivery_service.get_metrics().to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global webhook manager instance
webhook_manager = WebhookManager()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_webhook_subscription(
    name: str,
    target_url: str,
    event_types: List[WebhookEventType],
    secret: Optional[str] = None,
    **kwargs: Any
) -> WebhookSubscription:
    """Create a webhook subscription."""
    subscription = WebhookSubscription(
        name=name,
        target_url=target_url,
        event_types=event_types,
        secret=secret,
        **kwargs
    )
    
    webhook_manager.subscribe(subscription)
    return subscription


def send_webhook_event(
    event_type: WebhookEventType,
    source: str,
    payload: Dict[str, Any],
    **kwargs: Any
) -> str:
    """Send a webhook event."""
    return webhook_manager.receive_webhook(event_type, source, payload, **kwargs)


# Initialize logging
logger.info("Webhooks integration module initialized")
