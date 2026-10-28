"""
Webhooks Integration
Webhook management and integration for external system notifications
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import hmac
import asyncio
import aiohttp
from urllib.parse import urlparse

from .integ_exceptions import IntegrationException, WebhookException
from .integ_constants import WebhookEvents, WebhookStatus

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Webhook event types"""
    BACKUP_CREATED = "backup.created"
    BACKUP_COMPLETED = "backup.completed"
    BACKUP_FAILED = "backup.failed"
    BACKUP_DELETED = "backup.deleted"
    RESTORATION_STARTED = "restoration.started"
    RESTORATION_COMPLETED = "restoration.completed"
    RESTORATION_FAILED = "restoration.failed"
    SCHEDULE_EXECUTED = "schedule.executed"
    SCHEDULE_FAILED = "schedule.failed"
    STORAGE_FULL = "storage.full"
    SECURITY_ALERT = "security.alert"
    SYSTEM_MAINTENANCE = "system.maintenance"
    CUSTOM_EVENT = "custom.event"


class WebhookStatus(Enum):
    """Webhook status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    ERROR = "error"


class WebhookDeliveryStatus(Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class WebhookConfig:
    """Webhook configuration"""
    webhook_id: str
    name: str
    url: str
    events: List[WebhookEventType]
    secret: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 5.0
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_delivery: Optional[datetime] = None
    delivery_count: int = 0
    failure_count: int = 0
    status: WebhookStatus = WebhookStatus.ACTIVE
    custom_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookPayload:
    """Webhook payload structure"""
    event_id: str
    event_type: WebhookEventType
    timestamp: datetime
    source: str
    data: Dict[str, Any]
    signature: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookDelivery:
    """Webhook delivery record"""
    delivery_id: str
    webhook_id: str
    event_id: str
    status: WebhookDeliveryStatus
    attempt: int
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class WebhookManager:
    """
    Manager for webhook operations
    """
    
    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.delivery_queue: asyncio.Queue = asyncio.Queue()
        self._processing = False
        self._worker_task = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Delivery tracking
        self.deliveries: Dict[str, WebhookDelivery] = {}
        
        # Statistics
        self.stats = {
            'total_webhooks': 0,
            'active_webhooks': 0,
            'total_deliveries': 0,
            'successful_deliveries': 0,
            'failed_deliveries': 0,
            'pending_deliveries': 0
        }
    
    async def start(self):
        """Start the webhook manager"""
        if self._processing:
            return
        
        try:
            self._processing = True
            self._session = aiohttp.ClientSession()
            
            # Start delivery worker
            self._worker_task = asyncio.create_task(self._delivery_worker())
            
            logger.info("Webhook manager started")
            
        except Exception as e:
            self._processing = False
            logger.error(f"Failed to start webhook manager: {e}")
            raise WebhookException(f"Failed to start webhook manager: {e}")
    
    async def stop(self):
        """Stop the webhook manager"""
        if not self._processing:
            return
        
        try:
            self._processing = False
            
            # Cancel worker task
            if self._worker_task:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
            
            # Close session
            if self._session:
                await self._session.close()
                self._session = None
            
            logger.info("Webhook manager stopped")
            
        except Exception as e:
            logger.error(f"Error stopping webhook manager: {e}")
    
    def register_webhook(self, config: WebhookConfig) -> str:
        """
        Register a new webhook
        
        Args:
            config: Webhook configuration
            
        Returns:
            Webhook ID
        """
        try:
            # Validate webhook configuration
            self._validate_webhook_config(config)
            
            # Store webhook
            self.webhooks[config.webhook_id] = config
            
            # Update statistics
            self.stats['total_webhooks'] = len(self.webhooks)
            if config.active and config.status == WebhookStatus.ACTIVE:
                self.stats['active_webhooks'] += 1
            
            logger.info(f"Registered webhook: {config.name} ({config.webhook_id})")
            
            return config.webhook_id
            
        except Exception as e:
            logger.error(f"Failed to register webhook: {e}")
            raise WebhookException(f"Failed to register webhook: {e}")
    
    def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister a webhook
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            True if successful, False otherwise
        """
        if webhook_id not in self.webhooks:
            return False
        
        webhook = self.webhooks[webhook_id]
        
        # Update statistics
        if webhook.active and webhook.status == WebhookStatus.ACTIVE:
            self.stats['active_webhooks'] -= 1
        
        # Remove webhook
        del self.webhooks[webhook_id]
        self.stats['total_webhooks'] = len(self.webhooks)
        
        logger.info(f"Unregistered webhook: {webhook.name} ({webhook_id})")
        
        return True
    
    def update_webhook(self, webhook_id: str, **updates) -> bool:
        """
        Update webhook configuration
        
        Args:
            webhook_id: Webhook ID
            **updates: Updates to apply
            
        Returns:
            True if successful, False otherwise
        """
        if webhook_id not in self.webhooks:
            return False
        
        webhook = self.webhooks[webhook_id]
        
        # Update active status if changed
        old_active = webhook.active and webhook.status == WebhookStatus.ACTIVE
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)
        
        webhook.updated_at = datetime.utcnow()
        
        # Update statistics if active status changed
        new_active = webhook.active and webhook.status == WebhookStatus.ACTIVE
        if old_active != new_active:
            if new_active:
                self.stats['active_webhooks'] += 1
            else:
                self.stats['active_webhooks'] -= 1
        
        logger.info(f"Updated webhook: {webhook.name} ({webhook_id})")
        
        return True
    
    async def trigger_webhook(self, event_type: WebhookEventType, data: Dict[str, Any], 
                           source: str = "backup_system", **metadata) -> List[str]:
        """
        Trigger webhooks for an event
        
        Args:
            event_type: Event type
            data: Event data
            source: Event source
            **metadata: Additional metadata
            
        Returns:
            List of webhook delivery IDs
        """
        delivery_ids = []
        
        # Find webhooks that should receive this event
        target_webhooks = [
            webhook for webhook in self.webhooks.values()
            if (webhook.active and 
                webhook.status == WebhookStatus.ACTIVE and
                event_type in webhook.events)
        ]
        
        if not target_webhooks:
            logger.debug(f"No webhooks found for event: {event_type.value}")
            return delivery_ids
        
        # Create payload
        payload = WebhookPayload(
            event_id=f"evt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{len(self.deliveries)}",
            event_type=event_type,
            timestamp=datetime.utcnow(),
            source=source,
            data=data,
            metadata=metadata
        )
        
        # Queue deliveries for each webhook
        for webhook in target_webhooks:
            # Create webhook-specific payload
            webhook_payload = self._create_webhook_payload(webhook, payload)
            
            # Create delivery record
            delivery = WebhookDelivery(
                delivery_id=f"del_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{len(self.deliveries)}",
                webhook_id=webhook.webhook_id,
                event_id=payload.event_id,
                status=WebhookDeliveryStatus.PENDING,
                attempt=1
            )
            
            # Store delivery
            self.deliveries[delivery.delivery_id] = delivery
            
            # Queue for delivery
            await self.delivery_queue.put((webhook, webhook_payload, delivery))
            
            delivery_ids.append(delivery.delivery_id)
            
            # Update statistics
            self.stats['total_deliveries'] += 1
            self.stats['pending_deliveries'] += 1
        
        logger.info(f"Triggered {len(target_webhooks)} webhooks for event: {event_type.value}")
        
        return delivery_ids
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """
        Get webhook configuration
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            Webhook configuration or None
        """
        return self.webhooks.get(webhook_id)
    
    def list_webhooks(self, status: Optional[WebhookStatus] = None, 
                      event_type: Optional[WebhookEventType] = None) -> List[WebhookConfig]:
        """
        List webhooks
        
        Args:
            status: Filter by status (optional)
            event_type: Filter by event type (optional)
            
        Returns:
            List of webhook configurations
        """
        webhooks = list(self.webhooks.values())
        
        # Filter by status
        if status:
            webhooks = [w for w in webhooks if w.status == status]
        
        # Filter by event type
        if event_type:
            webhooks = [w for w in webhooks if event_type in w.events]
        
        return webhooks
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """
        Get delivery information
        
        Args:
            delivery_id: Delivery ID
            
        Returns:
            Delivery information or None
        """
        return self.deliveries.get(delivery_id)
    
    def get_deliveries(self, webhook_id: Optional[str] = None, 
                      status: Optional[WebhookDeliveryStatus] = None,
                      limit: int = 100) -> List[WebhookDelivery]:
        """
        Get delivery records
        
        Args:
            webhook_id: Filter by webhook ID (optional)
            status: Filter by status (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of delivery records
        """
        deliveries = list(self.deliveries.values())
        
        # Filter by webhook ID
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        
        # Filter by status
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        # Sort by created date (newest first) and limit
        deliveries.sort(key=lambda d: d.created_at, reverse=True)
        
        return deliveries[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get webhook statistics
        
        Returns:
            Webhook statistics
        """
        stats = self.stats.copy()
        
        # Calculate success rate
        if stats['total_deliveries'] > 0:
            stats['success_rate'] = (stats['successful_deliveries'] / stats['total_deliveries']) * 100
        else:
            stats['success_rate'] = 0
        
        # Add webhook breakdown by status
        stats['webhooks_by_status'] = {}
        for status in WebhookStatus:
            stats['webhooks_by_status'][status.value] = len([
                w for w in self.webhooks.values() if w.status == status
            ])
        
        # Add delivery breakdown by status
        stats['deliveries_by_status'] = {}
        for status in WebhookDeliveryStatus:
            stats['deliveries_by_status'][status.value] = len([
                d for d in self.deliveries.values() if d.status == status
            ])
        
        return stats
    
    async def _delivery_worker(self):
        """Worker for processing webhook deliveries"""
        logger.info("Webhook delivery worker started")
        
        while self._processing:
            try:
                # Get delivery from queue
                webhook, payload, delivery = await asyncio.wait_for(
                    self.delivery_queue.get(), 
                    timeout=5.0
                )
                
                # Process delivery
                await self._process_delivery(webhook, payload, delivery)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Delivery worker error: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("Webhook delivery worker stopped")
    
    async def _process_delivery(self, webhook: WebhookConfig, payload: WebhookPayload, 
                              delivery: WebhookDelivery):
        """Process a webhook delivery"""
        try:
            delivery.status = WebhookDeliveryStatus.RETRYING
            
            # Send webhook
            success, response_status, response_body = await self._send_webhook(
                webhook, payload
            )
            
            if success:
                # Delivery successful
                delivery.status = WebhookDeliveryStatus.DELIVERED
                delivery.response_status = response_status
                delivery.response_body = response_body
                delivery.delivered_at = datetime.utcnow()
                
                # Update webhook statistics
                webhook.delivery_count += 1
                webhook.last_delivery = delivery.delivered_at
                
                # Update global statistics
                self.stats['successful_deliveries'] += 1
                
                logger.info(f"Webhook delivered successfully: {webhook.name} ({delivery.delivery_id})")
                
            else:
                # Delivery failed
                delivery.error_message = f"HTTP {response_status}: {response_body}"
                
                # Check if we should retry
                if delivery.attempt < webhook.retry_count:
                    # Schedule retry
                    delivery.attempt += 1
                    delivery.status = WebhookDeliveryStatus.PENDING
                    
                    # Add delay before retry
                    await asyncio.sleep(webhook.retry_delay * delivery.attempt)
                    
                    # Re-queue for retry
                    await self.delivery_queue.put((webhook, payload, delivery))
                    
                    logger.warning(f"Webhook delivery failed, retrying: {webhook.name} ({delivery.delivery_id})")
                    
                else:
                    # Max retries reached
                    delivery.status = WebhookDeliveryStatus.FAILED
                    
                    # Update webhook statistics
                    webhook.failure_count += 1
                    
                    # Update global statistics
                    self.stats['failed_deliveries'] += 1
                    
                    logger.error(f"Webhook delivery failed after retries: {webhook.name} ({delivery.delivery_id})")
            
            # Update pending count
            self.stats['pending_deliveries'] = self.delivery_queue.qsize()
            
        except Exception as e:
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.error_message = str(e)
            
            webhook.failure_count += 1
            self.stats['failed_deliveries'] += 1
            
            logger.error(f"Error processing webhook delivery: {e}")
    
    async def _send_webhook(self, webhook: WebhookConfig, payload: WebhookPayload) -> tuple[bool, int, str]:
        """
        Send webhook to target URL
        
        Args:
            webhook: Webhook configuration
            payload: Webhook payload
            
        Returns:
            Tuple of (success, status_code, response_body)
        """
        try:
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Backup-Integration-Webhook/1.0',
                'X-Webhook-Event': payload.event_type.value,
                'X-Webhook-ID': payload.event_id,
                'X-Webhook-Timestamp': payload.timestamp.isoformat(),
                'X-Webhook-Source': payload.source,
            }
            
            # Add custom headers
            headers.update(webhook.headers)
            
            # Add signature if secret is configured
            if webhook.secret:
                signature = self._generate_signature(webhook.secret, payload)
                headers['X-Webhook-Signature'] = signature
            
            # Prepare payload data
            payload_data = {
                'event_id': payload.event_id,
                'event_type': payload.event_type.value,
                'timestamp': payload.timestamp.isoformat(),
                'source': payload.source,
                'data': payload.data,
                'metadata': payload.metadata
            }
            
            # Send request
            async with self._session.post(
                webhook.url,
                json=payload_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=webhook.timeout)
            ) as response:
                response_body = await response.text()
                
                # Consider 2xx status codes as success
                success = 200 <= response.status < 300
                
                return success, response.status, response_body
                
        except asyncio.TimeoutError:
            return False, 408, "Request timeout"
        except aiohttp.ClientError as e:
            return False, 500, f"Client error: {str(e)}"
        except Exception as e:
            return False, 500, f"Unexpected error: {str(e)}"
    
    def _create_webhook_payload(self, webhook: WebhookConfig, payload: WebhookPayload) -> WebhookPayload:
        """Create webhook-specific payload"""
        webhook_payload = WebhookPayload(
            event_id=payload.event_id,
            event_type=payload.event_type,
            timestamp=payload.timestamp,
            source=payload.source,
            data=payload.data.copy(),
            metadata=payload.metadata.copy()
        )
        
        # Add custom data
        webhook_payload.data.update(webhook.custom_data)
        
        # Generate signature if secret is configured
        if webhook.secret:
            webhook_payload.signature = self._generate_signature(webhook.secret, webhook_payload)
        
        return webhook_payload
    
    def _generate_signature(self, secret: str, payload: WebhookPayload) -> str:
        """Generate webhook signature"""
        # Create payload string for signing
        payload_str = json.dumps({
            'event_id': payload.event_id,
            'event_type': payload.event_type.value,
            'timestamp': payload.timestamp.isoformat(),
            'data': payload.data
        }, sort_keys=True, separators=(',', ':'))
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def _validate_webhook_config(self, config: WebhookConfig):
        """Validate webhook configuration"""
        if not config.webhook_id:
            raise WebhookException("Webhook ID is required")
        
        if not config.name:
            raise WebhookException("Webhook name is required")
        
        if not config.url:
            raise WebhookException("Webhook URL is required")
        
        # Validate URL format
        parsed = urlparse(config.url)
        if not parsed.scheme or not parsed.netloc:
            raise WebhookException("Invalid webhook URL format")
        
        if parsed.scheme not in ['http', 'https']:
            raise WebhookException("Webhook URL must use HTTP or HTTPS")
        
        if not config.events:
            raise WebhookException("At least one event type must be specified")
        
        if config.timeout <= 0:
            raise WebhookException("Timeout must be positive")
        
        if config.retry_count < 0:
            raise WebhookException("Retry count must be non-negative")
        
        if config.retry_delay < 0:
            raise WebhookException("Retry delay must be non-negative")


# Global webhook manager instance
_webhook_manager = None


def get_webhook_manager() -> WebhookManager:
    """Get the global webhook manager instance"""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager


def initialize_webhook_manager() -> WebhookManager:
    """Initialize the global webhook manager"""
    global _webhook_manager
    _webhook_manager = WebhookManager()
    return _webhook_manager


# Export main classes and functions
__all__ = [
    'WebhookManager',
    'WebhookConfig',
    'WebhookPayload',
    'WebhookDelivery',
    'WebhookEventType',
    'WebhookStatus',
    'WebhookDeliveryStatus',
    'get_webhook_manager',
    'initialize_webhook_manager',
]
