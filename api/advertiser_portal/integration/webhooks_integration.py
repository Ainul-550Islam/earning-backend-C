"""
Webhooks Integration Layer

This module provides seamless integration between the advertiser_portal
and the webhooks module, enabling real-time webhook delivery
and event notification to external systems.
"""

import asyncio
import json
import logging
import time
import hashlib
import hmac
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
import aiohttp
import requests

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.urls import reverse

from .event_bus import event_bus, Event, EventPriority
from .performance_monitor import performance_monitor
from ..models.advertiser import Advertiser
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
from ..models.tracking import Conversion
from ..models.notification import AdvertiserNotification
from ..exceptions import *
from ..utils import *

logger = logging.getLogger(__name__)


@dataclass
class WebhookConfig:
    """Webhook configuration data structure."""
    webhook_id: str
    advertiser_id: str
    url: str
    events: List[str]  # List of event types to subscribe to
    secret_key: Optional[str] = None
    is_active: bool = True
    retry_count: int = 3
    timeout_seconds: int = 30
    headers: Dict[str, str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.created_at is None:
            self.created_at = timezone.now()


@dataclass
class WebhookDelivery:
    """Webhook delivery attempt data structure."""
    delivery_id: str
    webhook_id: str
    event_type: str
    payload: Dict[str, Any]
    status: str  # 'pending', 'delivered', 'failed', 'retrying'
    attempt_count: int = 0
    max_attempts: int = 3
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    delivered_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = timezone.now()


@dataclass
class WebhookEvent:
    """Webhook event data structure."""
    event_id: str
    event_type: str
    data: Dict[str, Any]
    source: str
    timestamp: datetime
    advertiser_id: Optional[str] = None
    campaign_id: Optional[str] = None
    offer_id: Optional[str] = None
    conversion_id: Optional[str] = None


class WebhooksIntegration:
    """
    Integration layer for webhooks functionality.
    
    Provides reliable webhook delivery with retry logic,
    signature verification, and comprehensive monitoring.
    """
    
    def __init__(self):
        self.webhook_configs: Dict[str, WebhookConfig] = {}
        self.active_deliveries: Dict[str, WebhookDelivery] = {}
        self.delivery_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.event_mappings: Dict[str, str] = {}
        
        # Performance targets
        self.WEBHOOK_DELIVERY_LATENCY_MS = 200
        self.QUEUE_PROCESSING_BATCH_SIZE = 50
        
        # Initialize event mappings
        self._initialize_event_mappings()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Start background tasks
        try:
            _loop = asyncio.get_running_loop()
            _loop.create_task(self._delivery_processing_loop())
        except RuntimeError:
            pass  # No running event loop at import time
        try:
            _loop = asyncio.get_running_loop()
            _loop.create_task(self._retry_processing_loop())
        except RuntimeError:
            pass  # No running event loop at import time
        try:
            _loop = asyncio.get_running_loop()
            _loop.create_task(self._cleanup_loop())
        except RuntimeError:
            pass  # No running event loop at import time
    
    def _initialize_event_mappings(self):
        """Initialize event type mappings for webhooks."""
        self.event_mappings = {
            'advertiser_created': 'advertiser.created',
            'advertiser_updated': 'advertiser.updated',
            'advertiser_verified': 'advertiser.verified',
            'campaign_created': 'campaign.created',
            'campaign_updated': 'campaign.updated',
            'campaign_activated': 'campaign.activated',
            'campaign_paused': 'campaign.paused',
            'offer_created': 'offer.created',
            'offer_updated': 'offer.updated',
            'offer_activated': 'offer.activated',
            'conversion_received': 'conversion.received',
            'conversion_approved': 'conversion.approved',
            'conversion_rejected': 'conversion.rejected',
            'billing_transaction': 'billing.transaction',
            'invoice_generated': 'billing.invoice_generated',
            'fraud_detected': 'fraud.detected',
            'notification_sent': 'notification.sent'
        }
    
    def _register_event_handlers(self):
        """Register event handlers for webhook integration."""
        event_bus.register_handler(
            'advertiser_created',
            self.handle_advertiser_event,
            priority=EventPriority.NORMAL
        )
        
        event_bus.register_handler(
            'campaign_created',
            self.handle_campaign_event,
            priority=EventPriority.NORMAL
        )
        
        event_bus.register_handler(
            'offer_created',
            self.handle_offer_event,
            priority=EventPriority.NORMAL
        )
        
        event_bus.register_handler(
            'conversion_received',
            self.handle_conversion_event,
            priority=EventPriority.HIGH
        )
        
        event_bus.register_handler(
            'billing_transaction',
            self.handle_billing_event,
            priority=EventPriority.NORMAL
        )
        
        event_bus.register_handler(
            'fraud_detected',
            self.handle_fraud_event,
            priority=EventPriority.HIGH
        )
    
    async def register_webhook(self, config: WebhookConfig) -> Dict[str, Any]:
        """
        Register a new webhook configuration.
        
        Args:
            config: Webhook configuration
            
        Returns:
            Registration result
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('register_webhook'):
                # Validate configuration
                validation_result = await self._validate_webhook_config(config)
                if not validation_result['valid']:
                    raise ValidationError(validation_result['errors'])
                
                # Test webhook URL
                test_result = await self._test_webhook_url(config.url, config.secret_key)
                if not test_result['success']:
                    raise IntegrationError(f"Webhook URL test failed: {test_result['error']}")
                
                # Store configuration
                self.webhook_configs[config.webhook_id] = config
                
                # Emit webhook registration event
                await event_bus.emit(
                    'webhook_registered',
                    {
                        'webhook_id': config.webhook_id,
                        'advertiser_id': config.advertiser_id,
                        'url': config.url,
                        'events': config.events,
                        'is_active': config.is_active
                    },
                    source='advertiser_portal',
                    priority=EventPriority.NORMAL
                )
                
                processing_time = (time.time() - start_time) * 1000
                
                return {
                    'success': True,
                    'webhook_id': config.webhook_id,
                    'status': 'registered',
                    'events': config.events,
                    'processing_time_ms': processing_time
                }
                
        except Exception as e:
            logger.error(f"Error registering webhook: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time_ms': (time.time() - start_time) * 1000
            }
    
    async def unregister_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Unregister a webhook configuration.
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            Unregistration result
        """
        try:
            with performance_monitor.measure('unregister_webhook'):
                config = self.webhook_configs.get(webhook_id)
                if not config:
                    return {
                        'success': False,
                        'error': 'Webhook not found'
                    }
                
                # Remove configuration
                del self.webhook_configs[webhook_id]
                
                # Cancel pending deliveries
                await self._cancel_pending_deliveries(webhook_id)
                
                # Emit webhook unregistration event
                await event_bus.emit(
                    'webhook_unregistered',
                    {
                        'webhook_id': webhook_id,
                        'advertiser_id': config.advertiser_id
                    },
                    source='advertiser_portal',
                    priority=EventPriority.NORMAL
                )
                
                return {
                    'success': True,
                    'webhook_id': webhook_id,
                    'status': 'unregistered'
                }
                
        except Exception as e:
            logger.error(f"Error unregistering webhook: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def deliver_webhook(self, webhook_event: WebhookEvent) -> List[WebhookDelivery]:
        """
        Deliver webhook event to all matching webhooks.
        
        Args:
            webhook_event: Webhook event data
            
        Returns:
            List of webhook delivery attempts
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('deliver_webhook'):
                deliveries = []
                
                # Find matching webhooks
                matching_webhooks = await self._find_matching_webhooks(webhook_event)
                
                # Create delivery attempts
                for webhook_config in matching_webhooks:
                    delivery = WebhookDelivery(
                        delivery_id=f"{webhook_config.webhook_id}_{webhook_event.event_id}_{int(time.time())}",
                        webhook_id=webhook_config.webhook_id,
                        event_type=webhook_event.event_type,
                        payload=await self._prepare_webhook_payload(webhook_event, webhook_config),
                        status='pending',
                        max_attempts=webhook_config.retry_count
                    )
                    
                    deliveries.append(delivery)
                    self.active_deliveries[delivery.delivery_id] = delivery
                    
                    # Add to delivery queue
                    await self.delivery_queue.put(delivery)
                
                processing_time = (time.time() - start_time) * 1000
                
                # Log slow deliveries
                if processing_time > self.WEBHOOK_DELIVERY_LATENCY_MS:
                    logger.warning(f"Slow webhook delivery setup: {webhook_event.event_type} took {processing_time:.2f}ms")
                
                return deliveries
                
        except Exception as e:
            logger.error(f"Error delivering webhook: {e}")
            return []
    
    async def get_webhook_status(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook status and performance metrics."""
        config = self.webhook_configs.get(webhook_id)
        if not config:
            return None
        
        # Get delivery statistics
        recent_deliveries = [
            d for d in self.active_deliveries.values()
            if d.webhook_id == webhook_id and d.created_at > timezone.now() - timedelta(hours=24)
        ]
        
        total_deliveries = len(recent_deliveries)
        successful_deliveries = len([d for d in recent_deliveries if d.status == 'delivered'])
        failed_deliveries = len([d for d in recent_deliveries if d.status == 'failed'])
        
        return {
            'webhook_id': webhook_id,
            'advertiser_id': config.advertiser_id,
            'url': config.url,
            'events': config.events,
            'is_active': config.is_active,
            'total_deliveries_24h': total_deliveries,
            'successful_deliveries_24h': successful_deliveries,
            'failed_deliveries_24h': failed_deliveries,
            'success_rate_24h': (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0,
            'last_delivery': self._get_last_delivery_time(webhook_id)
        }
    
    async def handle_advertiser_event(self, event: Event):
        """Handle advertiser-related events."""
        event_data = event.data
        
        webhook_event = WebhookEvent(
            event_id=f"adv_{event_data.get('id', 'unknown')}_{int(time.time())}",
            event_type=self.event_mappings.get(event.event_type, event.event_type),
            data=event_data,
            source='advertiser_portal',
            timestamp=timezone.now(),
            advertiser_id=event_data.get('id')
        )
        
        await self.deliver_webhook(webhook_event)
    
    async def handle_campaign_event(self, event: Event):
        """Handle campaign-related events."""
        event_data = event.data
        
        webhook_event = WebhookEvent(
            event_id=f"camp_{event_data.get('id', 'unknown')}_{int(time.time())}",
            event_type=self.event_mappings.get(event.event_type, event.event_type),
            data=event_data,
            source='advertiser_portal',
            timestamp=timezone.now(),
            campaign_id=event_data.get('id'),
            advertiser_id=event_data.get('advertiser_id')
        )
        
        await self.deliver_webhook(webhook_event)
    
    async def handle_offer_event(self, event: Event):
        """Handle offer-related events."""
        event_data = event.data
        
        webhook_event = WebhookEvent(
            event_id=f"offer_{event_data.get('id', 'unknown')}_{int(time.time())}",
            event_type=self.event_mappings.get(event.event_type, event.event_type),
            data=event_data,
            source='advertiser_portal',
            timestamp=timezone.now(),
            offer_id=event_data.get('id'),
            advertiser_id=event_data.get('advertiser_id')
        )
        
        await self.deliver_webhook(webhook_event)
    
    async def handle_conversion_event(self, event: Event):
        """Handle conversion-related events."""
        event_data = event.data
        
        webhook_event = WebhookEvent(
            event_id=f"conv_{event_data.get('id', 'unknown')}_{int(time.time())}",
            event_type=self.event_mappings.get(event.event_type, event.event_type),
            data=event_data,
            source='advertiser_portal',
            timestamp=timezone.now(),
            conversion_id=event_data.get('id'),
            advertiser_id=event_data.get('advertiser_id'),
            campaign_id=event_data.get('campaign_id'),
            offer_id=event_data.get('offer_id')
        )
        
        await self.deliver_webhook(webhook_event)
    
    async def handle_billing_event(self, event: Event):
        """Handle billing-related events."""
        event_data = event.data
        
        webhook_event = WebhookEvent(
            event_id=f"bill_{event_data.get('id', 'unknown')}_{int(time.time())}",
            event_type=self.event_mappings.get(event.event_type, event.event_type),
            data=event_data,
            source='advertiser_portal',
            timestamp=timezone.now(),
            advertiser_id=event_data.get('advertiser_id')
        )
        
        await self.deliver_webhook(webhook_event)
    
    async def handle_fraud_event(self, event: Event):
        """Handle fraud-related events."""
        event_data = event.data
        
        webhook_event = WebhookEvent(
            event_id=f"fraud_{event_data.get('id', 'unknown')}_{int(time.time())}",
            event_type=self.event_mappings.get(event.event_type, event.event_type),
            data=event_data,
            source='advertiser_portal',
            timestamp=timezone.now(),
            advertiser_id=event_data.get('advertiser_id'),
            campaign_id=event_data.get('campaign_id')
        )
        
        await self.deliver_webhook(webhook_event)
    
    async def _find_matching_webhooks(self, webhook_event: WebhookEvent) -> List[WebhookConfig]:
        """Find webhooks that should receive the event."""
        matching_webhooks = []
        
        for config in self.webhook_configs.values():
            if not config.is_active:
                continue
            
            # Check if webhook is subscribed to this event type
            if webhook_event.event_type in config.events:
                # Check advertiser-specific webhooks
                if config.advertiser_id and config.advertiser_id != webhook_event.advertiser_id:
                    continue
                
                matching_webhooks.append(config)
        
        return matching_webhooks
    
    async def _prepare_webhook_payload(self, webhook_event: WebhookEvent, 
                                    config: WebhookConfig) -> Dict[str, Any]:
        """Prepare webhook payload with signature."""
        payload = {
            'event_id': webhook_event.event_id,
            'event_type': webhook_event.event_type,
            'data': webhook_event.data,
            'source': webhook_event.source,
            'timestamp': webhook_event.timestamp.isoformat(),
            'advertiser_id': webhook_event.advertiser_id,
            'campaign_id': webhook_event.campaign_id,
            'offer_id': webhook_event.offer_id,
            'conversion_id': webhook_event.conversion_id
        }
        
        # Add signature if secret key is configured
        if config.secret_key:
            payload['signature'] = self._generate_signature(payload, config.secret_key)
        
        return payload
    
    def _generate_signature(self, payload: Dict[str, Any], secret_key: str) -> str:
        """Generate HMAC signature for webhook payload."""
        # Create a copy without signature for signing
        payload_copy = payload.copy()
        payload_copy.pop('signature', None)
        
        # Convert to JSON string
        payload_str = json.dumps(payload_copy, sort_keys=True, separators=(',', ':'))
        
        # Generate HMAC signature
        signature = hmac.new(
            secret_key.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def _test_webhook_url(self, url: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
        """Test webhook URL connectivity."""
        try:
            # Create test payload
            test_payload = {
                'test': True,
                'timestamp': timezone.now().isoformat()
            }
            
            if secret_key:
                test_payload['signature'] = self._generate_signature(test_payload, secret_key)
            
            # Send test request
            headers = {'Content-Type': 'application/json'}
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=test_payload, headers=headers) as response:
                    if response.status < 400:
                        return {
                            'success': True,
                            'status_code': response.status,
                            'response': await response.text()
                        }
                    else:
                        return {
                            'success': False,
                            'status_code': response.status,
                            'error': f"HTTP {response.status}: {await response.text()}"
                        }
                        
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'Request timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _delivery_processing_loop(self):
        """Main webhook delivery processing loop."""
        while True:
            try:
                # Get batch of deliveries
                deliveries = []
                for _ in range(min(self.QUEUE_PROCESSING_BATCH_SIZE, self.delivery_queue.qsize())):
                    try:
                        delivery = self.delivery_queue.get_nowait()
                        deliveries.append(delivery)
                    except asyncio.QueueEmpty:
                        break
                
                if not deliveries:
                    await asyncio.sleep(0.1)  # Small delay when queue is empty
                    continue
                
                # Process deliveries in parallel
                tasks = []
                for delivery in deliveries:
                    task = asyncio.create_task(self._process_delivery(delivery))
                    tasks.append(task)
                
                # Wait for all tasks to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
            except Exception as e:
                logger.error(f"Error in delivery processing loop: {e}")
                await asyncio.sleep(1)  # Delay on error
    
    async def _process_delivery(self, delivery: WebhookDelivery):
        """Process a single webhook delivery."""
        try:
            config = self.webhook_configs.get(delivery.webhook_id)
            if not config or not config.is_active:
                delivery.status = 'failed'
                delivery.error_message = 'Webhook not found or inactive'
                return
            
            delivery.attempt_count += 1
            delivery.status = 'retrying'
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'AdvertiserPortal-Webhooks/1.0',
                'X-Webhook-Delivery-ID': delivery.delivery_id,
                'X-Webhook-Event': delivery.event_type
            }
            
            # Add custom headers
            headers.update(config.headers)
            
            # Send webhook
            timeout = aiohttp.ClientTimeout(total=config.timeout_seconds)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    config.url,
                    json=delivery.payload,
                    headers=headers
                ) as response:
                    delivery.response_status = response.status
                    delivery.response_body = await response.text()
                    
                    if response.status < 400:
                        delivery.status = 'delivered'
                        delivery.delivered_at = timezone.now()
                    else:
                        delivery.status = 'failed'
                        delivery.error_message = f"HTTP {response.status}: {delivery.response_body}"
            
            # Remove from active deliveries if successful or max attempts reached
            if delivery.status == 'delivered' or delivery.attempt_count >= delivery.max_attempts:
                self.active_deliveries.pop(delivery.delivery_id, None)
            
        except asyncio.TimeoutError:
            delivery.status = 'failed'
            delivery.error_message = 'Request timeout'
        except Exception as e:
            delivery.status = 'failed'
            delivery.error_message = str(e)
            logger.error(f"Error processing webhook delivery {delivery.delivery_id}: {e}")
    
    async def _retry_processing_loop(self):
        """Background loop for retrying failed deliveries."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Find failed deliveries that can be retried
                retry_deliveries = []
                
                for delivery in self.active_deliveries.values():
                    if (delivery.status == 'failed' and 
                        delivery.attempt_count < delivery.max_attempts):
                        retry_deliveries.append(delivery)
                
                # Retry deliveries
                for delivery in retry_deliveries:
                    await self.delivery_queue.put(delivery)
                    
            except Exception as e:
                logger.error(f"Error in retry processing loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _cleanup_loop(self):
        """Background loop for cleaning up old deliveries."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Remove old deliveries
                cutoff_time = timezone.now() - timedelta(hours=24)
                old_deliveries = [
                    delivery_id for delivery_id, delivery in self.active_deliveries.items()
                    if delivery.created_at < cutoff_time
                ]
                
                for delivery_id in old_deliveries:
                    self.active_deliveries.pop(delivery_id, None)
                    
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _cancel_pending_deliveries(self, webhook_id: str):
        """Cancel pending deliveries for a webhook."""
        pending_deliveries = [
            delivery_id for delivery_id, delivery in self.active_deliveries.items()
            if delivery.webhook_id == webhook_id and delivery.status in ['pending', 'retrying']
        ]
        
        for delivery_id in pending_deliveries:
            delivery = self.active_deliveries.get(delivery_id)
            if delivery:
                delivery.status = 'failed'
                delivery.error_message = 'Webhook unregistered'
    
    def _get_last_delivery_time(self, webhook_id: str) -> Optional[str]:
        """Get timestamp of last delivery for a webhook."""
        last_delivery = None
        
        for delivery in self.active_deliveries.values():
            if (delivery.webhook_id == webhook_id and 
                delivery.status == 'delivered' and
                (not last_delivery or delivery.delivered_at > last_delivery)):
                last_delivery = delivery.delivered_at
        
        return last_delivery.isoformat() if last_delivery else None
    
    async def _validate_webhook_config(self, config: WebhookConfig) -> Dict[str, Any]:
        """Validate webhook configuration."""
        errors = []
        
        # Check required fields
        if not config.webhook_id:
            errors.append("Webhook ID is required")
        
        if not config.advertiser_id:
            errors.append("Advertiser ID is required")
        
        if not config.url:
            errors.append("URL is required")
        
        # Validate URL
        try:
            parsed = urlparse(config.url)
            if not parsed.scheme or not parsed.netloc:
                errors.append("Invalid URL format")
            if parsed.scheme not in ['http', 'https']:
                errors.append("URL must use HTTP or HTTPS")
        except Exception:
            errors.append("Invalid URL format")
        
        # Validate events
        if not config.events:
            errors.append("At least one event must be specified")
        
        valid_events = list(self.event_mappings.keys())
        for event in config.events:
            if event not in valid_events:
                errors.append(f"Invalid event: {event}")
        
        # Validate parameters
        if config.retry_count < 0:
            errors.append("Retry count must be non-negative")
        
        if config.timeout_seconds <= 0:
            errors.append("Timeout must be positive")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


# Global integration instance
webhooks_integration = WebhooksIntegration()


# Export main classes
__all__ = [
    'WebhooksIntegration',
    'WebhookConfig',
    'WebhookDelivery',
    'WebhookEvent',
    'webhooks_integration',
]
