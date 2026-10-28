# engagement/integration_system/webhooks_integration.py
"""
Webhook integration system for engagement platform.
Provides webhook handling, processing, and delivery capabilities.
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
import hmac
import threading
import time
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .integ_constants import (
    IntegrationType, DataType, HttpMethod, ERROR_CODES, SUCCESS_CODES,
    DEFAULT_CONFIG, CACHE_KEYS
)
from .event_bus import event_bus, Event, EventType, EventBuilder
from .circuit_breaker import circuit_breaker_registry, CircuitBreakerUtils

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Webhook event types."""
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    CHECKIN_COMPLETED = "checkin.completed"
    QUEST_COMPLETED = "quest.completed"
    ACHIEVEMENT_UNLOCKED = "achievement.unlocked"
    PURCHASE_COMPLETED = "purchase.completed"
    LEADERBOARD_UPDATED = "leaderboard.updated"
    SYSTEM_ERROR = "system.error"
    SECURITY_ALERT = "security.alert"
    CUSTOM = "custom"


class WebhookStatus(Enum):
    """Webhook status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"
    TESTING = "testing"


class WebhookDeliveryStatus(Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    EXPIRED = "expired"


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    id: str
    name: str
    url: str
    event_types: List[WebhookEventType]
    secret: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_count: int = 3
    retry_delay: int = 60
    status: WebhookStatus = WebhookStatus.ACTIVE
    signature_method: str = "sha256"  # sha256, sha1, md5
    signature_header: str = "X-Webhook-Signature"
    content_type: str = "application/json"
    active: bool = True
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    last_delivery: Optional[datetime] = None
    delivery_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookDelivery:
    """Webhook delivery information."""
    id: str
    webhook_id: str
    event_type: WebhookEventType
    payload: Dict[str, Any]
    status: WebhookDeliveryStatus = WebhookDeliveryStatus.PENDING
    attempt_count: int = 0
    max_attempts: int = 3
    next_attempt_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=timezone.now)
    delivered_at: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


class BaseWebhookProcessor(ABC):
    """Base webhook processor class."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def process_webhook(self, webhook_config: WebhookConfig, event: Event) -> WebhookDelivery:
        """Process webhook delivery."""
        pass
    
    @abstractmethod
    def validate_webhook(self, webhook_config: WebhookConfig) -> bool:
        """Validate webhook configuration."""
        pass
    
    @abstractmethod
    def generate_signature(self, payload: str, secret: str, method: str) -> str:
        """Generate webhook signature."""
        pass


