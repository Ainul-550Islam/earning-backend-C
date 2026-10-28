"""
Webhooks Integration - External Webhook Management

Comprehensive webhook integration system for sending and receiving webhooks
with support for multiple providers, authentication, and retry mechanisms.
"""

import logging
import json
import hmac
import hashlib
import requests
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError, WebhookError, WebhookTimeoutError
from .circuit_breaker import CircuitBreaker, circuit_breaker_protection
from .event_bus import event_bus, Event

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    """Webhook status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    DISABLED = "disabled"


class WebhookAuthType(Enum):
    """Webhook authentication types."""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    HMAC = "hmac"
    OAUTH2 = "oauth2"


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    name: str
    url: str
    events: List[str]
    auth_type: WebhookAuthType = WebhookAuthType.NONE
    auth_credentials: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    secret_key: Optional[str] = None
    signature_algorithm: str = "sha256"
    signature_header: str = "X-Signature"
    timestamp_header: str = "X-Timestamp"
    idempotency_header: str = "X-Idempotency-Key"
    max_payload_size: int = 1048576  # 1MB
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """Webhook event data."""
    event_id: str
    webhook_name: str
    event_type: str
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=timezone.now)
    retry_count: int = 0
    max_retries: int = 3
    status: WebhookStatus = WebhookStatus.ACTIVE
    error_message: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class WebhookResponse:
    """Webhook response data."""
    success: bool
    status_code: int
    response_body: str
    headers: Dict[str, str]
    execution_time: float
    error_message: Optional[str] = None


class WebhookManager:
    """Webhook management system."""
    
    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_queue = Queue(maxsize=10000)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.statistics = {
            'total_webhooks': 0,
            'active_webhooks': 0,
            'events_sent': 0,
            'events_failed': 0,
            'events_retried': 0,
            'average_response_time': 0.0,
            'last_event_time': None
        }
        self._lock = threading.RLock()
        self._worker_threads: List[threading.Thread] = []
        self._running = False
        
        # Start worker threads
        self._start_workers()
    
    def _start_workers(self):
        """Start background worker threads."""
        self._running = True
        num_workers = min(4, max(1, getattr(settings, 'WEBHOOK_WORKERS', 2)))
        
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"WebhookWorker-{i}",
                daemon=True
            )
            worker.start()
            self._worker_threads.append(worker)
        
        logger.info(f"Started {num_workers} webhook workers")
    
    def _worker_loop(self):
        """Worker thread loop for processing webhook events."""
        while self._running:
            try:
                # Get event from queue
                event = self.event_queue.get(timeout=1)
                
                # Process webhook event
                self._process_webhook_event(event)
                
                # Mark task as done
                self.event_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Webhook worker error: {str(e)}")
    
    def _process_webhook_event(self, event: WebhookEvent):
        """Process webhook event."""
        start_time = timezone.now()
        
        try:
            # Get webhook configuration
            webhook_config = self.webhooks.get(event.webhook_name)
            if not webhook_config:
                event.status = WebhookStatus.FAILED
                event.error_message = f"Webhook not found: {event.webhook_name}"
                self._update_statistics(False, (timezone.now() - start_time).total_seconds())
                return
            
            # Check if webhook is active
            if not webhook_config.is_active:
                event.status = WebhookStatus.DISABLED
                event.error_message = "Webhook is inactive"
                return
            
            # Get circuit breaker
            circuit_breaker = self._get_circuit_breaker(event.webhook_name)
            
            # Send webhook through circuit breaker
            response = circuit_breaker.call(
                self._send_webhook_request,
                webhook_config,
                event
            )
            
            # Update event with response
            event.response_status = response.status_code
            event.response_body = response.response_body
            event.execution_time = response.execution_time
            event.status = WebhookStatus.ACTIVE if response.success else WebhookStatus.FAILED
            event.error_message = response.error_message
            
            # Update statistics
            self._update_statistics(response.success, response.execution_time)
            
            # Handle retry if failed
            if not response.success and event.retry_count < event.max_retries:
                self._schedule_retry(event)
            
            # Publish event
            self._publish_webhook_event(event, webhook_config)
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            event.status = WebhookStatus.FAILED
            event.error_message = str(e)
            self._update_statistics(False, (timezone.now() - start_time).total_seconds())
    
    def _send_webhook_request(self, webhook_config: WebhookConfig, event: WebhookEvent) -> WebhookResponse:
        """Send webhook request."""
        start_time = timezone.now()
        
        try:
            # Prepare payload
            payload = {
                'event': event.event_type,
                'data': event.payload,
                'timestamp': event.timestamp.isoformat(),
                'webhook_id': event.event_id,
                'source': 'rate_limit_system'
            }
            
            # Validate payload size
            payload_json = json.dumps(payload, default=str)
            if len(payload_json.encode()) > webhook_config.max_payload_size:
                raise WebhookError(f"Payload size exceeds limit: {len(payload_json.encode())} bytes")
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'RateLimit-Webhook/1.0',
                'X-Event-Type': event.event_type,
                'X-Event-ID': event.event_id,
                webhook_config.timestamp_header: event.timestamp.isoformat()
            }
            
            # Add custom headers
            headers.update(webhook_config.headers)
            headers.update(event.headers)
            
            # Add authentication
            auth_headers = self._get_auth_headers(webhook_config, payload_json)
            headers.update(auth_headers)
            
            # Add idempotency key
            if webhook_config.idempotency_header:
                headers[webhook_config.idempotency_header] = event.event_id
            
            # Make request
            response = requests.post(
                webhook_config.url,
                data=payload_json,
                headers=headers,
                timeout=webhook_config.timeout
            )
            
            # Parse response
            try:
                response_body = response.json()
            except ValueError:
                response_body = response.text
            
            return WebhookResponse(
                success=response.status_code < 400,
                status_code=response.status_code,
                response_body=response_body,
                headers=dict(response.headers),
                execution_time=(timezone.now() - start_time).total_seconds()
            )
            
        except requests.exceptions.Timeout:
            raise WebhookTimeoutError(f"Webhook timeout: {webhook_config.timeout}s")
        except requests.exceptions.RequestException as e:
            raise WebhookError(f"Webhook request failed: {str(e)}")
    
    def _get_auth_headers(self, webhook_config: WebhookConfig, payload: str) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {}
        
        if webhook_config.auth_type == WebhookAuthType.API_KEY:
            key_name = webhook_config.auth_credentials.get('key_name', 'X-API-Key')
            headers[key_name] = webhook_config.auth_credentials.get('api_key')
        
        elif webhook_config.auth_type == WebhookAuthType.BEARER_TOKEN:
            headers['Authorization'] = f"Bearer {webhook_config.auth_credentials.get('token')}"
        
        elif webhook_config.auth_type == WebhookAuthType.BASIC_AUTH:
            import base64
            credentials = f"{webhook_config.auth_credentials.get('username')}:{webhook_config.auth_credentials.get('password')}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"
        
        elif webhook_config.auth_type == WebhookAuthType.HMAC and webhook_config.secret_key:
            signature = hmac.new(
                webhook_config.secret_key.encode(),
                payload.encode(),
                getattr(hashlib, webhook_config.signature_algorithm)
            ).hexdigest()
            headers[webhook_config.signature_header] = signature
        
        elif webhook_config.auth_type == WebhookAuthType.OAUTH2:
            # Get OAuth2 token (implementation depends on provider)
            token = self._get_oauth2_token(webhook_config)
            headers['Authorization'] = f"Bearer {token}"
        
        return headers
    
    def _get_oauth2_token(self, webhook_config: WebhookConfig) -> str:
        """Get OAuth2 token."""
        # Check cache first
        cache_key = f"webhook_oauth_token_{webhook_config.name}"
        cached_token = cache.get(cache_key)
        
        if cached_token:
            return cached_token
        
        # Request new token
        token_url = webhook_config.auth_credentials.get('token_url')
        client_id = webhook_config.auth_credentials.get('client_id')
        client_secret = webhook_config.auth_credentials.get('client_secret')
        
        try:
            response = requests.post(
                token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': client_id,
                    'client_secret': client_secret
                },
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)
                
                # Cache token
                cache.set(cache_key, access_token, expires_in - 60)  # Refresh 1 minute early
                
                return access_token
            else:
                raise WebhookError(f"OAuth2 token request failed: {response.status_code}")
        
        except Exception as e:
            raise WebhookError(f"OAuth2 authentication failed: {str(e)}")
    
    def _get_circuit_breaker(self, webhook_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for webhook."""
        if webhook_name not in self.circuit_breakers:
            self.circuit_breakers[webhook_name] = CircuitBreaker(
                integration_name=f"webhook_{webhook_name}",
                failure_threshold=3,
                recovery_timeout=60,
                expected_exception=WebhookError
            )
        
        return self.circuit_breakers[webhook_name]
    
    def _schedule_retry(self, event: WebhookEvent):
        """Schedule webhook retry."""
        import threading
        
        def retry_webhook():
            import time
            time.sleep(5)  # Wait before retry
            
            event.retry_count += 1
            self.event_queue.put(event)
            self.statistics['events_retried'] += 1
        
        retry_thread = threading.Thread(target=retry_webhook, daemon=True)
        retry_thread.start()
    
    def _publish_webhook_event(self, event: WebhookEvent, webhook_config: WebhookConfig):
        """Publish webhook event to event bus."""
        try:
            import asyncio
            
            event_data = {
                'webhook_name': event.webhook_name,
                'event_type': event.event_type,
                'event_id': event.event_id,
                'status': event.status.value,
                'response_status': event.response_status,
                'execution_time': event.execution_time,
                'retry_count': event.retry_count,
                'timestamp': event.timestamp.isoformat()
            }
            
            if event.error_message:
                event_data['error_message'] = event.error_message
            
            # Publish to event bus
            asyncio.create_task(event_bus.publish(
                Event(f"webhook.{event.status.value}", event_data)
            ))
            
        except Exception as e:
            logger.error(f"Failed to publish webhook event: {str(e)}")
    
    def _update_statistics(self, success: bool, execution_time: float):
        """Update webhook statistics."""
        with self._lock:
            if success:
                self.statistics['events_sent'] += 1
            else:
                self.statistics['events_failed'] += 1
            
            self.statistics['last_event_time'] = timezone.now()
            
            # Update average response time
            total_events = self.statistics['events_sent'] + self.statistics['events_failed']
            if total_events == 1:
                self.statistics['average_response_time'] = execution_time
            else:
                current_avg = self.statistics['average_response_time']
                self.statistics['average_response_time'] = (
                    (current_avg * (total_events - 1) + execution_time) / total_events
                )
    
    def register_webhook(self, config: WebhookConfig) -> bool:
        """Register webhook."""
        try:
            with self._lock:
                self.webhooks[config.name] = config
                self.statistics['total_webhooks'] += 1
                
                if config.is_active:
                    self.statistics['active_webhooks'] += 1
            
            logger.info(f"Registered webhook: {config.name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to register webhook: {str(e)}")
            return False
    
    def unregister_webhook(self, name: str) -> bool:
        """Unregister webhook."""
        try:
            with self._lock:
                if name in self.webhooks:
                    config = self.webhooks[name]
                    del self.webhooks[name]
                    self.statistics['total_webhooks'] -= 1
                    
                    if config.is_active:
                        self.statistics['active_webhooks'] -= 1
                    
                    # Remove circuit breaker
                    if name in self.circuit_breakers:
                        self.circuit_breakers[name].shutdown()
                        del self.circuit_breakers[name]
                    
                    logger.info(f"Unregistered webhook: {name}")
                    return True
            
            return False
        
        except Exception as e:
            logger.error(f"Failed to unregister webhook: {str(e)}")
            return False
    
    def send_webhook(self, webhook_name: str, event_type: str, payload: Dict[str, Any], 
                    headers: Dict[str, str] = None) -> bool:
        """Send webhook event."""
        try:
            # Get webhook configuration
            webhook_config = self.webhooks.get(webhook_name)
            if not webhook_config:
                logger.error(f"Webhook not found: {webhook_name}")
                return False
            
            # Check if event type is supported
            if event_type not in webhook_config.events:
                logger.warning(f"Event type not supported by webhook {webhook_name}: {event_type}")
                return False
            
            # Create webhook event
            event = WebhookEvent(
                event_id=f"webhook_{webhook_name}_{timezone.now().timestamp()}",
                webhook_name=webhook_name,
                event_type=event_type,
                payload=payload,
                headers=headers or {},
                max_retries=webhook_config.retry_attempts
            )
            
            # Add to queue
            self.event_queue.put(event)
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to send webhook: {str(e)}")
            return False
    
    def send_webhook_sync(self, webhook_name: str, event_type: str, payload: Dict[str, Any],
                         headers: Dict[str, str] = None) -> WebhookResponse:
        """Send webhook synchronously."""
        try:
            # Get webhook configuration
            webhook_config = self.webhooks.get(webhook_name)
            if not webhook_config:
                raise WebhookError(f"Webhook not found: {webhook_name}")
            
            # Check if event type is supported
            if event_type not in webhook_config.events:
                raise WebhookError(f"Event type not supported: {event_type}")
            
            # Create webhook event
            event = WebhookEvent(
                event_id=f"webhook_sync_{webhook_name}_{timezone.now().timestamp()}",
                webhook_name=webhook_name,
                event_type=event_type,
                payload=payload,
                headers=headers or {},
                max_retries=0  # No retries for sync
            )
            
            # Send directly
            return self._send_webhook_request(webhook_config, event)
        
        except Exception as e:
            logger.error(f"Failed to send webhook sync: {str(e)}")
            raise
    
    def get_webhook(self, name: str) -> Optional[WebhookConfig]:
        """Get webhook configuration."""
        return self.webhooks.get(name)
    
    def get_all_webhooks(self) -> Dict[str, WebhookConfig]:
        """Get all webhook configurations."""
        return self.webhooks.copy()
    
    def get_active_webhooks(self) -> Dict[str, WebhookConfig]:
        """Get active webhook configurations."""
        return {
            name: config for name, config in self.webhooks.items()
            if config.is_active
        }
    
    def activate_webhook(self, name: str) -> bool:
        """Activate webhook."""
        with self._lock:
            webhook = self.webhooks.get(name)
            if webhook and not webhook.is_active:
                webhook.is_active = True
                self.statistics['active_webhooks'] += 1
                logger.info(f"Activated webhook: {name}")
                return True
        return False
    
    def deactivate_webhook(self, name: str) -> bool:
        """Deactivate webhook."""
        with self._lock:
            webhook = self.webhooks.get(name)
            if webhook and webhook.is_active:
                webhook.is_active = False
                self.statistics['active_webhooks'] -= 1
                logger.info(f"Deactivated webhook: {name}")
                return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get webhook statistics."""
        with self._lock:
            stats = self.statistics.copy()
            stats.update({
                'queue_size': self.event_queue.qsize(),
                'worker_threads': len(self._worker_threads),
                'running': self._running,
                'circuit_breakers': {
                    name: {
                        'state': cb.get_state().value,
                        'failure_count': cb.failure_count,
                        'last_failure_time': cb.last_failure_time.isoformat() if cb.last_failure_time else None
                    }
                    for name, cb in self.circuit_breakers.items()
                }
            })
            return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        queue_size = self.event_queue.qsize()
        error_rate = (
            self.statistics['events_failed'] / 
            max(1, self.statistics['events_sent'] + self.statistics['events_failed'])
        )
        
        health_status = {
            'status': 'healthy',
            'total_webhooks': self.statistics['total_webhooks'],
            'active_webhooks': self.statistics['active_webhooks'],
            'queue_size': queue_size,
            'error_rate': error_rate,
            'worker_threads': len(self._worker_threads),
            'running': self._running,
            'issues': []
        }
        
        # Check for issues
        if queue_size > 1000:
            health_status['issues'].append('High queue size')
            health_status['status'] = 'warning'
        
        if error_rate > 0.1:
            health_status['issues'].append('High error rate')
            health_status['status'] = 'warning'
        
        if not self._running:
            health_status['issues'].append('Webhook manager not running')
            health_status['status'] = 'error'
        
        return health_status
    
    def shutdown(self):
        """Shutdown webhook manager."""
        logger.info("Shutting down webhook manager...")
        
        # Stop workers
        self._running = False
        
        # Wait for workers to finish
        for worker in self._worker_threads:
            worker.join(timeout=5)
        
        # Shutdown circuit breakers
        for cb in self.circuit_breakers.values():
            cb.shutdown()
        
        # Clear queue
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except Empty:
                break
        
        logger.info("Webhook manager shutdown complete")


# Global webhook manager
webhook_manager = WebhookManager()


# Decorator for webhook event handling
def webhook_handler(webhook_name: str, event_types: List[str]):
    """Decorator for webhook event handlers."""
    def decorator(func):
        # Subscribe to webhook events
        for event_type in event_types:
            event_bus.subscribe(f"webhook.{event_type}", func)
        return func
    return decorator


# Convenience functions
def create_slack_webhook(name: str, webhook_url: str) -> WebhookConfig:
    """Create Slack webhook configuration."""
    return WebhookConfig(
        name=name,
        url=webhook_url,
        events=['rate_limit_exceeded', 'abuse_detected', 'ip_blocked', 'system_health'],
        auth_type=WebhookAuthType.NONE
    )


def create_discord_webhook(name: str, webhook_url: str) -> WebhookConfig:
    """Create Discord webhook configuration."""
    return WebhookConfig(
        name=name,
        url=webhook_url,
        events=['rate_limit_exceeded', 'abuse_detected', 'ip_blocked', 'system_health'],
        auth_type=WebhookAuthType.NONE
    )


def create_authenticated_webhook(name: str, url: str, api_key: str, events: List[str]) -> WebhookConfig:
    """Create authenticated webhook configuration."""
    return WebhookConfig(
        name=name,
        url=url,
        events=events,
        auth_type=WebhookAuthType.API_KEY,
        auth_credentials={'api_key': api_key}
    )


def create_hmac_webhook(name: str, url: str, secret: str, events: List[str]) -> WebhookConfig:
    """Create HMAC webhook configuration."""
    return WebhookConfig(
        name=name,
        url=url,
        events=events,
        auth_type=WebhookAuthType.HMAC,
        secret_key=secret
    )