class HttpWebhookProcessor(BaseWebhookProcessor):
    """HTTP webhook processor."""
    
    def process_webhook(self, webhook_config: WebhookConfig, event: Event) -> WebhookDelivery:
        """Process webhook delivery via HTTP."""
        delivery = WebhookDelivery(
            id=f"delivery_{timezone.now().timestamp()}",
            webhook_id=webhook_config.id,
            event_type=WebhookEventType(event.name),
            payload=event.data
        )
        
        start_time = time.time()
        
        try:
            # Prepare payload
            payload_data = self._prepare_payload(event)
            payload_json = json.dumps(payload_data)
            
            # Generate signature
            signature = self.generate_signature(
                payload_json, 
                webhook_config.secret or "", 
                webhook_config.signature_method
            )
            
            # Prepare headers
            headers = {
                'Content-Type': webhook_config.content_type,
                'User-Agent': 'Engagement-Webhook/1.0',
                webhook_config.signature_header: signature,
                **webhook_config.headers
            }
            
            # Send webhook
            response = self._send_http_request(
                webhook_config.url,
                payload_json,
                headers,
                webhook_config.timeout
            )
            
            # Update delivery status
            delivery.status = WebhookDeliveryStatus.DELIVERED
            delivery.response_status = response.status_code
            delivery.response_body = response.text
            delivery.delivered_at = timezone.now()
            delivery.duration_ms = int((time.time() - start_time) * 1000)
            
            # Update webhook stats
            webhook_config.delivery_count += 1
            webhook_config.last_delivery = timezone.now()
            
            self.logger.info(f"Webhook delivered: {delivery.id} to {webhook_config.url}")
            
        except Exception as exc:
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.error_message = str(exc)
            delivery.attempt_count += 1
            
            # Schedule retry if needed
            if delivery.attempt_count < delivery.max_attempts:
                delivery.status = WebhookDeliveryStatus.RETRYING
                delivery.next_attempt_at = timezone.now() + timedelta(seconds=webhook_config.retry_delay)
            
            webhook_config.failure_count += 1
            
            self.logger.error(f"Webhook delivery failed: {delivery.id} - {exc}")
        
        return delivery
    
    def validate_webhook(self, webhook_config: WebhookConfig) -> bool:
        """Validate webhook configuration."""
        try:
            # Check URL
            if not webhook_config.url:
                return False
            
            # Check event types
            if not webhook_config.event_types:
                return False
            
            # Test connectivity
            response = self._send_http_request(
                webhook_config.url,
                json.dumps({"test": True}),
                {'Content-Type': webhook_config.content_type},
                10  # Short timeout for validation
            )
            
            return response.status_code < 400
            
        except Exception as exc:
            self.logger.error(f"Webhook validation failed: {exc}")
            return False
    
    def generate_signature(self, payload: str, secret: str, method: str) -> str:
        """Generate webhook signature."""
        if not secret:
            return ""
        
        if method.lower() == 'sha256':
            return hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
        elif method.lower() == 'sha1':
            return hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha1
            ).hexdigest()
        elif method.lower() == 'md5':
            return hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.md5
            ).hexdigest()
        else:
            return ""
    
    def _prepare_payload(self, event: Event) -> Dict[str, Any]:
        """Prepare webhook payload."""
        return {
            'event': event.name,
            'event_type': event.type.value,
            'timestamp': event.timestamp.isoformat(),
            'source': event.source,
            'data': event.data,
            'metadata': event.metadata
        }
    
    def _send_http_request(self, url: str, payload: str, headers: Dict[str, str], timeout: int):
        """Send HTTP request."""
        import requests
        
        return requests.post(
            url,
            data=payload,
            headers=headers,
            timeout=timeout
        )


class WebhookManager:
    """Manager for webhook operations."""
    
    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.deliveries: Dict[str, WebhookDelivery] = {}
        self.processors: Dict[str, BaseWebhookProcessor] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.WebhookManager")
        
        # Register default processor
        self.register_processor('http', HttpWebhookProcessor('http'))
    
    def register_processor(self, name: str, processor: BaseWebhookProcessor):
        """Register webhook processor."""
        self.processors[name] = processor
        self.logger.info(f"Registered webhook processor: {name}")
    
    def register_webhook(self, webhook_config: WebhookConfig) -> bool:
        """Register webhook."""
        try:
            with self._lock:
                # Validate webhook
                processor = self.processors.get('http')  # Default to HTTP processor
                if not processor or not processor.validate_webhook(webhook_config):
                    self.logger.error(f"Webhook validation failed: {webhook_config.id}")
                    return False
                
                self.webhooks[webhook_config.id] = webhook_config
                
                # Cache webhook
                self._cache_webhook(webhook_config)
                
                self.logger.info(f"Registered webhook: {webhook_config.id}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to register webhook {webhook_config.id}: {exc}")
            return False
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """Unregister webhook."""
        try:
            with self._lock:
                if webhook_id in self.webhooks:
                    del self.webhooks[webhook_id]
                    self._clear_webhook_cache(webhook_id)
                    self.logger.info(f"Unregistered webhook: {webhook_id}")
                    return True
        except Exception as exc:
            self.logger.error(f"Failed to unregister webhook {webhook_id}: {exc}")
        return False
    
    def trigger_webhooks(self, event: Event) -> List[WebhookDelivery]:
        """Trigger webhooks for event."""
        deliveries = []
        
        try:
            event_type = WebhookEventType(event.name)
            
            with self._lock:
                # Find matching webhooks
                matching_webhooks = [
                    webhook for webhook in self.webhooks.values()
                    if (webhook.active and 
                        webhook.status == WebhookStatus.ACTIVE and
                        event_type in webhook.event_types)
                ]
            
            # Process each webhook
            for webhook in matching_webhooks:
                try:
                    processor = self.processors.get('http')
                    if processor:
                        delivery = processor.process_webhook(webhook, event)
                        deliveries.append(delivery)
                        self.deliveries[delivery.id] = delivery
                        
                        # Cache delivery
                        self._cache_delivery(delivery)
                        
                except Exception as exc:
                    self.logger.error(f"Failed to process webhook {webhook.id}: {exc}")
            
            self.logger.info(f"Triggered {len(deliveries)} webhooks for event {event.name}")
            
        except Exception as exc:
            self.logger.error(f"Failed to trigger webhooks: {exc}")
        
        return deliveries
    
    def retry_failed_deliveries(self) -> int:
        """Retry failed webhook deliveries."""
        retry_count = 0
        
        try:
            with self._lock:
                # Find deliveries to retry
                now = timezone.now()
                deliveries_to_retry = [
                    delivery for delivery in self.deliveries.values()
                    if (delivery.status == WebhookDeliveryStatus.RETRYING and
                        delivery.next_attempt_at and
                        delivery.next_attempt_at <= now)
                ]
            
            for delivery in deliveries_to_retry:
                webhook = self.webhooks.get(delivery.webhook_id)
                if not webhook:
                    continue
                
                # Create event from delivery
                event = Event(
                    id=delivery.id,
                    type=EventType.INTEGRATION,
                    name=delivery.event_type.value,
                    data=delivery.payload,
                    source="webhook_retry"
                )
                
                # Retry delivery
                processor = self.processors.get('http')
                if processor:
                    new_delivery = processor.process_webhook(webhook, event)
                    
                    # Update delivery
                    new_delivery.attempt_count = delivery.attempt_count + 1
                    new_delivery.id = delivery.id
                    
                    self.deliveries[delivery.id] = new_delivery
                    self._cache_delivery(new_delivery)
                    
                    retry_count += 1
            
            self.logger.info(f"Retried {retry_count} webhook deliveries")
            
        except Exception as exc:
            self.logger.error(f"Failed to retry webhook deliveries: {exc}")
        
        return retry_count
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get webhook by ID."""
        webhook = self.webhooks.get(webhook_id)
        if not webhook:
            # Try to get from cache
            webhook = self._get_cached_webhook(webhook_id)
            if webhook:
                self.webhooks[webhook_id] = webhook
        
        return webhook
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get delivery by ID."""
        delivery = self.deliveries.get(delivery_id)
        if not delivery:
            # Try to get from cache
            delivery = self._get_cached_delivery(delivery_id)
            if delivery:
                self.deliveries[delivery_id] = delivery
        
        return delivery
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get webhook statistics."""
        with self._lock:
            total_webhooks = len(self.webhooks)
            active_webhooks = sum(1 for w in self.webhooks.values() if w.active)
            total_deliveries = len(self.deliveries)
            successful_deliveries = sum(1 for d in self.deliveries.values() if d.status == WebhookDeliveryStatus.DELIVERED)
            failed_deliveries = sum(1 for d in self.deliveries.values() if d.status == WebhookDeliveryStatus.FAILED)
            
            return {
                'total_webhooks': total_webhooks,
                'active_webhooks': active_webhooks,
                'total_deliveries': total_deliveries,
                'successful_deliveries': successful_deliveries,
                'failed_deliveries': failed_deliveries,
                'success_rate': (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0,
                'last_updated': timezone.now().isoformat()
            }
    
    def _cache_webhook(self, webhook: WebhookConfig):
        """Cache webhook configuration."""
        cache_key = f"webhook_config:{webhook.id}"
        cache.set(cache_key, webhook.__dict__, timeout=3600)  # 1 hour
    
    def _get_cached_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get cached webhook configuration."""
        cache_key = f"webhook_config:{webhook_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return WebhookConfig(**cached_data)
        
        return None
    
    def _clear_webhook_cache(self, webhook_id: str):
        """Clear cached webhook configuration."""
        cache_key = f"webhook_config:{webhook_id}"
        cache.delete(cache_key)
    
    def _cache_delivery(self, delivery: WebhookDelivery):
        """Cache webhook delivery."""
        cache_key = f"webhook_delivery:{delivery.id}"
        cache.set(cache_key, delivery.__dict__, timeout=86400)  # 24 hours
    
    def _get_cached_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get cached webhook delivery."""
        cache_key = f"webhook_delivery:{delivery_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return WebhookDelivery(**cached_data)
        
        return None


# Webhook API views
class WebhookAPIView(APIView):
    """API view for webhook management."""
    
    def __init__(self):
        super().__init__()
        self.webhook_manager = WebhookManager()
    
    def get(self, request):
        """Get webhook statistics."""
        stats = self.webhook_manager.get_statistics()
        return Response(stats)
    
    def post(self, request):
        """Create new webhook."""
        try:
            data = request.data
            
            # Create webhook config
            webhook_config = WebhookConfig(
                id=data.get('id'),
                name=data.get('name'),
                url=data.get('url'),
                event_types=[WebhookEventType(t) for t in data.get('event_types', [])],
                secret=data.get('secret'),
                headers=data.get('headers', {}),
                timeout=data.get('timeout', 30),
                retry_count=data.get('retry_count', 3),
                retry_delay=data.get('retry_delay', 60),
                signature_method=data.get('signature_method', 'sha256'),
                signature_header=data.get('signature_header', 'X-Webhook-Signature'),
                content_type=data.get('content_type', 'application/json'),
                active=data.get('active', True),
                metadata=data.get('metadata', {})
            )
            
            # Register webhook
            if self.webhook_manager.register_webhook(webhook_config):
                return Response({
                    'success': True,
                    'webhook_id': webhook_config.id,
                    'message': 'Webhook registered successfully'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': 'Failed to register webhook'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as exc:
            return Response({
                'success': False,
                'message': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebhookDeliveryView(APIView):
    """API view for webhook delivery tracking."""
    
    def __init__(self):
        super().__init__()
        self.webhook_manager = WebhookManager()
    
    def get(self, request, delivery_id):
        """Get delivery information."""
        delivery = self.webhook_manager.get_delivery(delivery_id)
        
        if delivery:
            return Response({
                'success': True,
                'delivery': delivery.__dict__
            })
        else:
            return Response({
                'success': False,
                'message': 'Delivery not found'
            }, status=status.HTTP_404_NOT_FOUND)


# Webhook event handlers
class WebhookEventHandlers:
    """Event handlers for webhook system."""
    
    def __init__(self):
        self.webhook_manager = WebhookManager()
        self.logger = logging.getLogger(f"{__name__}.WebhookEventHandlers")
        
        # Register event handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register event handlers."""
        from .integ_signals import signal_manager
        
        # Register for engagement events
        signal_manager.send_integration_execution_completed = self._handle_integration_event
        signal_manager.send_data_processed = self._handle_data_event
        signal_manager.send_security_alert = self._handle_security_event
    
    def _handle_integration_event(self, sender, **kwargs):
        """Handle integration events."""
        try:
            integration_id = kwargs.get('integration_id')
            success = kwargs.get('success', True)
            data = kwargs.get('data', {})
            
            # Create event
            event_type = 'integration.completed' if success else 'integration.failed'
            event = EventBuilder.integration_event(
                event_type,
                integration_id,
                data={
                    'success': success,
                    'data': data
                }
            )
            
            # Trigger webhooks
            self.webhook_manager.trigger_webhooks(event)
            
        except Exception as exc:
            self.logger.error(f"Failed to handle integration event: {exc}")
    
    def _handle_data_event(self, sender, **kwargs):
        """Handle data events."""
        try:
            integration_id = kwargs.get('integration_id')
            data_type = kwargs.get('data_type')
            records_processed = kwargs.get('records_processed', 0)
            
            # Create event
            event = EventBuilder.create(
                EventType.DATA,
                'data.processed',
                data={
                    'integration_id': integration_id,
                    'data_type': data_type,
                    'records_processed': records_processed
                }
            )
            
            # Trigger webhooks
            self.webhook_manager.trigger_webhooks(event)
            
        except Exception as exc:
            self.logger.error(f"Failed to handle data event: {exc}")
    
    def _handle_security_event(self, sender, **kwargs):
        """Handle security events."""
        try:
            alert_type = kwargs.get('alert_type')
            integration_id = kwargs.get('integration_id')
            details = kwargs.get('details', {})
            
            # Create event
            event = EventBuilder.security_event(
                f'security.{alert_type}',
                data={
                    'integration_id': integration_id,
                    'alert_type': alert_type,
                    'details': details
                }
            )
            
            # Trigger webhooks
            self.webhook_manager.trigger_webhooks(event)
            
        except Exception as exc:
            self.logger.error(f"Failed to handle security event: {exc}")


# Webhook utilities
class WebhookUtils:
    """Utilities for webhook management."""
    
    @staticmethod
    def create_webhook_config(id: str, name: str, url: str, event_types: List[str], **kwargs) -> WebhookConfig:
        """Create webhook configuration."""
        return WebhookConfig(
            id=id,
            name=name,
            url=url,
            event_types=[WebhookEventType(t) for t in event_types],
            **kwargs
        )
    
    @staticmethod
    def verify_webhook_signature(payload: str, signature: str, secret: str, method: str = 'sha256') -> bool:
        """Verify webhook signature."""
        if method.lower() == 'sha256':
            expected_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
        elif method.lower() == 'sha1':
            expected_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha1
            ).hexdigest()
        elif method.lower() == 'md5':
            expected_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.md5
            ).hexdigest()
        else:
            return False
        
        return hmac.compare_digest(signature, expected_signature)
    
    @staticmethod
    def parse_webhook_event(request: HttpRequest) -> Dict[str, Any]:
        """Parse webhook event from request."""
        try:
            # Get signature
            signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
            
            # Get payload
            content_type = request.content_type
            if content_type == 'application/json':
                payload = request.body.decode('utf-8')
                data = json.loads(payload)
            else:
                payload = request.body.decode('utf-8')
                data = {'raw_payload': payload}
            
            return {
                'signature': signature,
                'payload': payload,
                'data': data,
                'content_type': content_type
            }
            
        except Exception as exc:
            logger.error(f"Failed to parse webhook event: {exc}")
            return {}


# Global webhook manager instance
webhook_manager = WebhookManager()
webhook_handlers = WebhookEventHandlers()


# Decorators
def webhook_trigger(event_types: List[str]):
    """Decorator to trigger webhooks for function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Create event
            event = EventBuilder.create(
                EventType.BUSINESS,
                func.__name__,
                data={
                    'result': result,
                    'args': args,
                    'kwargs': kwargs
                }
            )
            
            # Trigger webhooks
            webhook_manager.trigger_webhooks(event)
            
            return result
        return wrapper
    return decorator


# Webhook URL patterns
def get_webhook_urls():
    """Get webhook URL patterns."""
    from django.urls import path
    
    return [
        path('api/webhooks/', WebhookAPIView.as_view(), name='webhook-api'),
        path('api/webhooks/<str:delivery_id>/', WebhookDeliveryView.as_view(), name='webhook-delivery'),
    ]
